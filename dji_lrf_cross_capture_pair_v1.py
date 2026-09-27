#!/usr/bin/env python3
"""Find conservative T/V LRF metadata pairs across adjacent photo capture keys.

These are laser-coordinate consistency candidates, not fire-target truth.
"""
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/localization")
source = root / "lrf_capture_groups_round12.json"
target = root / "lrf_cross_capture_tv_pairs_v1.json"
if target.exists():
    raise SystemExit("output exists; refusing to overwrite")
data = json.loads(source.read_text(encoding="utf-8"))
groups = data["capture_groups"]


def when(key):
    return datetime.strptime(key.split("_")[1], "%Y%m%d%H%M%S")


def meters(a, b):
    lat1, lat2 = map(math.radians, (a["latitude"], b["latitude"]))
    dlat = lat2 - lat1
    dlon = math.radians(b["longitude"] - a["longitude"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    horizontal = 2 * 6371008.8 * math.asin(min(1, math.sqrt(h)))
    altitude = b["altitude"] - a["altitude"]
    return horizontal, math.hypot(horizontal, altitude)


same_capture = []
singletons = []
for group in groups:
    refs = group["lrf_reference_by_sensor"]
    if "T" in refs and "V" in refs:
        horizontal, three_d = meters(refs["T"], refs["V"])
        same_capture.append({"batch_id": group["batch_id"], "session_id": group["session_id"], "capture_key": group["capture_key"], "delta_horizontal_m": horizontal, "delta_3d_m": three_d, "target_identity": "unverified"})
    elif len(group["sensors"]) == 1:
        singletons.append(group)

possible = []
for thermal in singletons:
    if thermal["sensors"] != ["T"]:
        continue
    for visible in singletons:
        if visible["sensors"] != ["V"] or thermal["batch_id"] != visible["batch_id"] or thermal["session_id"] != visible["session_id"] or thermal["drone_id"] != visible["drone_id"]:
            continue
        dt = abs((when(thermal["capture_key"]) - when(visible["capture_key"])).total_seconds())
        if dt > 2:
            continue
        horizontal, three_d = meters(thermal["lrf_reference_by_sensor"]["T"], visible["lrf_reference_by_sensor"]["V"])
        if three_d > 0.5:
            continue
        possible.append({"batch_id": thermal["batch_id"], "session_id": thermal["session_id"], "drone_id": thermal["drone_id"], "thermal_capture_key": thermal["capture_key"], "visible_capture_key": visible["capture_key"], "filename_time_delta_s": dt, "delta_horizontal_m": horizontal, "delta_3d_m": three_d, "thermal_source": thermal["source_images"]["T"], "visible_source": visible["source_images"]["V"], "status": "candidate_same_lrf_shot_unverified_fire_target"})
possible.sort(key=lambda p: (p["filename_time_delta_s"], p["delta_3d_m"]))
selected = []
used_t, used_v = set(), set()
for pair in possible:
    t_key = (pair["session_id"], pair["thermal_capture_key"])
    v_key = (pair["session_id"], pair["visible_capture_key"])
    if t_key in used_t or v_key in used_v:
        continue
    selected.append(pair)
    used_t.add(t_key)
    used_v.add(v_key)


def summarize(pairs):
    out = {}
    for batch in sorted({p["batch_id"] for p in pairs}):
        values = [p["delta_3d_m"] for p in pairs if p["batch_id"] == batch]
        out[batch] = {"count": len(values), "median_delta_3d_m": statistics.median(values), "max_delta_3d_m": max(values)}
    return out


result = {"schema_version": "dji_lrf_cross_capture_tv_pairs_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "source": str(source), "same_capture_pairs": same_capture, "cross_capture_candidate_pairs": selected, "unpaired_singleton_groups": len(singletons) - 2 * len(selected), "batch_summary_same_capture": summarize(same_capture), "batch_summary_cross_capture": summarize(selected), "pairing_policy": {"same_batch_session_drone": True, "opposite_sensors_only": True, "filename_time_delta_max_s": 2, "lrf_coordinate_delta_3d_max_m": 0.5, "one_to_one": True}, "interpretation": "LRF metadata consistency only. Matching coordinates do not prove the laser dot, detected flame, smoke, and hotspot are the same physical target; no visual absolute-localization error is computed."}
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"same_capture": len(same_capture), "cross_capture": len(selected), "remaining_singletons": result["unpaired_singleton_groups"], "batch_summary_cross_capture": result["batch_summary_cross_capture"]}, ensure_ascii=False))
