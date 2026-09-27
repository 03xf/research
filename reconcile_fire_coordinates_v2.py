"""Reconcile existing LRF reference points with B4 burning-video sites.

This script is intentionally conservative: visual ray estimates are never
written into the LRF truth table or labeled as independent surveyed truth.
"""
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import math
import shutil
import statistics

import numpy as np

DATA = Path('/home/member/xmy/data/dataset_analysis')
SOURCE_SCRIPT = Path('/home/member/xmy/data/分析脚本/calculate_fixed_fire_points.py')
AUDIT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1/b4_f2_audit')
OUT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/localization_v2')
OUT.mkdir(parents=True, exist_ok=True)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def snapshot(path):
    dest = OUT / 'inputs' / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if sha(path) != sha(dest):
            raise RuntimeError(f'Frozen input changed: {dest}')
    else:
        shutil.copy2(path, dest)
    return {'source': str(path), 'snapshot': str(dest), 'sha256': sha(dest)}

source_paths = [DATA / 'fixed_fire_points.csv', DATA / 'fixed_fire_observations.csv',
                DATA / 'fixed_fire_point_summary.json', AUDIT / 'b4_105410_telemetry.csv']
snapshots = [snapshot(p) for p in source_paths]
spec = importlib.util.spec_from_file_location('fixedfire', SOURCE_SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source_hash = sha(SOURCE_SCRIPT)

with (OUT / 'inputs' / 'fixed_fire_point_summary.json').open(encoding='utf-8') as f:
    prior_summary = json.load(f)
origin_record = prior_summary['origin']
origin = (origin_record['latitude'], origin_record['longitude'], origin_record['altitude'])
origin_ecef = module.geodetic_to_ecef(*origin)

with (OUT / 'inputs' / 'fixed_fire_observations.csv').open(encoding='utf-8-sig', newline='') as f:
    obs = list(csv.DictReader(f))
with (OUT / 'inputs' / 'fixed_fire_points.csv').open(encoding='utf-8-sig', newline='') as f:
    prior_points = {(r['batch_id'], r['fire_id']): r for r in csv.DictReader(f)}

grouped = defaultdict(list)
for row in obs:
    if row['target_match_status'] == 'accepted':
        grouped[(row['batch_id'], row['fire_id'], row['observation_id'])].append(row)

events = []
for (batch, fire, event_id), rows in sorted(grouped.items()):
    chosen = next((r for r in rows if r['channel'] == 'InfraredCamera'), rows[0])
    lat = float(chosen['LRFTargetLat'])
    lon = float(chosen['LRFTargetLon'])
    alt = float(chosen['LRFTargetAlt'])
    enu = module.ecef_to_enu(module.geodetic_to_ecef(lat, lon, alt), origin, origin_ecef)
    events.append({'batch_id': batch, 'fire_id': fire, 'event_id': event_id,
                   'image_count': len(rows), 'chosen_image': chosen['name'],
                   'latitude': lat, 'longitude': lon, 'target_alt_original_datum': alt,
                   'east_m': enu[0], 'north_m': enu[1], 'up_m': enu[2]})

ref_rows = []
for key in sorted({(e['batch_id'], e['fire_id']) for e in events}):
    members = [e for e in events if (e['batch_id'], e['fire_id']) == key]
    med = tuple(statistics.median(e[k] for e in members) for k in ('east_m', 'north_m', 'up_m'))
    lat, lon, alt = module.ecef_to_geodetic(*module.enu_to_ecef(med, origin, origin_ecef))
    old = prior_points[key]
    old_horiz = module.distance_2d((lat, lon), (float(old['fire_latitude']), float(old['fire_longitude'])))
    max_spread = max((math.hypot(e['east_m'] - med[0], e['north_m'] - med[1]) for e in members), default=0)
    ref_rows.append({'point_id': f'{key[0]}_{key[1]}_LRF', 'batch_id': key[0], 'fire_id': key[1],
                     'latitude': lat, 'longitude': lon, 'target_alt_original_datum': alt,
                     'independent_events': len(members), 'photo_rows': sum(e['image_count'] for e in members),
                     'max_horizontal_event_deviation_m': max_spread,
                     'old_to_event_center_horizontal_m': old_horiz,
                     'source': 'XMP_LRFTarget_event_median',
                     'scope': 'prefire_reference' if key == ('B2', 'F1') else 'LRF_impact_reference',
                     'physical_match_to_burning_video': 'unverified'})

with (OUT / 'inputs' / 'b4_105410_telemetry.csv').open(encoding='utf-8', newline='') as f:
    telemetry = {r['drone'].split('_')[0]: r for r in csv.DictReader(f)}

B4_REF = next(r for r in ref_rows if r['point_id'] == 'B4_F1_LRF')
LAT0, LON0 = B4_REF['latitude'], B4_REF['longitude']
EAST_PER_DEG, NORTH_PER_DEG = 95194.0, 111186.0

def basis(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    forward = np.array([math.cos(p) * math.sin(y), math.cos(p) * math.cos(y), math.sin(p)])
    right = np.array([math.cos(y), -math.sin(y), 0.0])
    up = np.cross(right, forward)
    return forward, right, up

def ray(drone, x, y):
    rec = telemetry[drone]
    c = np.array([(float(rec['longitude']) - LON0) * EAST_PER_DEG,
                  (float(rec['latitude']) - LAT0) * NORTH_PER_DEG,
                  float(rec['abs_alt'])])
    forward, right, up = basis(float(rec['gb_yaw']), float(rec['gb_pitch']))
    fx = 1280.0 * float(rec['focal_len']) / 24.0  # nominal 35-mm equivalent video focal length
    direction = forward + (x - 960.0) / fx * right - (y - 540.0) / fx * up
    return c, direction / np.linalg.norm(direction)

def ground_point(c, direction, z):
    return c + (z - c[2]) / direction[2] * direction

marks = [
    ('B4_video_east_near_road', '无人机08', 1510, 360),
    ('B4_video_east_near_road', '无人机09', 1640, 395),
    ('B4_video_east_near_road', '无人机02', 250, 225),
    ('B4_video_west_near_tree', '无人机08', 170, 815),
    ('B4_video_west_near_tree', '无人机09', 420, 855),
    ('B4_video_west_near_tree', '无人机02', 1670, 745),
]
mark_rows = []
site_rows = []
for target in sorted({x[0] for x in marks}):
    rays, points = [], []
    for _, drone, x, y in [m for m in marks if m[0] == target]:
        c, direction = ray(drone, x, y)
        ground = ground_point(c, direction, 52.5)
        rays.append((c, direction))
        points.append(ground)
        mark_rows.append({'point_id': target, 'drone': drone, 'session': telemetry[drone]['session'],
                          'source_mp4': telemetry[drone]['file'], 'offset_s': telemetry[drone]['offset_s'],
                          'source_pixel_x': x, 'source_pixel_y': y,
                          'camera_latitude': telemetry[drone]['latitude'],
                          'camera_longitude': telemetry[drone]['longitude'],
                          'camera_abs_alt': telemetry[drone]['abs_alt'],
                          'gimbal_yaw': telemetry[drone]['gb_yaw'],
                          'gimbal_pitch': telemetry[drone]['gb_pitch'],
                          'nominal_focal_length_35mm': telemetry[drone]['focal_len'],
                          'ground_intersection_east_m': float(ground[0]),
                          'ground_intersection_north_m': float(ground[1])})
    A = np.zeros((3, 3))
    b = np.zeros(3)
    for c, direction in rays:
        projector = np.eye(3) - np.outer(direction, direction)
        A += projector
        b += projector @ c
    tri = np.linalg.solve(A, b)
    residual = [float(np.linalg.norm(np.cross(tri - c, d))) for c, d in rays]
    ground_xy = np.median(np.array(points)[:, :2], axis=0)
    spread = max(np.linalg.norm(a[:2] - b[:2]) for a, b in combinations(points, 2))
    site_rows.append({'point_id': target, 'latitude_estimate': LAT0 + ground_xy[1] / NORTH_PER_DEG,
                      'longitude_estimate': LON0 + ground_xy[0] / EAST_PER_DEG,
                      'triangulated_latitude_diagnostic': LAT0 + tri[1] / NORTH_PER_DEG,
                      'triangulated_longitude_diagnostic': LON0 + tri[0] / EAST_PER_DEG,
                      'triangulated_abs_alt_diagnostic_unverified_datum': float(tri[2]),
                      'camera_views': len(rays), 'ground_plane_abs_alt_assumption': 52.5,
                      'cross_view_horizontal_spread_m': float(spread),
                      'ray_residuals_m': residual,
                      'distance_to_B4_LRF_F1_m': float(np.linalg.norm(ground_xy)),
                      'source': 'nominal_camera_multiview_video_estimate',
                      'status': 'provisional_not_ground_truth',
                      'matched_lrf_point_id': None})

def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

write_csv(OUT / 'lrf_reference_events.csv', events)
write_csv(OUT / 'lrf_reference_event_centers.csv', ref_rows)
write_csv(OUT / 'b4_video_source_marks.csv', mark_rows)
write_csv(OUT / 'b4_video_site_estimates.csv', site_rows)

report = {'schema_version': 'dji_fire_coordinate_reconciliation_v2',
          'generated_utc': datetime.now(timezone.utc).isoformat(),
          'source_snapshots': snapshots,
          'coordinate_calculation_script_sha256': source_hash,
          'lrf_event_centers': ref_rows,
          'video_site_estimates': site_rows,
          'b4_legacy_f2_lrf_coordinate': None,
          'b4_lrf_video_identity_status': 'unmatched; video flames lie about 78 m from the B4 LRF center',
          'method_limits': [
              'LRF centers describe impact-location repeatability; ground burning-source identity is not independently established.',
              'B2_F1 is a prefire fuel pile.',
              'B3_F1 has one independent LRF event despite two photo rows.',
              'Video site estimates use nominal focal length, logged GPS/gimbal pose and a 52.5 m ground-plane assumption; no Matrice 4T calibration is available.',
              'Cross-view spread measures internal consistency, not absolute accuracy.',
              'B4 video site labels are geographic descriptors; they are not forced into the old B4 F1/F2 labels.',
              'LRFTargetAlt and video abs_alt have unverified datum compatibility; do not merge or report a validated absolute height.',
          ]}
with (OUT / 'coordinate_reconciliation_v2.json').open('w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps({'lrf_centers': len(ref_rows), 'lrf_events': len(events), 'video_sites': len(site_rows),
                  'out': str(OUT)}, ensure_ascii=False))
