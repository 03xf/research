#!/usr/bin/env python3
"""Correct path-derived session/drone metadata without changing detections."""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    changed = 0
    for row in payload["observations"]:
        path = Path(row["metadata_reference"]["thermal_source"])
        session = path.parent.name
        drone = path.parent.parent.name
        assert session.startswith("DJI_") and drone.startswith("无人机")
        if row.get("session_id") != session or row.get("drone_id") != drone:
            changed += 1
        row["session_id"] = session
        row["drone_id"] = drone
    payload["schema_version"] = "dji_aligned_inference_corrected_provenance_v2"
    payload["corrected_from"] = str(args.input)
    payload["provenance_correction"] = {"rows_changed": changed, "rule": "thermal_source parent=session, grandparent=drone; detections and frame/timestamps unchanged"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["provenance_correction"], ensure_ascii=False))


if __name__ == "__main__":
    main()
