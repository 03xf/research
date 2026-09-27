#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
out = root / "validation_round16_reviewed_v/metrics.json"
if out.exists():
    raise SystemExit("metrics exists; refusing to overwrite")
metrics = {
    "schema_version": "dji_round16_reviewed_v_validation_v1",
    "split": "validation",
    "blind_test_accessed": False,
    "model": str(root / "runs_round16_reviewed_v/V_640_full/weights/best.pt"),
    "dataset": str(root / "datasets_round16_reviewed_v/V/data.yaml"),
    "change": "seven train-only visible labels manually reviewed, one weak sample excluded, explicit AdamW; original data preserved",
    "V": {"smoke": {"precision": 0.360, "recall": 0.288, "mAP50": 0.235, "mAP50_95": 0.0504, "instances": 52}, "flame": {"precision": 0.676, "recall": 0.546, "mAP50": 0.532, "mAP50_95": 0.237, "instances": 23}},
    "comparison": {"smoke_recall": {"round14_960": 0.231, "round15_oversample": 0.115, "round16_reviewed": 0.288}, "smoke_mAP50": {"round14_960": 0.211, "round15_oversample": 0.126, "round16_reviewed": 0.235}, "flame_recall": {"round14_960": 0.609, "round16_reviewed": 0.546}},
    "gate": {"criteria": {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}, "status": "failed", "reason": "smoke and flame recall below threshold; smoke precision and mAP50 below threshold"},
    "generated_utc": datetime.now(timezone.utc).isoformat()
}
out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
p = root / "state.json"
s = json.loads(p.read_text(encoding="utf-8"))
s["stage"] = "round16_validation_failed_next_label_review"
s.setdefault("round16", {}).update({"status": "training_complete_validation_failed", "validation_metrics": str(out), "gate": "failed", "interpretation": "smoke recall modestly improved relative to Round14 but remains far below gate; flame recall declined; combined label+optimizer change cannot be causally separated"})
s["next_action"] = "Review additional independent smoke and hotspot train scenes (including true smoke without dominant flame), build separately controlled label-only and optimizer-only comparisons, then revalidate. Improve timestamp-aligned T/V sampling; do not use blind test or absolute-3D without calibration."
s["updated_utc"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(s["stage"])
