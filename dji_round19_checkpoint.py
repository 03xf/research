#!/usr/bin/env python3
"""Register the parallel T hotspot-label QC experiment."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
target = root / "round19_thermal_qc_plan.json"
if target.exists():
    raise SystemExit("plan exists; refusing to overwrite")
data = root / "datasets_round19_thermal_qc_t/T"
run = root / "runs_round19_thermal_qc/T_640_auto"
assert (data / "dataset_manifest.json").is_file() and (run / "run_config.json").is_file()
doc = {"schema_version": "dji_round19_thermal_qc_plan_v1", "created_utc": datetime.now(timezone.utc).isoformat(), "hypothesis": "Six train-only T frames with missing or shifted hotspot boxes contribute to thermal detection errors.", "dataset_manifest": str(data / "dataset_manifest.json"), "run": str(run), "log": str(root / "logs_round19_thermal_qc/T_640_auto.log"), "comparison_model": str(root / "runs_round12/T_640_round12_full/weights/best.pt"), "same_base_weights_as_round12": True, "same_auto_optimizer_policy_as_round12": True, "validation_unchanged": True, "blind_test_accessed": False, "gate": {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}, "next_action": "Validate after 100 successful epochs, compare with Round12 on the same validation split, and keep blind test sealed."}
target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
path = root / "state.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["stage"] = "parallel_round18_v_round19_t_training"
state["round19"] = {"plan": str(target), "status": "training_running", "blind_test_accessed": False}
state["next_action"] = "Await separate V Round18 and T Round19 controlled validations; if either gate fails, expand independent train-session labels. Continue LRF and synchronized-frame audit without absolute-3D claims."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(target)
