#!/usr/bin/env python3
"""Conservative centroid tracker for T/V association records.

Tracks are maintained separately per sensor.  A fused track_id is emitted only
for a paired single-target observation; multi-target or ambiguous records
retain sensor-specific IDs and are never forcibly merged.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def center(box):
    x1, y1, x2, y2 = map(float, box)
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def update_tracks(states, boxes, next_id, max_dist):
    assigned = []
    used = set()
    for box in boxes:
        c = center(box)
        candidates = [(dist(c, state["center"]), tid, state) for tid, state in states.items() if tid not in used and state["age"] <= 3]
        if candidates:
            d, tid, state = min(candidates)
            if d <= max_dist:
                used.add(tid)
                state["center"], state["age"], state["frames"] = c, 0, state["frames"] + 1
                assigned.append(tid)
                continue
        tid = next_id
        next_id += 1
        states[tid] = {"center": c, "age": 0, "frames": 1}
        used.add(tid)
        assigned.append(tid)
    for tid in list(states):
        if tid not in used:
            states[tid]["age"] += 1
            if states[tid]["age"] > 3:
                del states[tid]
    return assigned, next_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--max-pixel-distance", type=float, default=180.0)
    args = ap.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rows = sorted(payload.get("observations", []), key=lambda r: (r.get("batch_id"), r.get("video_group"), r.get("timestamp_s", 0.0)))
    states = defaultdict(dict)
    counters = defaultdict(int)
    track_stats = defaultdict(lambda: {"frames": 0, "last_time": None, "confidence": []})
    for row in rows:
        key = (row.get("batch_id"), row.get("video_group"))
        t_boxes = row.get("thermal_detection", {}).get("boxes", [])
        v_boxes = row.get("visible_detection", {}).get("boxes", [])
        t_ids, counters[(key, "T")] = update_tracks(states[(key, "T")], t_boxes, counters[(key, "T")] + 1, args.max_pixel_distance)
        v_ids, counters[(key, "V")] = update_tracks(states[(key, "V")], v_boxes, counters[(key, "V")] + 1, args.max_pixel_distance)
        row["thermal_track_ids"], row["visible_track_ids"] = t_ids, v_ids
        row["track_id"] = None
        if row.get("association_status") == "paired" and len(t_ids) == 1 and len(v_ids) == 1:
            row["track_id"] = f"{key[0]}:{key[1]}:F{t_ids[0]}-{v_ids[0]}"
        for sensor, ids, det in (("T", t_ids, row.get("thermal_detection", {})), ("V", v_ids, row.get("visible_detection", {}))):
            conf = det.get("confidence", [])
            for tid in ids:
                stat = track_stats[(key, sensor, tid)]
                stat["frames"] += 1
                stat["last_time"] = row.get("timestamp_s")
                if conf:
                    stat["confidence"].append(float(max(conf)))
    for stat in track_stats.values():
        vals = stat.pop("confidence")
        stat["mean_confidence"] = sum(vals) / len(vals) if vals else None
    payload["schema_version"] = "dji_tv_tracking_v1"
    payload["tracking"] = {"max_pixel_distance": args.max_pixel_distance, "track_count": len(track_stats), "tracks": {str(k): v for k, v in track_stats.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"track_count": len(track_stats), "observation_count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
