#!/usr/bin/env python3
"""Create timestamp-aligned strided T/V schedules for a selected batch."""
import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path


def fps(info):
    a, b = info["fps"].split("/")
    return float(a) / float(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--sync", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--stride", type=int, default=300)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    pairs = json.loads(args.sync.read_text(encoding="utf-8"))["pairs"]
    groups, deltas = [], []
    for pair in pairs:
        tfps, vfps = fps(pair["T_info"]), fps(pair["V_info"])
        tstart, vstart = float(pair["T_info"].get("start_s", 0) or 0), float(pair["V_info"].get("start_s", 0) or 0)
        tframes, vframes = int(pair["T_info"]["frames"]), int(pair["V_info"]["frames"])
        matches = []
        for sample_index, tf in enumerate(range(args.stride - 1, tframes, args.stride)):
            tt = tstart + tf / tfps
            vf = round((tt - vstart) * vfps)
            if not 0 <= vf < vframes:
                continue
            vt = vstart + vf / vfps
            delta = abs(vt - tt)
            deltas.append(delta)
            matches.append({"sample_index": sample_index, "thermal_frame": tf, "visible_frame": vf, "thermal_timestamp_s": tt, "visible_timestamp_s": vt, "predicted_sync_delta_s": delta})
        groups.append({"pair_key": pair["pair_key"], "thermal_source": pair["T"], "visible_source": pair["V"], "thermal_fps": tfps, "visible_fps": vfps, "matched_count": len(matches), "matches": matches})
    summary = {"batch": args.batch, "video_groups": len(groups), "planned_frame_pairs": len(deltas), "predicted_median_delta_s": statistics.median(deltas) if deltas else None, "predicted_p95_delta_s": sorted(deltas)[math.ceil(.95 * len(deltas))-1] if deltas else None, "predicted_max_delta_s": max(deltas) if deltas else None, "pairs_over_50ms": sum(x > .05 for x in deltas), "pairs_over_100ms": sum(x > .1 for x in deltas)}
    payload = {"schema_version": "dji_aligned_frame_schedule_batch_v1", "batch": args.batch, "created_utc": datetime.now(timezone.utc).isoformat(), "sync_source": str(args.sync), "stride": args.stride, "summary": summary, "frame_rule": "T frame stride-1; V frame is nearest frame at the same constant-fps timestamp", "spatial_correspondence": "unverified", "groups": groups}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
