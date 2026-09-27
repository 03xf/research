#!/usr/bin/env python3
"""Record Round15 gate and corrected provisional localization checkpoint."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
METRICS = ROOT / "validation_round15_oversample/metrics.json"
STATE = ROOT / "state.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if METRICS.exists():
    raise SystemExit("metrics file exists; refusing to overwrite")
threshold = {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}
metrics = {
    "schema_version": "dji_round15_oversample_validation_v1",
    "split": "validation",
    "blind_test_accessed": False,
    "dataset_manifest": str(ROOT / "datasets_round15_oversample/dataset_manifest.json"),
    "models": {"V": str(ROOT / "runs_round15_oversample/V_640_full/weights/best.pt"), "T": str(ROOT / "runs_round15_oversample/T_640_full/weights/best.pt")},
    "V": {"smoke": {"precision": 0.262, "recall": 0.115, "mAP50": 0.126, "instances": 52}, "flame": {"precision": 0.709, "recall": 0.478, "mAP50": 0.563, "instances": 23}},
    "T": {"hotspot": {"precision": 0.48629638804586695, "recall": 0.5, "mAP50": 0.4303436048108172, "instances": 58}},
    "comparison_round14": {"V_smoke_recall": {"round14": 0.231, "round15": 0.115}, "V_smoke_mAP50": {"round14": 0.211, "round15": 0.126}, "T_hotspot_recall": {"round14": 0.4827586206896552, "round15": 0.5}},
    "gate": {"thresholds": threshold, "status": "failed", "reason": "class-0 positive oversampling did not improve V smoke and T remains below precision/recall/mAP50 thresholds"},
    "validation_directories": {"V": str(ROOT / "validation_round15_oversample/V_val"), "T": str(ROOT / "validation_round15_oversample/T_val")},
    "generated_utc": datetime.now(timezone.utc).isoformat(),
}
write(METRICS, metrics)
s = read(STATE)
s["stage"] = "round15_failed_provisional_localization_complete"
s.setdefault("round15", {})["status"] = "training_complete_validation_failed"
s["round15"]["validation_metrics"] = str(METRICS)
s["round15"]["gate"] = "failed"
s["provisional_inference"] = dict(s.get("provisional_inference", {}), status="B4_TV_complete", V_summary="inference_round14_provisional/V_corrected/summary.json", T_summary="inference_round14_provisional/T_corrected2/summary.json", association_v4="association_round14_provisional_v4.json", degraded_tracking_v4="degraded_tracking_round14_provisional_v4.json", lrf_photo_detections="localization/lrf_photo_detections_provisional_v1.json", localization_report="localization/provisional_localization_report_v2.json", false_legacy_association="association_round14_provisional_v2.json", absolute_fire_localization="unavailable")
s["next_action"] = "Prioritize smoke/hotspot label and scene review, correct class definitions, and use timestamp-aligned re-sampling; retain blind test and absolute-3D gate."
s["updated_utc"] = datetime.now(timezone.utc).isoformat()
write(STATE, s)
print(json.dumps({"stage": s["stage"], "round15_gate": metrics["gate"]["status"], "localization_report": s["provisional_inference"]["localization_report"]}))
