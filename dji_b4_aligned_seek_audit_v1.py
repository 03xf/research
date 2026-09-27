#!/usr/bin/env python3
"""Spot-check OpenCV seeks for a predicted B4 T/V frame schedule."""
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import cv2

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
source = root / "b4_aligned_frame_schedule_v1.json"
output = root / "b4_aligned_seek_audit_v1.json"
if output.exists():
    raise SystemExit("output exists; refusing to overwrite")
schedule = json.loads(source.read_text(encoding="utf-8"))
rows = []
for group in schedule["groups"]:
    samples = group["matches"]
    if not samples:
        continue
    selected = [samples[i] for i in sorted({0, len(samples) // 2, len(samples) - 1})]
    captures = {sensor: cv2.VideoCapture(group[f"{sensor}_source"]) for sensor in ("thermal", "visible")}
    for match in selected:
        row = {"pair_key": group["pair_key"], "sample_index": match["sample_index"], "predicted_sync_delta_s": match["predicted_sync_delta_s"]}
        for sensor in ("thermal", "visible"):
            cap = captures[sensor]
            frame_index = match[f"{sensor}_frame"]
            ok = cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            decoded, frame = cap.read()
            row[f"{sensor}_read_ok"] = bool(ok and decoded and frame is not None)
            row[f"{sensor}_requested_frame"] = frame_index
            row[f"{sensor}_reported_pos_frames"] = cap.get(cv2.CAP_PROP_POS_FRAMES)
            row[f"{sensor}_reported_pos_msec"] = cap.get(cv2.CAP_PROP_POS_MSEC)
            row[f"{sensor}_expected_pos_msec"] = 1000 * frame_index / group[f"{sensor}_fps"]
        if row["thermal_read_ok"] and row["visible_read_ok"]:
            row["reported_sync_delta_s"] = abs(row["thermal_reported_pos_msec"] - row["visible_reported_pos_msec"]) / 1000
        else:
            row["reported_sync_delta_s"] = None
        rows.append(row)
    for cap in captures.values():
        cap.release()

deltas = [x["reported_sync_delta_s"] for x in rows if x["reported_sync_delta_s"] is not None]
summary = {"video_groups": len(schedule["groups"]), "sampled_pairs": len(rows), "read_success_pairs": len(deltas), "reported_median_delta_s": statistics.median(deltas) if deltas else None, "reported_max_delta_s": max(deltas) if deltas else None, "reported_over_50ms": sum(x > .05 for x in deltas), "reported_over_100ms": sum(x > .1 for x in deltas)}
doc = {"schema_version": "dji_b4_aligned_seek_audit_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "schedule": str(source), "summary": summary, "rows": rows, "interpretation": "OpenCV-reported seek timestamps are a spot check, not a substitute for exhaustive decoded packet PTS validation. No cross-camera spatial association is inferred."}
output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
