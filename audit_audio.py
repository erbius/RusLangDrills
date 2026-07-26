import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
import re, hashlib

def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())

CYRILLIC_TO_LATIN = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh","з":"z",
    "и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r",
    "с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts","ч":"ch","ш":"sh",
    "щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
}

def transliterate(value: str) -> str:
    return "".join(CYRILLIC_TO_LATIN.get(c, c) for c in value.lower())

def slugify_text(value: str) -> str:
    t = transliterate(normalize_text(value))
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return t or f"w-{hashlib.sha1(normalize_text(value).encode('utf-8')).hexdigest()[:12]}"

def extract_words_from_json(data_path):
    data = json.loads(data_path.read_text(encoding="utf-8"))
    words_set = set()
    if "vocabulary" in data:
        for item in data["vocabulary"]:
            if "ru" in item:
                words_set.add(item["ru"].lower().strip())
    if "verbs" in data:
        for verb_key in data["verbs"].keys():
            words_set.add(verb_key.lower().strip())
    return sorted(list(words_set))

data_path = Path("data.json")
data = json.loads(data_path.read_text(encoding="utf-8"))

# What the script will extract
words = extract_words_from_json(data_path)

# Check for slug collisions
slugs = [slugify_text(w) for w in words]
slug_counts = {}
for w, s in zip(words, slugs):
    slug_counts.setdefault(s, []).append(w)
collisions = {s: ws for s, ws in slug_counts.items() if len(ws) > 1}

# Check for "[Translation needed" in the words that will be voiced
missing_en = [item for item in data['vocabulary'] if '[Translation needed' in item.get('en','')]

print(f"=== Audio Generation Audit ===\n")
print(f"Vocabulary items:          {len(data['vocabulary'])}")
print(f"Verb infinitives:          {len(data['verbs'])}")
print(f"Unique words (audio clips):{len(words)}")
print(f"Slug collisions:           {len(collisions)}")
print(f"Words still missing EN:    {len(missing_en)}")

# Show how many of each word type
vocab_by_type = {}
for item in data['vocabulary']:
    t = item.get('type','?')
    vocab_by_type[t] = vocab_by_type.get(t, 0) + 1
print(f"\nVocabulary by type:")
for k,v in sorted(vocab_by_type.items()):
    print(f"  {k:<15} {v}")

print(f"\nSample words (first 10):")
for w in words[:10]:
    print(f"  {w}")
print(f"  ...")
print(f"  (total {len(words)} unique Russian words → {len(words)} .wav clips)")

if collisions:
    print(f"\n⚠️  SLUG COLLISIONS (same filename for different words):")
    for s, ws in collisions.items():
        print(f"  slug '{s}': {ws}")
else:
    print(f"\n✅ No slug collisions — all clips will have unique filenames")

# Verb conjugation forms (the script does NOT generate conjugations — only infinitives)
# Check if verbs in data have conjugation forms
sample_verb = next(iter(data['verbs'].values()))
conj_forms = list(sample_verb.get('conjugations', {}).keys())
print(f"\n⚠️  Note: script extracts verb INFINITIVES only (not conjugation forms)")
print(f"   Sample verb conjugation keys: {conj_forms}")
print(f"   Conjugations would add: {len(data['verbs'])} verbs × {len(conj_forms)} forms = {len(data['verbs'])*len(conj_forms)} extra clips")
print(f"\nCurrent script clip count:     {len(words)} clips (vocab + verb infinitives)")
print(f"With conjugations added:       {len(words) + len(data['verbs'])*len(conj_forms)} clips")
