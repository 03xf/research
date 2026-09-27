#!/usr/bin/env python3
"""Create a current-state B1-B4 experiment report from authoritative artifacts."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
out_json = root / "consolidated_report_round22.json"
out_md = root / "consolidated_report_round22.md"
if out_json.exists() or out_md.exists():
    raise SystemExit("report exists; refusing to overwrite")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summary(path):
    data = read(path)
    return data.get("summary", {})


round17 = read(root / "validation_round17_control/comparison.json")
round18 = read(root / "validation_round18_smoke_qc/comparison.json")
round19 = read(root / "validation_round19_thermal_qc/comparison.json")
cal = read(root / "localization/calibration_recovery_status_v1.json")
lrf = read(root / "localization/lrf_b4_stratified_metrics_v2.json")
dispersion = read(root / "localization/lrf_session_dispersion_v1.json")
photo_lrf = read(root / "localization/detection_lrf_association_all_round20.json")
batch_files = {
    "B1": {"inference": root / "inference_round21_B1_provisional/observations.json", "association": root / "association_round21_B1_provisional.json", "tracking": root / "tracking_round21_B1_provisional.json"},
    "B2": {"inference": root / "inference_round22_B2_provisional/observations.json", "association": root / "association_round22_B2_provisional.json", "tracking": root / "tracking_round22_B2_provisional.json"},
    "B3": {"inference": root / "inference_round21_B3_provisional/observations.json", "association": root / "association_round21_B3_provisional.json", "tracking": root / "tracking_round21_B3_provisional.json"},
    "B4": {"inference": root / "inference_round20_aligned_provisional/observations.json", "association": root / "association_round20_aligned_provisional.json", "tracking": root / "tracking_round20_aligned_provisional.json"},
}
batch_summary = {}
for batch, paths in batch_files.items():
    batch_summary[batch] = {kind: summary(path) for kind, path in paths.items()}

report = {
    "schema_version": "dji_consolidated_report_round22_v1",
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "/home/member/xmy/xmy only",
    "blind_test_accessed": False,
    "historical_results_preserved": True,
    "detector_gate": {
        "criteria": {"precision": 0.60, "recall": 0.70, "mAP50": 0.50},
        "status": "not_passed",
        "evidence": {
            "round17_control": str(root / "validation_round17_control/comparison.json"),
            "round18_smoke_qc": str(root / "validation_round18_smoke_qc/comparison.json"),
            "round19_thermal_qc": str(root / "validation_round19_thermal_qc/comparison.json"),
        },
        "current_interpretation": "No V/T model is qualified for final fire-event truth or blind-test release."
    },
    "validation": {"round17": round17["results"], "round18": {"delta": round18["delta"], "gate": round18["gate"]}, "round19": {"round19": round19["round19"]["classes"], "delta_vs_round12": round19["delta_vs_round12"], "gate": round19["gate"]}},
    "aligned_video_processing": batch_summary,
    "lrf_reference": {"B4_metrics": lrf["overall"], "B4_sample_count": lrf["sample_count"], "grouped_session_dispersion": str(root / "localization/lrf_session_dispersion_v1.json"), "cross_capture_pairs": str(root / "localization/lrf_cross_capture_tv_pairs_v1.json"), "photo_detection_association": str(root / "localization/detection_lrf_association_all_round20.json"), "photo_summary": photo_lrf["summary"], "semantics": "LRF coordinates are spatial references, not flame-center truth."},
    "calibration": {"status": cal["absolute_localization_status"], "usable_for_matrice4t": cal["usable_for_matrice4t"], "missing_parameters": cal["required_parameters"], "evidence": str(root / "localization/calibration_recovery_status_v1.json")},
    "capability_boundary": {"available": ["old-model and DJI-domain validation evidence", "timestamp-aligned T/V frame schedules", "provisional V/T detections with frame/time/model hashes", "temporal candidate association", "sensor-specific image-plane tracks", "B1-B4 grouped LRF metadata and B4 LRF error baseline", "LRF/detection independent correspondence records"], "unavailable": ["qualified fire-event detector", "spatially verified T/V association", "verified flame/hotspot-to-LRF target identity", "camera intrinsics/distortion/extrinsics", "absolute 3-D fire coordinates", "reprojection and ray-intersection errors"]},
    "next_actions": ["Review independent B1/B3/B4 smoke and hotspot scenes, not adjacent duplicate frames.", "Test tiled/small-target training only after label audit and preserve the same validation split.", "If a model passes the detector gate, freeze it before opening the sealed blind test.", "Obtain Matrice 4T calibration package or collect known-target V/T calibration data with synchronized pose/GPS/LRF.", "Implement range-assisted single-view geometry only after real intrinsics and extrinsics are verified.", "Keep B2 separate as pre-fire/hotspot candidate data."]
}
out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# DJI B1–B4 consolidated experiment report (Round22)",
    "",
    f"Generated UTC: `{report['generated_utc']}`",
    "",
    "## Current conclusion",
    "",
    "The reproducible pipeline now reaches timestamp-aligned provisional detection, temporal association, sensor-specific image-plane tracking, grouped LRF reference analysis, and calibration audit. The detector gate is not passed, T/V spatial correspondence is unverified, and absolute 3-D localization is unavailable because Matrice 4T intrinsics, distortion and extrinsics were not verified.",
    "",
    "## Batch processing",
    "",
]
for batch, data in batch_summary.items():
    lines.append(f"- **{batch}**: {data['inference'].get('observation_count', 0)} aligned observations; {data['association'].get('temporal_candidate_count', 0)} temporal candidates; {data['tracking'].get('track_count', 0)} sensor-specific tracks; spatially verified pairs: {data['association'].get('spatially_verified_count', 0)}.")
lines += [
    "",
    "## Detection and localization boundary",
    "",
    "- V/T model validation remains below the configured precision/recall/mAP50 gate; blind test remains sealed.",
    "- B2 is retained as a pre-fire/hotspot candidate batch and is excluded from burning-fire truth claims.",
    f"- B4 LRF reference baseline: `{lrf['sample_count']}` samples; mean/overall metrics are in `{root / 'localization/lrf_b4_stratified_metrics_v2.json'}`.",
    f"- All-batch LRF photo association: `{photo_lrf['summary']['detection_count']}` provisional boxes across `{photo_lrf['summary']['row_count']}` photos; same-target identity remains unverified.",
    f"- Calibration status: `{cal['absolute_localization_status']}`; required parameters remain unavailable according to `{root / 'localization/calibration_recovery_status_v1.json'}`.",
    "",
    "## Reproducibility evidence",
    "",
    f"- JSON report: `{out_json}`",
    f"- State: `{root / 'state.json'}`",
    f"- Aligned schedules: `{root / 'b1_aligned_frame_schedule_v1.json'}`, `{root / 'b2_aligned_frame_schedule_v1.json'}`, `{root / 'b3_aligned_frame_schedule_v1.json'}`, `{root / 'b4_aligned_frame_schedule_v1.json'}`",
    "",
    "## Next execution",
    "",
    *[f"{i}. {action}" for i, action in enumerate(report["next_actions"], 1)],
]
out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"json": str(out_json), "markdown": str(out_md), "detector_gate": report["detector_gate"]["status"], "absolute_localization": report["calibration"]["status"]}, ensure_ascii=False))
