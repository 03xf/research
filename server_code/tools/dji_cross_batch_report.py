#!/usr/bin/env python3
"""Create a cross-batch report from completed DJI coarse inference outputs."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
import statistics


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    quality = load(args.results / "detection_quality.json")
    grouped = defaultdict(lambda: {"source_count": 0, "sampled_frames": 0, "detection_frames": 0, "boxes": 0, "invalid_boxes": 0, "confidence": [], "max_zero_run": 0})
    for row in quality.get("sources", []):
        key = f"{row.get('batch_id')}:{row.get('sensor')}"
        g = grouped[key]
        g["source_count"] += 1
        g["sampled_frames"] += row.get("sampled_frames", 0)
        g["detection_frames"] += row.get("detection_frames", 0)
        g["boxes"] += row.get("boxes", 0)
        g["invalid_boxes"] += row.get("invalid_boxes", 0)
        g["max_zero_run"] = max(g["max_zero_run"], row.get("max_zero_run", 0))
        if row.get("mean_confidence") is not None:
            g["confidence"].append(row["mean_confidence"])
    for g in grouped.values():
        vals = g.pop("confidence")
        g["detection_frame_rate"] = g["detection_frames"] / g["sampled_frames"] if g["sampled_frames"] else 0.0
        g["mean_source_confidence"] = statistics.mean(vals) if vals else None
    association = load(args.results / "tv_association.json") if (args.results / "tv_association.json").exists() else {}
    tracking = load(args.results / "tv_tracking.json") if (args.results / "tv_tracking.json").exists() else {}
    lrf = load(args.results / "lrf_summary.json") if (args.results / "lrf_summary.json").exists() else {}
    lrf_interpretation = {}
    for batch, values in lrf.items():
        if batch in {"B1", "B3"}:
            lrf_interpretation[batch] = "aggregate is not an absolute accuracy estimate; multiple spatial reference points must be grouped by session/target"
        elif batch == "B2":
            lrf_interpretation[batch] = "pre-fire candidate reference; do not treat as flame-center truth"
        elif batch == "B4":
            lrf_interpretation[batch] = "primary laser-reference group; still not identical to flame-center truth"
    payload = {
        "schema_version": "dji_cross_batch_report_v1",
        "detection_by_batch_sensor": dict(sorted(grouped.items())),
        "association_summary": association.get("summary"),
        "tracking_summary": tracking.get("tracking", {}),
        "lrf_summary": lrf,
        "lrf_interpretation": lrf_interpretation,
        "absolute_3d_localization": "disabled_until_real_intrinsics_and_extrinsics_are_confirmed"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"groups": len(grouped), "association": association.get("summary"), "tracks": tracking.get("tracking", {}).get("track_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
