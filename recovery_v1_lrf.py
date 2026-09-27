"""Recount LRF events and retain the distinction between reference and prediction."""

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_prepare import ROOT, digest, write_new


def run(root, out):
    groups_file = root / "localization/lrf_capture_groups_round12.json"
    reference_file = root / "localization/lrf_b4_reference_v1.json"
    calibration_file = root / "localization/calibration_audit_v1.json"
    data = json.loads(groups_file.read_text(encoding="utf-8"))
    reference = json.loads(reference_file.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_file.read_text(encoding="utf-8"))
    if out.exists():
        raise FileExistsError(out)
    groups = data["capture_groups"]
    if len(groups) != data["capture_group_count"] or sum(g["record_count"] for g in groups) != data["record_count"]:
        raise ValueError("LRF capture-group counts do not reconcile")
    by_batch = {}
    rows = []
    for batch in ("B1", "B2", "B3", "B4"):
        subset = [g for g in groups if g["batch_id"] == batch]
        by_batch[batch] = {
            "photo_records": sum(g["record_count"] for g in subset),
            "capture_groups": len(subset),
            "paired_sensor_groups": sum(len(g["sensors"]) == 2 for g in subset),
            "same_physical_source_verified": 0,
        }
        for group in subset:
            rows.append({
                "group_id": group["group_id"], "batch_id": batch,
                "session_id": group["session_id"], "drone_id": group["drone_id"],
                "capture_key": group["capture_key"], "photo_records": group["record_count"],
                "sensors": ",".join(group["sensors"]),
                "tv_lrf_coordinate_delta_m": group.get("tv_lrf_coordinate_delta_m"),
                "physical_source_id": None, "lrf_hit_on_ground_source": "unverified",
                "ground_reference_origin": "unverified",
                "visual_prediction_wgs84": None,
                "association_status": "reference_metadata_only",
                "reviewer": None, "review_note": None,
            })
    result = {
        "schema_version": "dji_recovery_lrf_event_audit_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "capture_group_source": str(groups_file), "capture_group_source_sha256": digest(groups_file),
        "legacy_b4_reference_source": str(reference_file), "legacy_b4_reference_sha256": digest(reference_file),
        "calibration_audit_source": str(calibration_file), "calibration_audit_sha256": digest(calibration_file),
        "by_batch": by_batch,
        "legacy_b4_reference_summary": reference["summary"],
        "legacy_b4_reference_semantics": "LRF record dispersion against a fixed reference; reference provenance and same-ground-source identity require review",
        "calibration_parameters": calibration["calibration_parameters"],
        "absolute_visual_localization": "unavailable",
        "visual_localization_error_m": None,
        "physical_target_confirmed_groups": 0,
        "next_action": "Independently review each LRF landing point and reference origin before associating a capture group with a ground burning source.",
    }
    out.mkdir(parents=True)
    write_new(out / "lrf_event_audit.json", result)
    write_new(out / "lrf_review_rows.json", {"schema_version": "dji_recovery_lrf_review_rows_v1", "items": rows})
    with (out / "lrf_review_rows.csv").open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"by_batch": by_batch, "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    run(args.root, args.out or args.root / "recovery_v1/lrf")
