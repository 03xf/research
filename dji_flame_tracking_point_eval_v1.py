"""Track frozen single-class flame candidate on the existing 50-point clips."""
import argparse
import collections
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dji_source_truth_eval_v2 import matched
from recovery_v1_evaluate import digest, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--freeze', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--tracker', type=Path, required=True)
    ap.add_argument('--device', default='0')
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = args.root.resolve()
    queue_path = root / 'source_truth_review_v1' / 'queue.json'
    decisions_path = root / 'source_truth_review_v1' / 'decisions.json'
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    decisions = json.loads(decisions_path.read_text(encoding='utf-8'))['decisions']
    freeze = json.loads(args.freeze.read_text(encoding='utf-8'))
    evaluation = json.loads(Path(freeze['development_result']).read_text(encoding='utf-8'))
    weights = Path(freeze['weights'])
    if (digest(weights) != freeze['weights_sha256'] or
            evaluation['weights_sha256'] != freeze['weights_sha256'] or
            evaluation['classes'][0]['work_threshold'] != freeze['threshold'] or
            len(queue['tasks']) != 50 or set(decisions) != {x['task_id'] for x in queue['tasks']}):
        raise ValueError('frozen model or 50-point cohort mismatch')
    sys.path.insert(0, '/home/member/xmy/xmy/code/projects/ultralytics')
    import cv2
    import recovery_v1_track_clips_v2 as track
    track.CLASS_NAMES['V'] = ('flame',)
    args.output.mkdir(parents=True)
    summaries = {}
    track_rows = {}
    for clip in queue['clips']:
        clip_id = clip['clip_id']
        clip_path = root / 'video_clips' / clip_id
        output = args.output / clip_id / 'V'
        started = time.monotonic()
        summary = track.run_sensor(clip_path, 'V', weights, evaluation, output,
                                   960, args.device, args.tracker)
        elapsed = time.monotonic() - started
        summaries[clip_id] = {**summary, 'processing_seconds': elapsed,
                              'processing_fps': summary['frames'] / elapsed}
        track_rows[clip_id] = {x['frame_file']: x for x in json.loads(
            (output / 'detections.json').read_text(encoding='utf-8'))['rows']}
    totals = collections.Counter()
    by_batch = collections.defaultdict(collections.Counter)
    by_clip = collections.defaultdict(collections.Counter)
    rows = []
    for task in queue['tasks']:
        choice = decisions[task['task_id']]
        if choice['frame_status'] != 'usable':
            continue
        clip_id = task['clip_id']
        frame = Path(task['visible_frame'])
        data = track_rows[clip_id].get(frame.name)
        if data is None:
            raise ValueError('review frame not found in tracked clip: ' + str(frame))
        image = cv2.imread(str(frame))
        if image is None:
            raise ValueError('review frame unreadable: ' + str(frame))
        height, width = image.shape[:2]
        detections = [x for x in data['detections'] if x['class_name'] == 'flame']
        eligible = choice['source_state'] == 'active_fire'
        points = choice['V']['points'] if eligible else []
        pairs = matched(points, detections, width, height)
        batch = next(c['source']['batch_id'] for c in queue['clips'] if c['clip_id'] == clip_id)
        row = {'task_id': task['task_id'], 'clip_id': clip_id, 'batch': batch,
               'source_state': choice['source_state'],
               'eligible_truth_points': len(points), 'matched_points': len(pairs),
               'missed_points': len(points) - len(pairs),
               'detections': len(detections),
               'negative_frame_with_detection': int(not points and bool(detections))}
        rows.append(row)
        for counter in (totals, by_batch[batch], by_clip[clip_id]):
            counter['truth'] += len(points)
            counter['matched'] += len(pairs)
            counter['missed'] += len(points) - len(pairs)
            counter['detections'] += len(detections)
            counter['negative_frame_with_detection'] += row['negative_frame_with_detection']
    if totals['truth'] != 52 or by_batch['B4']['truth'] != 32:
        raise ValueError('point truth support changed')
    write_json(args.output / 'result.json', {
        'schema_version': 'dji_single_flame_tracking_point_eval_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'exploratory_historically_exposed': True,
        'baseline_E2_tracked': {'B4': '18/32', 'overall': '33/52'},
        'method': 'same ByteTrack and point-inside-box greedy one-to-one logic as E2; active-fire V points only',
        'candidate_freeze_sha256': digest(args.freeze),
        'truth_queue_sha256': digest(queue_path),
        'truth_decisions_sha256': digest(decisions_path),
        'tracker_sha256': digest(args.tracker),
        'totals': dict(totals),
        'by_batch': {k: dict(v) for k, v in by_batch.items()},
        'by_clip': {k: dict(v) for k, v in by_clip.items()},
        'tracking': summaries, 'rows': rows})
    print(json.dumps({'totals': dict(totals), 'B4': dict(by_batch['B4']),
                      'minimum_processing_fps': min(x['processing_fps'] for x in summaries.values())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
