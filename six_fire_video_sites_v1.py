"""Derive B1/B2 image-only site estimates; combine all six burning-video sites."""
from pathlib import Path
import csv
import json
import math

import numpy as np

ROOT = Path(r"D:\课题\_dji_preview")
LAT0, LON0 = 31.2895, 120.4727
GROUND_ALT_ASSUMED_M = 52.5

# Ground contact at the wood pile, not the top/centre of the flame.
# Each image is a separately positioned drone at the audit timestamp.
MARKS = {
    "B1_video_fire": {
        "batch": "b1", "time_local": "2026-09-07 16:03:00+08:00",
        "views": {"无人机02": (950, 890), "无人机08": (1000, 430), "无人机09": (970, 545)},
    },
    "B2_video_fire": {
        "batch": "b2", "time_local": "2026-09-08 09:25:00+08:00",
        "views": {"无人机01": (960, 875), "无人机06": (990, 785), "无人机07": (940, 810)},
    },
}


def to_enu(lat, lon):
    return np.array([(lon - LON0) * 95194.0, (lat - LAT0) * 111186.0])


def to_geo(point):
    return LAT0 + point[1] / 111186.0, LON0 + point[0] / 95194.0


def ground(row, xy):
    yaw, pitch = math.radians(float(row["gb_yaw"])), math.radians(float(row["gb_pitch"]))
    forward = np.array([math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch)])
    right = np.array([math.cos(yaw), -math.sin(yaw), 0.0])
    up = np.cross(right, forward)
    focal = 1280.0 * float(row["focal_len"]) / 24.0
    x, y = xy
    ray = forward + (x - 960.0) / focal * right - (y - 540.0) / focal * up
    camera = np.array([*to_enu(float(row["latitude"]), float(row["longitude"])), float(row["abs_alt"])])
    if ray[2] >= 0:
        raise ValueError(f"ray does not meet ground: {row['drone']}")
    return (camera + (GROUND_ALT_ASSUMED_M - camera[2]) / ray[2] * ray)[:2]


sites = []
for site_id, spec in MARKS.items():
    poses = {row["drone"].split("_")[0]: row for row in csv.DictReader((ROOT / f"{spec['batch']}_telemetry.csv").open(encoding="utf-8-sig"))}
    views = []
    points = []
    for drone, xy in spec["views"].items():
        pose = poses[drone]
        point = ground(pose, xy)
        points.append(point)
        lat, lon = to_geo(point)
        views.append({"drone": drone, "source_video": pose["file"], "source_frame": Path(pose["frame"]).name,
                      "x_px": xy[0], "y_px": xy[1], "latitude_estimate": lat, "longitude_estimate": lon})
    center = np.median(np.array(points), axis=0)
    lat, lon = to_geo(center)
    sites.append({"site_id": site_id, "batch_id": spec["batch"].upper(), "video_time_local": spec["time_local"],
                  "latitude_estimate": lat, "longitude_estimate": lon,
                  "max_horizontal_view_deviation_m": float(max(np.linalg.norm(point - center) for point in points)),
                  "ground_altitude_assumed_m": GROUND_ALT_ASSUMED_M,
                  "method": "manual_wood_pile_ground_contact_nominal_intrinsics_multiview_ground_plane",
                  "status": "provisional_visual_not_surveyed_truth", "views": views})

for site_id, batch, time, lat, lon, spread in [
    ("B3_video_north_fire", "B3", "2026-09-08 10:07:00+08:00", 31.2899036006, 120.4726785084, 2.26),
    ("B3_video_south_fire", "B3", "2026-09-08 10:07:00+08:00", 31.2896677352, 120.4727986134, 2.71),
    ("B4_video_east_near_road", "B4", "2026-09-08 10:54:10+08:00", 31.2887792678, 120.4727584031, 3.04),
    ("B4_video_west_near_tree", "B4", "2026-09-08 10:54:10+08:00", 31.2888262887, 120.4724890680, 3.06),
]:
    sites.append({"site_id": site_id, "batch_id": batch, "video_time_local": time,
                  "latitude_estimate": lat, "longitude_estimate": lon,
                  "max_horizontal_view_deviation_m": spread, "ground_altitude_assumed_m": GROUND_ALT_ASSUMED_M,
                  "method": "existing_nominal_intrinsics_multiview_ground_plane",
                  "status": "provisional_visual_not_surveyed_truth"})

out = ROOT / "six_fire_video_sites_v1.json"
out.write_text(json.dumps({"schema_version": "six_fire_video_sites_v1", "sites": sites,
                           "limitations": ["Image-only coordinates use nominal focal length and assumed ground elevation",
                                           "Six video sites are distinct batch-time targets; laser records have not been used to calculate them"]},
                          ensure_ascii=False, indent=2), encoding="utf-8")
for site in sites:
    print(site["site_id"], f"{site['latitude_estimate']:.10f}", f"{site['longitude_estimate']:.10f}", site["max_horizontal_view_deviation_m"])
