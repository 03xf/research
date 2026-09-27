#!/usr/bin/env python3
"""Build conservative temporal T/V association records from aligned inference."""
import json
import math
from collections import Counter
from pathlib import Path


def center(box):
    return [(float(box[0]) + float(box[2])) / 2, (float(box[1]) + float(box[3])) / 2]


def enrich(row):
    source = Path(row["metadata_reference"]["thermal_source"])
    parts = source.parts
    drone = next((p for p in parts if p.startswith("无人机")), None)
    session = next((p for p in parts if p.startswith("DJI_") and len(p) >= 20), None)
    td, vd = row["thermal_detection"], row["visible_detection"]
    time_delta = abs(float(row["thermal_timestamp_s"]) - float(row["visible_timestamp_s"]))
    if td["boxes"] and vd["boxes"]:
        status = "paired_temporal_candidate"
    elif td["boxes"]:
        status = "thermal_only"
    elif vd["boxes"]:
        status = "visible_only"
    else:
        status = "no_detection"
    if time_delta > 0.1:
        status = "unpaired" if not (td["boxes"] or vd["boxes"]) else "unpaired_with_detection"
    return {**row, "session_id": session, "drone_id": drone, "association_status": status, "sync_quality": "normal" if time_delta <= .05 else ("suspicious" if time_delta <= .1 else "invalid"), "thermal_centers": [center(b) for b in td["boxes"]], "visible_centers": [center(b) for b in vd["boxes"]], "same_target_status": "unverified", "fire_event_id": None, "track_id": None, "spatial_correspondence": "unverified"}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    rows = [enrich(row) for row in source["observations"]]
    status_counts = Counter(row["association_status"] for row in rows)
    sync_counts = Counter(row["sync_quality"] for row in rows)
    payload = {"schema_version": "dji_aligned_association_v1", "source_inference": str(args.input), "provisional_detector": True, "association_basis": "timestamp-aligned frame schedule; no calibrated spatial correspondence", "thresholds": {"normal_max_s": .05, "suspicious_max_s": .1}, "summary": {"observation_count": len(rows), "status_counts": dict(status_counts), "sync_quality_counts": dict(sync_counts), "temporal_candidate_count": sum(x["association_status"] == "paired_temporal_candidate" for x in rows), "spatially_verified_count": 0}, "observations": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
