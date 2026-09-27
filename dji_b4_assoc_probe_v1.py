"""Probe scene association on an existing frozen B4 replay result."""
import collections
import json
from pathlib import Path

from dji_b4_source_assoc_v1 import associate

root = Path(r'D:\课题\_dji_preview')
scene = json.loads((root / 'B4_scene_map_v1.json').read_text(encoding='utf-8'))
events = [json.loads(x) for x in (root / 'B4_primary_results.jsonl').open(encoding='utf-8')]
recent = {}
counts = collections.Counter()
for event in events:
    event['image_size_px'] = [1920, 1080] if event['sensor'] == 'V' else [1280, 1024]
    rows = associate(event, scene, recent)
    for row in rows:
        counts[event['sensor'], row['association_status'], row['point_id']] += 1
    if event['frame_seq'] in (1, 15, 30, 45, 75, 120, 150):
        print(event['sensor'], event['pts_s'], [(x['point_id'], x['association_status'], x['reason_zh']) for x in rows])
print(dict(counts))
