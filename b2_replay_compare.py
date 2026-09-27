"""Summarize matched B2 fixed replay and prefire runs."""
import csv
import json
from pathlib import Path

base = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1')
paths = {
    'R2_fire': base/'b2_auto_round2/replay_B2_20_60',
    'R3_fire': base/'b2_auto_round3/replay_B2_20_60',
    'R4_fire': base/'b2_auto_round4/replay_B2_20_60',
    'R2_prefire': base/'b2_auto_round4/prefire_R2',
    'R4_prefire': base/'b2_auto_round4/prefire_R4',
}
summary = {}
for label, root in paths.items():
    manifest = json.loads((root/'manifest.json').read_text())
    with (root/'fixed_fire_live.csv').open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    active = [r['active'] == '1' for r in rows]
    starts = [j for j, val in enumerate(active) if val and (j == 0 or not active[j-1])]
    runs = []
    for start in starts:
        end = start
        while end < len(active) and active[end]:
            end += 1
        runs.append(end-start)
    frame_events = [json.loads(s) for s in (root/'results.jsonl').read_text().splitlines() if s.strip()]
    sensors = {}
    for sensor in ('V', 'T'):
        ev = [x for x in frame_events if x.get('type') == 'frame' and x.get('sensor') == sensor]
        sensors[sensor] = {'frames': len(ev), 'frames_with_raw_detection': sum(bool(x['raw_detections']) for x in ev),
                           'raw_detections': sum(len(x['raw_detections']) for x in ev),
                           'frames_with_track': sum(bool(x['tracks']) for x in ev),
                           'track_ids': sorted({str(t.get('track_id',t.get('id'))) for x in ev for t in x['tracks']})}
    summary[label] = {'active_frames': sum(active), 'total_coordinate_frames': len(active),
                      'active_runs': len(runs), 'longest_active_run_frames': max(runs, default=0),
                      'first_active_pts_s': next((float(r['pts_s']) for r in rows if r['active']=='1'), None),
                      'paired_count': manifest['paired_count'], 'errors': manifest['errors'],
                      'sensors': sensors}
print(json.dumps(summary, ensure_ascii=False, indent=2))
