import collections
import json
from pathlib import Path

root = Path(r'D:\课题\_dji_preview')
queue = json.loads((root / 'source_truth_queue.json').read_text(encoding='utf-8'))
decisions = json.loads((root / 'source_truth_decisions.json').read_text(encoding='utf-8'))['decisions']
groups = collections.defaultdict(list)
for task in queue['tasks']:
    if task['clip_id'].startswith('B4_') or task['clip_id'].startswith(('visible_', 'multiple_', 'paired_', 'residual_')):
        d = decisions[task['task_id']]
        groups[task['clip_id']].append({
            'task': task['task_id'], 'pts': task.get('visible_pts_s'),
            'state': d['source_state'], 'relation': d['tv_relation'],
            'V': d['V']['points'], 'T': d['T']['points'],
        })
for clip, rows in groups.items():
    ids = {s: collections.Counter(p[2] for r in rows for p in r[s]) for s in ('V', 'T')}
    states = collections.Counter(r['state'] for r in rows)
    print(clip, 'rows', len(rows), 'states', dict(states), 'IDs', {s: dict(c) for s, c in ids.items()})
    for row in rows:
        print(' ', row)

from PIL import Image
for sensor in ('V', 'T'):
    with Image.open(root / f'B4_{sensor}_000040.jpg') as image:
        print(sensor, 'size', image.size)
events = [json.loads(line) for line in (root / 'B4_primary_results.jsonl').open(encoding='utf-8')]
for sensor in ('V', 'T'):
    xs = [x for x in events if x['sensor'] == sensor]
    print(sensor, 'frame count', len(xs), 'detections', sum(len(x['raw_detections']) for x in xs))
    for x in xs[::15]:
        print(round(x['pts_s'], 2), [(round(d['bbox_xyxy_px'][0]), round(d['bbox_xyxy_px'][1]), round(d['bbox_xyxy_px'][2]), round(d['bbox_xyxy_px'][3]), round(d['confidence'], 2)) for d in x['raw_detections']])
