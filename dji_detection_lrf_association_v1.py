#!/usr/bin/env python3
"""Join provisional photo detections to LRF metadata without asserting identity."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/localization")
photos = root / "lrf_photo_detections_provisional_v1.json"
groups = root / "lrf_capture_groups_round12.json"
output = root / "detection_lrf_association_v1.json"
if output.exists():
    raise SystemExit("output exists; refusing to overwrite")
photo_rows = json.loads(photos.read_text(encoding="utf-8"))["observations"]
group_rows = json.loads(groups.read_text(encoding="utf-8"))["capture_groups"]
refs = {(g["session_id"], g["capture_key"], sensor): g["lrf_reference_by_sensor"].get(sensor) for g in group_rows for sensor in ("T", "V")}
rows = []
for row in photo_rows:
    key = (row["session_id"], row["capture_key"], row["sensor"])
    reference = refs.get(key)
    detections = row.get("detections", [])
    rows.append({"observation_id": row["observation_id"], "batch_id": "B4", "session_id": row["session_id"], "drone_id": row["drone_id"], "capture_key": row["capture_key"], "sensor": row["sensor"], "source_image": row["source_image"], "detection_count": len(detections), "detections": detections, "lrf_reference": reference, "same_target_status": "unverified" if detections and reference else ("reference_only" if reference else "missing_reference"), "pixel_offset_px": "unavailable", "absolute_fire_coordinate": "unavailable", "localization_mode": "image_plane_plus_independent_lrf_reference"})
batch = defaultdict(lambda: {"photos": 0, "images_with_detections": 0, "detection_count": 0, "reference_only": 0, "detections_with_unverified_lrf": 0})
for row in rows:
    s = batch[row["sensor"]]
    s["photos"] += 1
    s["detection_count"] += row["detection_count"]
    if row["detection_count"]:
        s["images_with_detections"] += 1
        s["detections_with_unverified_lrf"] += row["detection_count"]
    elif row["lrf_reference"]:
        s["reference_only"] += 1
payload = {"schema_version": "dji_detection_lrf_association_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "photo_detection_source": str(photos), "lrf_group_source": str(groups), "provisional_detector": True, "same_target_rule": "unverified unless independently confirmed by visual/temporal evidence", "summary": {"row_count": len(rows), "detection_count": sum(x["detection_count"] for x in rows), "by_sensor": batch, "absolute_localization": "unavailable"}, "observations": rows, "interpretation": "LRF coordinates remain independent spatial references; they are not replaced by detection centers or reported as fire coordinates."}
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload["summary"], ensure_ascii=False))
