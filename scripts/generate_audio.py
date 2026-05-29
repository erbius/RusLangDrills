import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf
import torch


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def transliterate(value: str) -> str:
    pieces = []
    for char in value.lower():
        pieces.append(CYRILLIC_TO_LATIN.get(char, char))
    return "".join(pieces)


def slugify_text(value: str) -> str:
    transliterated = transliterate(normalize_text(value))
    transliterated = re.sub(r"[^a-z0-9]+", "-", transliterated)
    transliterated = re.sub(r"-+", "-", transliterated).strip("-")
    return transliterated or f"w-{hashlib.sha1(normalize_text(value).encode('utf-8')).hexdigest()[:12]}"


def get_item_text(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("text") or item.get("ru") or ""
    return ""


def get_item_category(item) -> str:
    if isinstance(item, dict):
        return normalize_text(str(item.get("category") or item.get("group") or item.get("type") or ""))
    return ""


def get_item_speed(item, text: str, category: str, rules: dict) -> str:
    normalized = normalize_text(text)
    if isinstance(item, dict):
        if "speed" in item:
            rate_value = str(item["speed"]).strip().lower()
            if rate_value in {"x-slow", "slow", "medium", "fast", "x-fast"}:
                return rate_value
        if "rate" in item:
            rate = str(item["rate"]).strip().lower()
            if rate == "slow":
                return "slow"
            if rate == "slower":
                return "x-slow"
            if rate == "normal":
                return "medium"

    category_speeds = rules.get("categorySpeeds", {}) if isinstance(rules, dict) else {}
    if category and category in category_speeds:
        rate_value = str(category_speeds[category]).strip().lower()
        if rate_value in {"x-slow", "slow", "medium", "fast", "x-fast"}:
            return rate_value

    slow_categories = set()
    if isinstance(rules, dict):
        slow_categories = {normalize_text(value) for value in rules.get("slowCategories", []) if value}
    if category and category in slow_categories:
        return "slow"

    slow_words = set()
    if isinstance(rules, dict):
        slow_words = {normalize_text(value) for value in rules.get("slowWords", []) if value}
    if normalized in slow_words:
        return "slow"

    fast_words = set()
    if isinstance(rules, dict):
        fast_words = {normalize_text(value) for value in rules.get("fastWords", []) if value}
    if normalized in fast_words:
        return "medium"

    if " " not in normalized and len(normalized) <= 5:
        return "slow"
    if len(normalized) >= 10 and " " not in normalized:
        return "slow"
    return "medium"


def load_words(words_path: Path):
    raw = json.loads(words_path.read_text(encoding="utf-8"))
    raw_words = raw.get("words", raw) if isinstance(raw, dict) else raw
    rules = raw.get("rules", {}) if isinstance(raw, dict) else {}
    category_lookup = {}
    if isinstance(raw, dict):
        for category_name, category_words in (raw.get("categories") or {}).items():
            for category_word in category_words or []:
                category_lookup[normalize_text(str(category_word))] = normalize_text(str(category_name))
    if not isinstance(raw_words, list):
        raise ValueError("words.json must be a list or an object with a 'words' list")

    deduped = {}
    for item in raw_words:
        text = get_item_text(item)
        if isinstance(item, str):
            clip_id = None
            explicit_slug = None
            source_item = {"text": text}
        elif isinstance(item, dict):
            clip_id = item.get("id")
            explicit_slug = item.get("slug") or item.get("filename")
            source_item = dict(item)
        else:
            continue

        text = text.strip()
        if not text:
            continue

        key = normalize_text(text)
        if not key:
            continue

        category = get_item_category(item) or category_lookup.get(key, "")

        if not clip_id:
            clip_id = slugify_text(explicit_slug or text)

        clip_id = re.sub(r"[^a-z0-9-]+", "", clip_id.lower())
        if not clip_id:
            clip_id = f"w-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"

        if key not in deduped:
            deduped[key] = {"id": clip_id, "text": text, "category": category, "source": source_item, "rules": rules}

    return list(deduped.values())


def load_tts_model(language: str, model_id: str):
    model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language=language,
        speaker=model_id,
        trust_repo=True,
    )
    model.to(torch.device("cpu"))
    return model


def resolve_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def main():
    parser = argparse.ArgumentParser(description="Generate pronunciation clips with Silero TTS")
    parser.add_argument("--words", default="audio/words.json", help="Path to words list JSON")
    parser.add_argument("--output", default="audio/clips", help="Directory for generated clips")
    parser.add_argument("--manifest", default="audio/manifest.json", help="Manifest output path")
    parser.add_argument("--language", default="ru", help="Silero language code")
    parser.add_argument("--model-id", default="v5_5_ru", help="Silero model id")
    parser.add_argument("--speaker", default="xenia", help="Voice speaker id")
    parser.add_argument("--sample-rate", type=int, default=48000, help="Audio sample rate")
    parser.add_argument("--prune", action="store_true", help="Delete clips not present in words list")
    args = parser.parse_args()

    repo_root = Path.cwd()
    words_path = repo_root / args.words
    output_dir = repo_root / args.output
    manifest_path = repo_root / args.manifest

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    words = load_words(words_path)
    if not words:
        raise RuntimeError("No words found to synthesize")

    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    model = load_tts_model(args.language, args.model_id)

    items = []
    by_text = {}
    expected_files = set()

    for entry in words:
        text = entry["text"]
        text_key = normalize_text(text)
        clip_name = f"{entry['id']}.wav"
        clip_path = output_dir / clip_name
        speed = get_item_speed(entry.get("source", {}), text, entry.get("category", ""), entry.get("rules", {}))

        if speed != "medium":
            audio_text = f'<speak><prosody rate="{speed}">{text}</prosody></speak>'
            audio = model.apply_tts(
                ssml_text=audio_text,
                speaker=args.speaker,
                sample_rate=args.sample_rate,
            )
        else:
            audio = model.apply_tts(
                text=text,
                speaker=args.speaker,
                sample_rate=args.sample_rate,
                put_accent=True,
                put_yo=True,
            )

        audio_np = audio.detach().cpu().numpy()
        sf.write(clip_path, audio_np, args.sample_rate)

        rel_path = resolve_relative(clip_path, repo_root)
        items.append({"id": entry["id"], "text": text, "path": rel_path, "rate": speed})
        by_text[text_key] = rel_path
        expected_files.add(clip_path.resolve())

    if args.prune:
        for clip_file in output_dir.glob("*.wav"):
            if clip_file.resolve() not in expected_files:
                clip_file.unlink()

    manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sampleRate": args.sample_rate,
        "items": items,
        "byText": by_text,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Generated {len(items)} clips into {output_dir}")


if __name__ == "__main__":
    main()
