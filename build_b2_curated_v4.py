"""Tighten B2 V labels to the dominant visible flame envelope."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

BOX = {
    'obs_000283': [886, 615, 916, 677],
    'obs_000291': [864, 489, 1076, 693],
    'obs_000219': [952, 432, 1064, 605],
    'obs_000227': [951, 408, 1104, 638],
    'obs_000235': [908, 459, 1074, 642],
    'obs_000257': [1152, 534, 1189, 607],
    'obs_000273': [720, 0, 1080, 650],
    'obs_000281': [850, 0, 1150, 680],
    'obs_000297': [739, 311, 1147, 756],
    'obs_000217': [882, 470, 1015, 560],
    'obs_000294': [314, 179, 890, 1080],
    'obs_000253': [963, 427, 1067, 635],
    'obs_000269': [931, 429, 1140, 657],
    'obs_000215': [590, 729, 718, 948],
    'obs_000212': [731, 0, 1270, 958],
    'obs_000276': [955, 562, 1156, 705],
    'obs_000292': [808, 270, 1165, 727],
    'obs_000300': [952, 583, 1147, 815],
    'obs_000250': [912, 667, 1003, 890],
    'obs_000296': [1040, 687, 1115, 825],
    'obs_000232': [840, 650, 1160, 965],
    'obs_000248': [695, 600, 950, 825],
}
IGNORE = {'obs_000205', 'obs_000207'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

p = argparse.ArgumentParser()
p.add_argument('--base', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
if a.output.exists():
    raise SystemExit('output already exists')
shutil.copytree(a.base, a.output)
manifest = json.loads((a.output / 'manifest.json').read_text())
for row in manifest['records']:
    oid = row['observation_id']
    if oid not in BOX and oid not in IGNORE:
        continue
    split = row['split']
    image = a.output / 'V/images' / split / (oid + '.jpg')
    label = a.output / 'V/labels' / split / (oid + '.txt')
    if oid in IGNORE:
        image.unlink()
        label.unlink()
        row.update(status='ignore', reason='dispersed_or_weak_flame_cannot_be_bounded_consistently')
        for key in ('box_xyxy_px', 'reviewed_image_sha256', 'label_sha256'):
            row.pop(key, None)
        continue
    x1, y1, x2, y2 = BOX[oid]
    if not (0 <= x1 < x2 <= 1920 and 0 <= y1 < y2 <= 1080):
        raise ValueError(oid)
    line = f'0 {(x1+x2)/3840:.10f} {(y1+y2)/2160:.10f} {(x2-x1)/1920:.10f} {(y2-y1)/1080:.10f}\n'
    label.write_text(line)
    row.update(box_xyxy_px=BOX[oid], label_sha256=sha(label),
               review_method='manual_dominant_flame_envelope_after_color_proposal_review')
manifest['schema_version'] = 'b2_curated_v4'
manifest['created_utc'] = datetime.now(timezone.utc).isoformat()
manifest['parent_manifest_sha256'] = sha(a.base / 'manifest.json')
manifest['label_policy'] = 'One dominant visible flame envelope per positive image; ambiguous/dispersed cases ignored.'
manifest['holdout_caveat'] = 'This video has been inspected during earlier rounds; scenario diagnostic, not a fresh confirmation set.'
from collections import Counter
manifest['counts'] = {split: dict(Counter(row['status'] for row in manifest['records'] if row['split'] == split))
                      for split in ('train', 'development', 'holdout')}
(a.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
(a.output / 'V/dataset.yaml').write_text(f'path: {a.output / "V"}\ntrain: images/train\nval: images/development\nnames: {{0: flame}}\n')
print(manifest['counts'])
