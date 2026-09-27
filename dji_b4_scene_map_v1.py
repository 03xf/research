"""Build a scene-specific B4 source lookup from existing human image points."""
import argparse
import csv
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    truth = root / 'source_truth_review_v1'
    queue_path, decision_path = truth / 'queue.json', truth / 'decisions.json'
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    decisions = json.loads(decision_path.read_text(encoding='utf-8'))['decisions']
    clip_id = 'multiple_boxes_0_DJI_202609081039_006_pts_v2'
    reference = next(c for c in queue['clips'] if c['clip_id'] == clip_id)
    source = reference['source']
    if source['batch_id'] != 'B4' or source['session_id'] != 'DJI_202609081039_006':
        raise ValueError('unexpected reference scene')
    points = {(sensor, side): [] for sensor in ('V', 'T') for side in ('west', 'east')}
    used = []
    for task in queue['tasks']:
        if task['clip_id'] != clip_id:
            continue
        choice = decisions[task['task_id']]
        if (choice['frame_status'], choice['source_state'], choice['tv_relation']) != ('usable', 'active_fire', 'same_source'):
            raise ValueError('uncertain source truth: ' + task['task_id'])
        used.append(task['task_id'])
        for sensor in ('V', 'T'):
            marks = choice[sensor]['points']
            if len(marks) != 2:
                raise ValueError('two physical sources expected: ' + task['task_id'])
            for x, y, _legacy_id in marks:
                side = 'west' if x < 0.5 else 'east'
                points[sensor, side].append((float(x), float(y)))
    if len(used) != 10 or any(len(p) != 10 for p in points.values()):
        raise ValueError('incomplete ten-pair source evidence')
    anchors = {}
    for (sensor, side), marks in points.items():
        mx = statistics.median(x for x, _ in marks)
        my = statistics.median(y for _, y in marks)
        deviation = max(((x-mx)**2+(y-my)**2)**0.5 for x, y in marks)
        if deviation > 0.055:
            raise ValueError('scene anchor not stable: ' + sensor + side)
        anchors.setdefault(side, {})[sensor] = {
            'point_normalized': [mx, my],
            'manual_points': len(marks),
            'max_manual_deviation_normalized': deviation,
        }
    marks_path = root.parent / 'localization_v2' / 'b4_video_source_marks.csv'
    inventory_path = root.parent / 'localization_v2' / 'fire_coordinate_inventory_v3.csv'
    with marks_path.open(encoding='utf-8-sig', newline='') as f:
        source_marks = list(csv.DictReader(f))
    with inventory_path.open(encoding='utf-8-sig', newline='') as f:
        inventory = {r['point_id']: r for r in csv.DictReader(f)}
    sources = []
    for side, point_id in (('east', 'B4_video_east_near_road'), ('west', 'B4_video_west_near_tree')):
        matches = [m for m in source_marks if m['point_id'] == point_id and m['session'] == source['session_id']
                   and m['source_mp4'] == source['visible_video']]
        if len(matches) != 1:
            raise ValueError('missing unique visual coordinate mark: ' + point_id)
        mark = matches[0]
        vx, vy = anchors[side]['V']['point_normalized']
        if abs(vx-float(mark['source_pixel_x'])/1920) > 0.06 or abs(vy-float(mark['source_pixel_y'])/1080) > 0.06:
            raise ValueError('coordinate mark does not align with human scene point: ' + point_id)
        coord = inventory[point_id]
        if coord['status'] != 'provisional_visual' or coord['batch_id'] != 'B4':
            raise ValueError('coordinate source status mismatch: ' + point_id)
        sources.append({
            'point_id': point_id,
            'name_zh': '东侧靠道路火源' if side == 'east' else '西侧靠树木火源',
            'side': side,
            'latitude': float(coord['latitude']),
            'longitude': float(coord['longitude']),
            'coordinate_status': 'provisional_visual',
            'coordinate_method': coord['source'],
            'anchors': anchors[side],
        })
    scene = {
        'schema_version': 'dji_b4_scene_source_map_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'batch_id': 'B4',
        'session_id': source['session_id'],
        'video_group': source['video_group'],
        'visible_video': source['visible_video'],
        'thermal_video': source['thermal_video'],
        'source_count': 2,
        'sources': sources,
        'association_scope': 'this fixed-camera video group only; the source point coordinates are approximate visual candidates',
        'association_gate': {'V_radius_normalized': 0.12, 'T_radius_normalized': 0.10,
                             'require_V_flame_for_coordinate': True, 'T_recent_V_seconds': 0.6},
        'provenance': {'human_queue_sha256': sha(queue_path), 'human_decisions_sha256': sha(decision_path),
                       'source_marks_sha256': sha(marks_path), 'inventory_sha256': sha(inventory_path),
                       'human_tasks': used,
                       'legacy_F1_label': 'nonunique across the two physical fires; ignored for geographic association'},
        'limits': ['No camera calibration or independent absolute visual WGS84 accuracy',
                   'The LRF B4_F1 point is about 78 m from these two video candidates and is not assigned to them',
                   'B4 F2 remains three separate unassigned postfire candidates'],
    }
    output = root / 'realtime_v3' / 'scene_map_b4_1039_006_v1.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(output), 'sha256': sha(output), 'sources': sources}, ensure_ascii=False))


if __name__ == '__main__':
    main()
