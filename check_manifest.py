import json
from pathlib import Path

manifest = json.loads(Path('audio/manifest.json').read_text(encoding='utf-8'))
items = manifest.get('items', [])
clips_on_disk = list(Path('audio/clips').glob('*.wav'))
missing_files = [i for i in items if not Path(i['path']).exists()]

print(f"Manifest entries : {len(items)}")
print(f"Files on disk    : {len(clips_on_disk)}")
print(f"Missing files    : {len(missing_files)}")
print(f"Generated at     : {manifest.get('generatedAt','?')}")
print(f"Sample rate      : {manifest.get('sampleRate','?')} Hz")

if missing_files:
    print("\nMISSING:")
    for m in missing_files[:10]:
        print(f"  {m['path']}")
else:
    print("\nAll clips present on disk.")

# Check a few entries for correctness
print("\nSample manifest entries:")
for item in items[:5]:
    print(f"  {item['text']:<20} -> {item['path']}")
