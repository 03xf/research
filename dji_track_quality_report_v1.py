#!/usr/bin/env python3
"""Summarize provisional image-plane tracks without treating them as fire truth."""
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
sources = {
    "B1": root / "tracking_round21_B1_provisional.json",
    "B2": root / "tracking_round22_B2_provisional.json",
    "B3": root / "tracking_round21_B3_provisional.json",
    "B4": root / "tracking_round20_aligned_provisional.json",
}
target = root / "track_quality_round22_provisional.json"
if target.exists():
    raise SystemExit("output exists; refusing to overwrite")


def p95(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


reports = {}
for batch, path in sources.items():
    data = json.loads(path.read_text(encoding="utf-8"))
    track_points = defaultdict(list)
    for point in data["image_plane_points"]:
        track_points[point["track_id"]].append(point)
    sensor_reports = {}
    for sensor in ("T", "V"):
        tracks = {key: sorted(points, key=lambda x: x["timestamp_s"]) for key, points in track_points.items() if points[0]["sensor"] == sensor}
        lengths = [len(points) for points in tracks.values()]
        step_px = []
        normalized_step = []
        for points in tracks.values():
            for a, b in zip(points, points[1:]):
                step_px.append(math.dist(a["pixel_center"], b["pixel_center"]))
                normalized_step.append(math.dist(a["normalized_center"], b["normalized_center"]))
        sensor_reports[sensor] = {"track_count": len(tracks), "multi_observation_track_count": sum(length > 1 for length in lengths), "median_observations_per_track": statistics.median(lengths) if lengths else None, "median_track_step_px": statistics.median(step_px) if step_px else None, "p95_track_step_px": p95(step_px), "median_normalized_step": statistics.median(normalized_step) if normalized_step else None, "p95_normalized_step": p95(normalized_step), "localization_mode": "image_plane_only"}
    reports[batch] = {"source": str(path), "sensor_metrics": sensor_reports, "semantics": "B2 pre-fire/hotspot candidate only" if batch == "B2" else "provisional detector tracks, not verified fire-event tracks"}
payload = {"schema_version": "dji_track_quality_round22_provisional_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "batches": reports, "cross_sensor_track_consistency": "unavailable", "absolute_position_jitter": "unavailable", "interpretation": "Center-step metrics reflect movement, view changes, 10-second sampling and association errors; they are not pure localization noise or physically measured distances."}
target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({batch: report["sensor_metrics"] for batch, report in reports.items()}, ensure_ascii=False))
