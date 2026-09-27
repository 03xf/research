"""Archive recovery status and register the completed B4 detection-quality audit."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    work = ROOT / "detection_quality_v2"
    status_path = ROOT / "status_current.json"
    paths = {
        "policy": work / "policy.json",
        "development_selection": work / "development_selection_v1.json",
        "V_area": work / "V_area_development_v1.json",
        "C4_manifest": work / "datasets/C4/manifest.json",
        "C4_run": work / "runs/C4_V_flame_960_s0/run_config.json",
        "C4_weights": work / "runs/C4_V_flame_960_s0/weights/best.pt",
        "C4_development": work / "C4_development/result.json",
        "T_confirmation": work / "T_confirmation_fixed_v1.json",
        "T_points": work / "T_source_points_fixed_v1.json",
        "T_mining": work / "T_hard_negative_mining_v1_complete/candidates.json",
        "T_crop_probe": work / "T_negative_crop_probe_v1/candidates.json",
        "report": work / "REPORT_20260926.md",
    }
    for path in [status_path, *paths.values()]:
        if not path.is_file():
            raise FileNotFoundError(path)
    status = load(status_path)
    if "detection_quality_v2" in status:
        raise ValueError("quality experiment already registered")
    if load(paths["C4_run"])["status"] != "complete":
        raise ValueError("C4 training incomplete")
    if load(paths["C4_development"])["classes"][0]["gate_passed"]:
        raise ValueError("C4 unexpectedly passed its development gate")
    if load(paths["T_confirmation"])["gate_passed"]:
        raise ValueError("T unexpectedly passed confirmation gate")
    points = load(paths["T_points"])["totals"]
    if (points["baseline_matched"], points["candidate_matched"],
            points["baseline_no_point_frame_with_detection"],
            points["candidate_no_point_frame_with_detection"]) != (54, 54, 9, 9):
        raise ValueError("T point comparison changed")
    if load(paths["T_mining"])["count"] != 0 or load(paths["T_crop_probe"])["candidate_count"] != 0:
        raise ValueError("T hard-negative audit changed")
    before = status_path.read_bytes()
    history = ROOT / "status_history" / (hashlib.sha256(before).hexdigest() + ".json")
    if history.exists() and history.read_bytes() != before:
        raise ValueError("status archive collision")
    if not history.exists():
        history.write_bytes(before)
    status["updated_utc"] = datetime.now(timezone.utc).isoformat()
    status["stage"] = "b4_detection_quality_no_deployable_candidate"
    status["next_action"] = "Keep frozen E2 V/T and existing B4 dashboard. Do not tune on exposed confirmation data; future detection work needs genuinely varied small flames and verified nonfire heat sources."
    status["status_history_archived"] = str(history)
    status["detection_quality_v2"] = {
        "status": "complete_no_deployable_candidate",
        "focus": ["B4 V small-flame misses", "B4 T high-temperature false detections"],
        "default_models": "frozen E2 V and E2 T unchanged",
        "V_C4_training_complete": True,
        "V_C4_development_passed": False,
        "V_new_confirmation_evaluation_done": False,
        "T_fixed_candidate_development_passed": True,
        "T_fixed_candidate_confirmation_passed": False,
        "T_no_point_alarm_frames_reduced": False,
        "T_candidate_deployed": False,
        "missing_training_hard_negatives": True,
        "files": {name: {"path": str(path), "sha256": digest(path)}
                  for name, path in paths.items()},
    }
    temp = ROOT / "status_current.json.tmp_detection_quality_v2"
    if temp.exists():
        raise FileExistsError(temp)
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(status_path)
    print(json.dumps({"stage": status["stage"], "archive": str(history),
                      "report_sha256": digest(paths["report"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
