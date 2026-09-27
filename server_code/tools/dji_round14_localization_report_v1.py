#!/usr/bin/env python3
"""Evidence-bound report for the provisional B4 localization branch."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    args = ap.parse_args()
    root = args.root
    loc = root / "localization"
    report_path = loc / "provisional_localization_report_v1.json"
    if report_path.exists():
        raise SystemExit("report exists; refusing to overwrite")
    assoc = read(root / "association_round14_provisional_v3.json")
    track = read(root / "degraded_tracking_round14_provisional_v3.json")
    photos = read(loc / "lrf_photo_detections_provisional_v1.json")
    lrf = read(loc / "lrf_b4_stratified_metrics_v2.json")
    calibration = read(loc / "calibration_recovery_status_v1.json")
    report = {
        "schema_version": "dji_provisional_localization_report_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "B4 provisional detector and LRF reference; not final fire localization",
        "detector_gate": "failed",
        "time_axis_correction": "Original association v2 used sample_index as frame_index and is invalid; v3 uses sample_index*vid_stride/fps.",
        "video_sync": assoc["summary"],
        "image_plane_tracking": track["summary"],
        "lrf_photo_detection": photos["summary"],
        "lrf_fixed_reference": {"reference_point_wgs84": lrf.get("reference_point_wgs84"), "reference_semantics": lrf.get("reference_semantics"), "sample_count": lrf.get("sample_count"), "overall": lrf.get("overall")},
        "target_correspondence": {"temporal_candidates": assoc["summary"]["status_counts"].get("temporal_candidate", 0), "spatially_verified_pairs": 0, "photo_detection_to_lrf_same_target_verified": 0, "reason": "No calibrated T/V mapping, laser pixel coordinate, or independent same-target adjudication."},
        "absolute_localization": {"status": "unavailable", "calibration_usable_for_matrice4t": calibration.get("usable_for_matrice4t"), "missing_parameters": calibration.get("required_parameters"), "no_absolute_fire_coordinates_emitted": True},
        "quality_warnings": ["V/T detector validation did not pass class thresholds", "Coarse 300-frame sampling with unequal FPS yields sparse <=100ms paired observations", "Sensor-specific coarse tracks are diagnostic and not validated fire-event identities", "LRF reference point is not flame, smoke or thermal-hotspot center", "B4/F1 LRF photos and candidate videos are not independently verified as same-time/same-target observations"],
        "evidence": {"association_v3": str(root / "association_round14_provisional_v3.json"), "image_plane_tracking_v3": str(root / "degraded_tracking_round14_provisional_v3.json"), "lrf_photo_detections": str(loc / "lrf_photo_detections_provisional_v1.json"), "lrf_reference_metrics": str(loc / "lrf_b4_stratified_metrics_v2.json"), "calibration_recovery": str(loc / "calibration_recovery_status_v1.json")},
        "next_actions": ["Re-sample V frames at thermal timestamps instead of equal sample indices", "Audit smoke and hotspot labels in independent train sessions; do not alter held-out validation", "Repeat T/V association with calibrated spatial mapping or manual same-target adjudication", "Acquire genuine Matrice 4T V/T intrinsics, distortion and extrinsics before absolute geolocation"]
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
