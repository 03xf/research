"""Exploratory B4 scene-lookup audit against existing reviewed image points."""
import argparse
import collections
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


RUNS = {
    'visible_flame_0_DJI_202609081039_006_pts_v2': 'B4_primary_location_dashboard_final',
    'paired_negative_0_DJI_202609081039_006_pts_v2': 'B4_prelight_check',
    'multiple_boxes_0_DJI_202609081039_006_pts_v2': 'B4_two_sources_check',
}
SIDE_IDS = {'east': 'B4_video_east_near_road', 'west': 'B4_video_west_near_tree'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def side(point):
    return 'west' if float(point[0]) < .5 else 'east'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    truth_root = root / 'source_truth_review_v1'
    queue_path, decisions_path = truth_root / 'queue.json', truth_root / 'decisions.json'
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    decisions = json.loads(decisions_path.read_text(encoding='utf-8'))['decisions']
    scene_path = root / 'realtime_v3' / 'scene_map_b4_1039_006_v1.json'
    scene = json.loads(scene_path.read_text(encoding='utf-8'))
    coords = {x['point_id']: x for x in scene['sources']}
    totals = collections.Counter()
    per_clip = {}
    rows = []
    for clip_id, run_name in RUNS.items():
        run = root / 'realtime_v3' / run_name
        manifest_path = run / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if Path(manifest['source']).name != clip_id or manifest['scene_map_sha256'] != sha(scene_path):
            raise ValueError('scene or clip mismatch: ' + run_name)
        if manifest['errors'] or manifest['frames'] != {'V': 150, 'T': 150}:
            raise ValueError('incomplete replay: ' + run_name)
        with (run / 'positions.csv').open(encoding='utf-8-sig', newline='') as f:
            positions = list(csv.DictReader(f))
        with (run / 'results.jsonl').open(encoding='utf-8') as f:
            events = [json.loads(line) for line in f]
        if len(events) != 300:
            raise ValueError('missing frame rows: ' + run_name)
        counts = collections.Counter()
        per_frame_sources = collections.Counter()
        track_sources = collections.defaultdict(set)
        for pos in positions:
            status, point_id = pos['association_status'], pos['point_id']
            if status == 'provisional_visual_lookup':
                if point_id not in coords or pos['coordinate_source'] != 'provisional_visual':
                    raise ValueError('invalid source or coordinate provenance')
                if abs(float(pos['latitude'])-coords[point_id]['latitude']) > 1e-9 or abs(float(pos['longitude'])-coords[point_id]['longitude']) > 1e-9:
                    raise ValueError('coordinate differs from frozen inventory')
                per_frame_sources[pos['sensor'], pos['frame_seq'], point_id] += 1
                if pos['track_id']:
                    track_sources[pos['track_id']].add(point_id)
            elif pos['latitude'] or pos['longitude']:
                raise ValueError('unconfirmed detection has geographic coordinates')
            counts[status] += 1
        if clip_id.startswith('paired_negative_'):
            early = [p for p in positions if float(p['pts_s']) < 19.8]
            counts['prelight_detection_candidates'] = len(early)
            counts['prelight_candidates_with_coordinate'] = sum(p['association_status'] == 'provisional_visual_lookup' for p in early)
        if any(value > 1 for value in per_frame_sources.values()):
            raise ValueError('one physical source assigned to multiple detections in one frame')
        if any(len(value) > 1 for value in track_sources.values()):
            raise ValueError('one track switched between physical sources')
        for task in queue['tasks']:
            if task['clip_id'] != clip_id:
                continue
            choice = decisions[task['task_id']]
            if choice['frame_status'] != 'usable':
                continue
            for sensor in ('V', 'T'):
                pts = float(task['visible_pts_s' if sensor == 'V' else 'thermal_pts_s'])
                frame_events = [e for e in events if e['sensor'] == sensor]
                nearest = min(frame_events, key=lambda e: abs(float(e['pts_s'])-pts))
                nearest_pts = float(nearest['pts_s'])
                if abs(nearest_pts-pts) > .11:
                    raise ValueError('reviewed image time not found: ' + task['task_id'])
                frame = [p for p in positions if p['sensor'] == sensor and int(p['frame_seq']) == nearest['frame_seq']]
                linked = [p for p in frame if p['association_status'] == 'provisional_visual_lookup']
                eligible = choice['source_state'] == 'active_fire' if sensor == 'V' else choice['source_state'] in ('active_fire', 'residual_heat')
                truth_points = choice[sensor]['points'] if eligible else []
                truth_sides = {side(p) for p in truth_points}
                covered = set()
                wrong = 0
                for p in linked:
                    predicted_side = next(k for k, v in SIDE_IDS.items() if v == p['point_id'])
                    distances = [math.hypot(float(p['image_x_normalized'])-float(t[0]),
                                            float(p['image_y_normalized'])-float(t[1]))
                                 for t in truth_points if side(t) == predicted_side]
                    if not distances or min(distances) > .14:
                        wrong += 1
                    else:
                        covered.add(predicted_side)
                record = {'task_id': task['task_id'], 'sensor': sensor, 'state': choice['source_state'],
                          'pts_s': nearest_pts, 'truth_sources': sorted(truth_sides),
                          'located_sources': sorted(covered), 'wrong_coordinate_count': wrong}
                rows.append(record)
                counts[sensor+'_truth_sources'] += len(truth_sides)
                counts[sensor+'_located_sources'] += len(covered)
                counts[sensor+'_wrong_coordinates_on_reviewed_frames'] += wrong
                if choice['source_state'] == 'hot_background':
                    counts[sensor+'_hot_background_reviewed_frames'] += 1
                    counts[sensor+'_hot_background_frames_with_coordinate'] += bool(linked)
        per_clip[clip_id] = {'run': str(run), 'manifest_sha256': sha(manifest_path),
                             'positions_sha256': sha(run / 'positions.csv'), 'counts': dict(counts)}
        totals.update(counts)
    output = {
        'schema_version': 'dji_b4_location_validation_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'scene_map_sha256': sha(scene_path),
        'truth_queue_sha256': sha(queue_path),
        'truth_decisions_sha256': sha(decisions_path),
        'reviewed_pair_count': len(rows)//2,
        'per_clip': per_clip, 'totals': dict(totals), 'reviewed_frame_rows': rows,
        'interpretation': 'Exploratory scene-specific image-point association. Coordinate output is a lookup of prior approximate visual points, not an independent geolocation prediction.',
    }
    path = root / 'realtime_v3' / 'B4_location_validation_v1.json'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(path), 'reviewed_pairs': output['reviewed_pair_count'],
                      'totals': output['totals']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
