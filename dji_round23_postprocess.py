#!/usr/bin/env python3
"""Wait for Round23 tiled V/T training and validate on original full frames."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

work = Path("/home/member/xmy/xmy")
sys.path.insert(0, str(work / "code/tools"))
import dji_round17_postprocess as common

root = work / "results/dji_adaptation/b4_trial_v7"
runs = {"V": root / "runs_round23_tiled_retry1/V_640_auto", "T": root / "runs_round23_tiled_retry1/T_640_auto"}
common.OUT = root / "validation_round23_tiled_retry1"
deadline = time.monotonic() + 5 * 3600
while not all(common.valid_completion(run) for run in runs.values()):
    if time.monotonic() > deadline:
        raise SystemExit("Round23 training incomplete after five hours; inspect run logs")
    time.sleep(60)
common.OUT.mkdir(parents=True, exist_ok=True)
results = {sensor: common.validate(sensor, run) for sensor, run in runs.items()}
gate = {"precision": .60, "recall": .70, "mAP50": .50}
passes = {sensor: all(row["validation_instances"] >= 20 and all(row[key] >= threshold for key, threshold in gate.items()) for row in result["classes"].values()) for sensor, result in results.items()}
reference = {"V": json.loads((root / "validation_round18_smoke_qc/V_640_auto/metrics.json").read_text(encoding="utf-8")), "T": json.loads((root / "validation_round19_thermal_qc/T_640_auto/metrics.json").read_text(encoding="utf-8"))}
deltas = {sensor: {cls: {metric: row[metric] - reference[sensor]["classes"][cls][metric] for metric in gate} for cls, row in result["classes"].items()} for sensor, result in results.items()}
payload = {"schema_version": "dji_round23_tiled_comparison_v1", "generated_utc": datetime.now(timezone.utc).isoformat(), "validation_only": True, "blind_test_accessed": False, "tiled": results, "reference": reference, "delta": deltas, "gate": {"criteria": gate, "passed_by_sensor": passes, "both_passed": all(passes.values())}, "interpretation": "Train images are tiled; validation images are original full frames. Differences reflect tiling plus any changed T base checkpoint, so T cannot be interpreted as a pure tiling ablation against Round19."}
out = common.OUT / "comparison.json"
if out.exists():
    raise SystemExit("comparison exists; refusing to overwrite")
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state_path = root / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round23_tiled_validation_passed" if all(passes.values()) else "round23_tiled_validation_failed_next_scene_diversity"
state["round23"] = {"status": state["stage"], "comparison": str(out), "blind_test_accessed": False}
state["next_action"] = "If both V/T gates pass, freeze and run the sealed blind test; otherwise identify independent training scenes and review labels, with calibration recovery proceeding separately."
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"stage": state["stage"], "comparison": str(out), "gate": payload["gate"], "delta": deltas}, ensure_ascii=False), flush=True)
