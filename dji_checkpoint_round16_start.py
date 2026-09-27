#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
p = root / "state.json"
s = json.loads(p.read_text(encoding="utf-8"))
s["stage"] = "round16_reviewed_v_training"
s["round16"] = {"scope": "V-only training-label correction and explicit-AdamW experiment", "visual_audit": "results/dji_adaptation/b4_trial_v7/round16_visual_audit_v1.json", "dataset": "results/dji_adaptation/b4_trial_v7/datasets_round16_reviewed_v/V", "training_run": "results/dji_adaptation/b4_trial_v7/runs_round16_reviewed_v/V_640_full", "status": "smoke_passed_full_running", "validation_unchanged": True, "blind_test_accessed": False, "original_labels_preserved": True, "cause_hypothesis": "weak smoke label localization/class noise"}
s["next_action"] = "Finish Round16 V, validate on fixed held-out validation, compare smoke/flame to Round14; continue reviewing diverse train-only smoke and hotspot scenes."
s["updated_utc"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(s["stage"])
