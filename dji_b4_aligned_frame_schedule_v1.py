#!/usr/bin/env python3
"""Plan T/V frame-index pairs on a shared video time axis, without inference."""
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
sync_path = Path("/home/member/xmy/xmy/results/dji_all_batches/sync/B4.json")
output = root / "b4_aligned_frame_schedule_v1.json"
if output.exists():
    raise SystemExit("output exists; refusing to overwrite")
pairs = json.loads(sync_path.read_text(encoding="utf-8"))["pairs"]


def fps(info):
    a, b = info["fps"].split("/")
    return float(a) / float(b)


groups = []
all_delta = []
for pair in pairs:
    thermal, visible = pair["T_info"], pair["V_info"]
    t_fps, v_fps = fps(thermal), fps(visible)
    t_start, v_start = float(thermal["start_s"]), float(visible["start_s"])
    t_total, v_total = int(thermal["frames"]), int(visible["frames"])
    matches = []
    # Match the same thermal samples used by the strided baseline, but seek
    # visible frames by timestamp instead of reusing the sample index.
    for sample_index, thermal_frame in enumerate(range(299, t_total, 300)):
        timestamp = t_start + thermal_frame / t_fps
        visible_frame = round((timestamp - v_start) * v_fps)
        if not 0 <= visible_frame < v_total:
            continue
        visible_time = v_start + visible_frame / v_fps
        delta = abs(visible_time - timestamp)
        all_delta.append(delta)
        matches.append({"sample_index": sample_index, "thermal_frame": thermal_frame, "visible_frame": visible_frame, "thermal_timestamp_s": timestamp, "visible_timestamp_s": visible_time, "predicted_sync_delta_s": delta})
    groups.append({"pair_key": pair["pair_key"], "thermal_source": pair["T"], "visible_source": pair["V"], "thermal_fps": t_fps, "visible_fps": v_fps, "matched_count": len(matches), "max_predicted_delta_s": max((x["predicted_sync_delta_s"] for x in matches), default=None), "matches": matches})

summary = {"video_groups": len(groups), "planned_frame_pairs": len(all_delta), "predicted_median_delta_s": statistics.median(all_delta) if all_delta else None, "predicted_p95_delta_s": sorted(all_delta)[math.ceil(0.95 * len(all_delta)) - 1] if all_delta else None, "predicted_max_delta_s": max(all_delta) if all_delta else None, "pairs_over_50ms": sum(x > 0.05 for x in all_delta), "pairs_over_100ms": sum(x > 0.1 for x in all_delta)}
doc = {"schema_version": "dji_b4_aligned_frame_schedule_v1", "created_utc": datetime.now(timezone.utc).isoformat(), "sync_source": str(sync_path), "summary": summary, "frame_rule": "T frames 299+300*k to match original Ultralytics stride; V frame = round((T start + T frame / T fps - V start) * V fps)", "time_basis": "constant-fps sync audit; predicted deltas must be checked against decoded video PTS before final T/V association", "spatial_correspondence": "unverified", "model_gate": "failed; this is a sampling schedule only, not fire detections", "groups": groups}
output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
