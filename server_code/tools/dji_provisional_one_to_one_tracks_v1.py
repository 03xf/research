#!/usr/bin/env python3
'''Conservative within-sensor track candidates from coarse DJI detections.'''
import argparse
import collections
import datetime
import hashlib
import json
import math
from pathlib import Path


def overlap(a, b):
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def track_stream(rows, stream_index, max_gap_s, max_center_delta):
    frames = collections.defaultdict(list)
    for row in rows:
        frames[(float(row['timestamp_s']), int(row['frame_index']))].append(row)
    active = {}
    tracks = {}
    links = []
    next_id = 1
    for (timestamp, frame_index), detections in sorted(frames.items()):
        active = {tid: previous for tid, previous in active.items()
                  if 0 < timestamp - previous['timestamp_s'] <= max_gap_s}
        candidates = []
        for tid, previous in active.items():
            for j, detection in enumerate(detections):
                if previous['class_id'] != detection['class_id']:
                    continue
                dx = detection['normalized_center'][0] - previous['normalized_center'][0]
                dy = detection['normalized_center'][1] - previous['normalized_center'][1]
                distance = math.hypot(dx, dy)
                if distance > max_center_delta:
                    continue
                iou = overlap(previous['bbox_xyxy'], detection['bbox_xyxy'])
                cost = 0.7 * distance / max_center_delta + 0.3 * (1.0 - iou)
                candidates.append((cost, distance, -iou, tid, j))
        used_tracks = set()
        used_detections = set()
        assignments = []
        for cost, distance, neg_iou, tid, j in sorted(candidates):
            if tid in used_tracks or j in used_detections:
                continue
            used_tracks.add(tid)
            used_detections.add(j)
            assignments.append((tid, j, distance, -neg_iou, cost))
        for tid, j, distance, iou, cost in assignments:
            detection = detections[j]
            previous = active[tid]
            tracks[tid]['observation_ids'].append(detection['observation_id'])
            tracks[tid]['timestamps_s'].append(timestamp)
            links.append({'track_id': tid,
                          'from_observation_id': previous['observation_id'],
                          'to_observation_id': detection['observation_id'],
                          'delta_s': timestamp - previous['timestamp_s'],
                          'normalized_center_delta': distance,
                          'bbox_iou': iou, 'assignment_cost': cost})
            active[tid] = detection
        for j, detection in enumerate(detections):
            if j in used_detections:
                continue
            tid = stream_index + ':' + str(next_id).zfill(5)
            next_id += 1
            tracks[tid] = {'track_id': tid, 'class_id': detection['class_id'],
                           'observation_ids': [detection['observation_id']],
                           'timestamps_s': [timestamp]}
            active[tid] = detection
    for item in tracks.values():
        item['duration_s'] = item['timestamps_s'][-1] - item['timestamps_s'][0]
        item['observation_count'] = len(item['observation_ids'])
        item['same_target_status'] = 'provisional_image_plane_candidate'
    return list(tracks.values()), links, len(frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-gap-s', type=float, default=20.0)
    parser.add_argument('--max-center-delta', type=float, default=0.15)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('refusing to overwrite output')
    streams = collections.defaultdict(list)
    skipped_reserved = 0
    source_rows = 0
    for line in args.source.open(encoding='utf-8'):
        row = json.loads(line)
        source_rows += 1
        if row['batch_id'] != 'B4':
            continue
        if row['session_id'] == 'DJI_202609081117_006':
            skipped_reserved += 1
            continue
        key = (row['session_id'], row['drone_id'], row['video_group'], row['sensor'])
        streams[key].append(row)
    all_tracks = []
    all_links = []
    frame_count = 0
    per_stream = []
    for i, (key, rows) in enumerate(sorted(streams.items()), 1):
        tracks, links, frames = track_stream(rows, 'B4_' + str(i).zfill(2), args.max_gap_s, args.max_center_delta)
        for track in tracks:
            track.update(dict(zip(('session_id', 'drone_id', 'video_group', 'sensor'), key)))
        for link in links:
            link.update(dict(zip(('session_id', 'drone_id', 'video_group', 'sensor'), key)))
        all_tracks.extend(tracks)
        all_links.extend(links)
        frame_count += frames
        per_stream.append({'session_id': key[0], 'drone_id': key[1], 'video_group': key[2],
                           'sensor': key[3], 'frame_count': frames, 'observation_count': len(rows),
                           'track_count': len(tracks), 'link_count': len(links)})
    counts = collections.Counter(obs for track in all_tracks for obs in track['observation_ids'])
    if any(value != 1 for value in counts.values()):
        raise SystemExit('observation assigned to multiple tracks')
    if len(all_links) != sum(len(track['observation_ids']) - 1 for track in all_tracks):
        raise SystemExit('link count invariant failed')
    payload = {'schema_version': 'dji_b4_one_to_one_provisional_tracks_v1',
               'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'source': str(args.source), 'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
               'source_row_count': source_rows, 'excluded_reserved_session': 'DJI_202609081117_006',
               'excluded_reserved_observations': skipped_reserved,
               'max_gap_s': args.max_gap_s, 'max_center_delta': args.max_center_delta,
               'stream_count': len(streams), 'frame_count': frame_count,
               'observation_count': len(counts), 'track_count': len(all_tracks),
               'multi_observation_track_count': sum(x['observation_count'] > 1 for x in all_tracks),
               'link_count': len(all_links),
               'assignment_rule': 'Greedy one-to-one same-class matching within each sensor/video using normalized center distance and same-sensor bbox IoU.',
               'quality_status': 'provisional_detector_coarse_10s_sampling',
               'same_target_verified': False, 'cross_sensor_association_verified': False,
               'absolute_position': 'unavailable',
               'limitations': ['Coarse detections can be false positives or fragments.',
                               'Nearest motion does not prove physical target identity.',
                               'No calibrated T/V pixel transform is available.',
                               'Gaps longer than max_gap_s start a new track.'],
               'per_stream': per_stream, 'tracks': all_tracks, 'links': all_links}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('stream_count', 'frame_count', 'observation_count', 'track_count', 'multi_observation_track_count', 'link_count', 'excluded_reserved_observations')}))


if __name__ == '__main__':
    main()
