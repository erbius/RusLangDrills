# Audio Workflow

This project serves pronunciation clips from `audio/clips` using `audio/manifest.json`.

## Add New Words

1. Edit `audio/words.json`.
2. Add a new entry to the `words` list.
3. If you want the clip to sound slower or use a specific slug, add the word to the matching category in `categories` or turn it into an object with `text`, `category`, `slug`, or `speed`.
3. Commit and push.

The `Generate Audio Clips` workflow will regenerate clips and update `audio/manifest.json`.

## Catalog Rules

The generator reads the `rules` and `categories` sections in `audio/words.json`.

- `rules.categorySpeeds` maps categories to rates like `slow`, `medium`, or `x-slow`.
- `categories` lets you place future words into a group without changing the Python script.
- Word objects can still override everything with explicit `speed`, `rate`, `category`, `slug`, or `filename` values.

## Manual Run

You can run the workflow manually from the Actions tab using `workflow_dispatch`.

## Local Generation

```bash
python -m pip install -r requirements-audio.txt
python scripts/generate_audio.py --prune
```

Generated clips are deterministic by text key, so existing words keep stable file names.
