#!/usr/bin/env python3
"""Create a unified image-plane localization observation table for B1-B4.

Per-frame video GPS/pose is unavailable in current inference artifacts, so
each unavailable parameter is explicit. LRF photo metadata remains separate.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
out = root / "localization/localization_observation_table_round22.jsonl"
manifest = root / "localization/localization_observation_table_round22_manifest.json"
if out.exists() or manifest.exists():
    raise SystemExit("output exists; refusing to overwrite")
sources = {
    "B1": (root / "association_round21_B1_provisional.json", root / "inference_round21_B1_provisional/observations.json"),
    "B2": (root / "association_round22_B2_provisional.json", root / "inference_round22_B2_provisional/observations.json"),
    "B3": (root / "association_round21_B3_provisional.json", root / "inference_round21_B3_provisional/observations.json"),
    "B4": (root / "association_round20_aligned_provisional.json", root / "inference_round20_aligned_provisional/observations.json"),
}
field_names = ("gps_lat", "gps_lon", "absolute_altitude", "relative_altitude", "aircraft_roll", "aircraft_pitch", "aircraft_yaw", "gimbal_roll", "gimbal_pitch", "gimbal_yaw", "rtk_status", "rtk_std", "lrf_distance", "lrf_lat", "lrf_lon", "lrf_alt")
counts = Counter()
with out.open("w", encoding="utf-8") as target:
    for batch, (association_path, inference_path) in sources.items():
        association = json.loads(association_path.read_text(encoding="utf-8"))
        inference = json.loads(inference_path.read_text(encoding="utf-8"))
        for observation in association["observations"]:
            for sensor, field, frame_field, time_field, size in (("T", "thermal_detection", "thermal_frame", "thermal_timestamp_s", (1280, 1024)), ("V", "visible_detection", "visible_frame", "visible_timestamp_s", (1920, 1080))):
                detection = observation[field]
                for index, box in enumerate(detection.get("boxes", [])):
                    x1, y1, x2, y2 = map(float, box)
                    center = [(x1+x2)/2, (y1+y2)/2]
                    row = {"observation_id": f"{observation['observation_id']}:{sensor}:{index}", "batch_id": batch, "session_id": observation["session_id"], "drone_id": observation["drone_id"], "video_group": observation["video_group"], "sensor": sensor, "timestamp_s": observation[time_field], "frame_index": observation[frame_field], "pixel_center": center, "normalized_center": [center[0]/size[0], center[1]/size[1]], "bbox_xyxy": box, "class_id": int(detection["class"][index]) if index < len(detection["class"]) else None, "confidence": float(detection["confidence"][index]) if index < len(detection["confidence"]) else None, "model_hash": inference["t_weights_sha256"] if sensor == "T" else inference["v_weights_sha256"], "metadata_reference": observation["metadata_reference"], "sync_delta_s": observation["sync_delta_s"], "association_status": observation["association_status"], "same_target_status": "unverified", "localization_mode": "image_plane_only", "quality_status": "provisional_detector", "parameter_source": {name: "unavailable" for name in field_names}, "absolute_fire_coordinate": "unavailable"}
                    row.update({name: "unavailable" for name in field_names})
                    target.write(json.dumps(row, ensure_ascii=False) + "\n")
                    counts[batch] += 1
manifest.write_text(json.dumps({"schema_version": "dji_localization_observation_table_round22_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "rows": sum(counts.values()), "by_batch": counts, "sources": {batch: {"association": str(a), "inference": str(i)} for batch, (a, i) in sources.items()}, "all_video_pose_fields": "unavailable", "photo_lrf_table": str(root / "localization/lrf_localization_observations_v1.json"), "absolute_localization": "unavailable", "interpretation": "Only image-plane detections and video times are joined here. DJI photo GPS/pose/LRF metadata is not interpolated onto video frames without a verified time and extrinsic transform."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"rows": sum(counts.values()), "by_batch": counts}, ensure_ascii=False))
