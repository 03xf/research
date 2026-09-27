"""Reference-assisted per-frame ground projection for one audited B2 camera view.

The LRF site anchors each sensor once. Subsequent V flame and T hotspot boxes
produce changing, provisional ground positions from their own frame telemetry.
This is not an independently calibrated absolute geolocation.
"""
import bisect
import json
import math
import re
import subprocess
from pathlib import Path


FIELDS = ('latitude', 'longitude', 'abs_alt', 'gb_yaw', 'gb_pitch', 'focal_len')
LAT_M = 111186.0
LON_M = 95194.0


def _seconds(stamp):
    h, m, s = stamp.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def extract_telemetry(scene, output, start_s=20.0, end_s=60.0):
    result = {'schema_version': 'b2_frame_telemetry_v1', 'sources': {}}
    for sensor in ('V', 'T'):
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-copyts', '-ss', str(start_s),
                   '-i', scene['visible_video' if sensor == 'V' else 'thermal_video'],
                   '-t', str(end_s), '-map', '0:s:0', '-f', 'srt', '-']
        raw = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                             errors='replace', check=True).stdout
        rows = []
        for block in re.split(r'\n\s*\n', raw):
            match = re.search(r'(\d\d:\d\d:\d\d,\d+)\s+-->', block)
            if not match:
                continue
            row = {'pts_s': _seconds(match.group(1))}
            for key in FIELDS:
                value = re.search(r'\b' + key + r':\s*([-+\d.]+)', block)
                if value:
                    row[key] = float(value.group(1))
            if all(key in row for key in FIELDS):
                rows.append(row)
        if not rows:
            raise ValueError('no complete subtitle telemetry for ' + sensor)
        result['sources'][sensor] = rows
    output.write_text(json.dumps(result, ensure_ascii=False) + '\n', encoding='utf-8')
    return result


def _project(row, pixel, size, ground_alt_m, ref_lat, ref_lon):
    yaw, pitch = math.radians(row['gb_yaw']), math.radians(row['gb_pitch'])
    forward = (math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch))
    right = (math.cos(yaw), -math.sin(yaw), 0.0)
    up = (right[1] * forward[2] - right[2] * forward[1],
          right[2] * forward[0] - right[0] * forward[2],
          right[0] * forward[1] - right[1] * forward[0])
    focal_px = 1280.0 * row['focal_len'] / 24.0  # nominal equivalent, consistent with prior project work
    dx = (pixel[0] - 0.5) * size[0] / focal_px
    dy = (pixel[1] - 0.5) * size[1] / focal_px
    ray = tuple(forward[i] + dx * right[i] - dy * up[i] for i in range(3))
    if ray[2] >= -0.01:
        raise ValueError('ray does not intersect assumed ground plane')
    travel = (ground_alt_m - row['abs_alt']) / ray[2]
    east = (row['longitude'] - ref_lon) * LON_M + travel * ray[0]
    north = (row['latitude'] - ref_lat) * LAT_M + travel * ray[1]
    return east, north


class RelativeLocator:
    def __init__(self, scene, telemetry):
        spec = scene['dynamic_location']
        source = scene['sources'][0]
        self.point_id = source['point_id']
        self.latitude = source['latitude']
        self.longitude = source['longitude']
        self.ground_alt_m = spec['assumed_ground_alt_m']
        self.calibration = spec['calibration']
        self.rows = telemetry['sources']
        self.times = {s: [r['pts_s'] for r in self.rows[s]] for s in ('V', 'T')}
        self.reference_offset = {}
        for sensor in ('V', 'T'):
            cal = self.calibration[sensor]
            pose, delta = self.pose(sensor, cal['pts_s'])
            if delta > 0.15:
                raise ValueError('calibration pose is too far from reference frame')
            self.reference_offset[sensor] = _project(pose, cal['point_normalized'],
                cal['image_size_px'], self.ground_alt_m, self.latitude, self.longitude)

    def pose(self, sensor, pts_s):
        times = self.times[sensor]
        index = bisect.bisect_left(times, pts_s)
        options = [i for i in (index - 1, index) if 0 <= i < len(times)]
        nearest = min(options, key=lambda i: abs(times[i] - pts_s))
        return self.rows[sensor][nearest], abs(times[nearest] - pts_s)

    def locate(self, event):
        sensor, size = event['sensor'], event['image_size_px']
        pose, delta = self.pose(sensor, event['pts_s'])
        if delta > 0.15:
            return []
        estimates = []
        for position in event['positions']:
            if position['point_id'] != self.point_id or position['association_status'] not in (
                    'lrf_reference_lookup', 'thermal_candidate_only'):
                continue
            det = event['raw_detections'][position['detection_index']]
            x1, y1, x2, y2 = det['bbox_xyxy_px']
            # Both sensors use the lower middle of the detected region as a ground-contact proxy.
            point = [((x1 + x2) / 2) / size[0], y2 / size[1]]
            east, north = _project(pose, point, size, self.ground_alt_m, self.latitude, self.longitude)
            ref_east, ref_north = self.reference_offset[sensor]
            east -= ref_east
            north -= ref_north
            estimate = {
                'sensor': sensor, 'frame_seq': event['frame_seq'], 'pts_s': event['pts_s'],
                'point_id': self.point_id, 'track_id': position['track_id'],
                'association_status': position['association_status'], 'confidence': position['confidence'],
                'image_x_normalized': point[0], 'image_y_normalized': point[1],
                'estimated_latitude': self.latitude + north / LAT_M,
                'estimated_longitude': self.longitude + east / LON_M,
                'offset_east_m': east, 'offset_north_m': north,
                'offset_from_lrf_m': math.hypot(east, north),
                'reference_latitude': self.latitude, 'reference_longitude': self.longitude,
                'pose_delta_s': delta,
                'estimate_kind': 'V_flame_ground_proxy' if sensor == 'V' else 'T_hotspot_ground_proxy',
                'method': 'per_frame_subtitle_pose_nominal_ray_ground_LRF_one_point_correction',
            }
            position['dynamic_estimate'] = estimate
            det['position']['dynamic_estimate'] = estimate
            estimates.append(estimate)
        event['dynamic_estimates'] = estimates
        return estimates


if __name__ == '__main__':
    import argparse
    import csv
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--results', type=Path)
    parser.add_argument('--estimate-csv', type=Path)
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text(encoding='utf-8'))
    result = extract_telemetry(scene, args.output)
    summary = {s: len(result['sources'][s]) for s in ('V', 'T')}
    if args.results:
        if not args.estimate_csv:
            parser.error('--estimate-csv is required with --results')
        locator = RelativeLocator(scene, result)
        estimates = []
        for line in args.results.open(encoding='utf-8'):
            estimates.extend(locator.locate(json.loads(line)))
        with args.estimate_csv.open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(estimates[0]))
            writer.writeheader()
            writer.writerows(estimates)
        summary['estimate_counts'] = {s: sum(e['sensor'] == s for e in estimates) for s in ('V', 'T')}
        summary['offset_range_m'] = {s: [round(min(e['offset_from_lrf_m'] for e in estimates if e['sensor'] == s), 3),
                                         round(max(e['offset_from_lrf_m'] for e in estimates if e['sensor'] == s), 3)]
                                     for s in ('V', 'T')}
    print(json.dumps(summary))
