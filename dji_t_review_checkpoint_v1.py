"""Record the B4 thermal review queue without changing frozen model results."""
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    queue_dir = root / "thermal_background_v1/review_queue_v1"
    queue_path = queue_dir / "queue.json"
    decisions_path = queue_dir / "decisions.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))["records"]
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))["decisions"]
    if len(queue) != 32 or len({x["key"] for x in queue}) != 32:
        raise ValueError("thermal queue incomplete")
    if not set(decisions).issubset({x["key"] for x in queue}):
        raise ValueError("unknown thermal decision")
    status_path = root / "status_current.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    work = root / "thermal_background_v1"
    freeze_path = work / "review_frozen_v1.json"
    runs = {}
    for mode in ("T1_T_960_s0", "T2_T_960_s0"):
        path = work / "runs" / mode / "run_config.json"
        if path.exists():
            runs[mode] = json.loads(path.read_text(encoding="utf-8"))["status"]
    frozen = freeze_path.exists()
    training_started = bool(runs)
    history = root / "status_history"
    history.mkdir(exist_ok=True)
    backup = history / (digest(status_path) + ".json")
    if not backup.exists():
        shutil.copyfile(status_path, backup)
    status["updated_utc"] = datetime.now(timezone.utc).isoformat()
    status["stage"] = ("thermal_background_seed0_training" if training_started else
                       "thermal_background_review_frozen_training_pending" if frozen else
                       "thermal_background_review_pending")
    status["next_action"] = ("Finish T1/T2 seed-0 training and evaluate on the unchanged 66-image T development split." if training_started else
                             "Start T1/T2 controlled training." if frozen else
                             "Complete 32 paired B4 V/T reviews before training.")
    status["thermal_background_v1"] = {
        "status": "training" if training_started else "review_frozen" if frozen else "review_pending",
        "focus": "B4 T hot-background false detections while preserving fire-source coverage",
        "queue": str(queue_path),
        "queue_sha256": digest(queue_path),
        "decisions": str(decisions_path),
        "decision_count": len(decisions),
        "pair_count": 32,
        "existing_training_images": 16,
        "new_training_video_pairs": 16,
        "review_web_local_tunnel": "http://127.0.0.1:18797/",
        "E2_T_remains_default": True,
        "review_frozen_sha256": digest(freeze_path) if frozen else None,
        "runs": runs,
        "training_started": training_started,
        "review_has_negative_images": any(x["outcome"] == "usable" and not any(
            b["kind"] == "source" for b in x["boxes"]) for x in decisions.values()),
        "confirmation_threshold_tuning": False,
        "B4_primary": True,
        "historical_flame_C1_failure_retained": True,
    }
    temp = status_path.with_suffix(".json.new")
    if temp.exists():
        raise FileExistsError(temp)
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, status_path)
    print(json.dumps({"stage": status["stage"], "decisions": len(decisions),
                      "queue_sha256": digest(queue_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
