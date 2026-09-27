"""Freeze the development-selected seed-0 E2 weights and work thresholds."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(root):
    root = root.resolve()
    comparison = root / "comparison_seed0_seed1_seed2_v1.json"
    output = root / "model_freeze_preconfirmation_v1.json"
    if output.exists():
        raise FileExistsError(output)
    selected = json.loads(comparison.read_text(encoding="utf-8"))[
        "provisional_seed0_selection"
    ]
    models = {}
    for sensor, names in (("V", ("smoke", "flame")), ("T", ("hotspot",))):
        model_id = selected[sensor]["model_id"]
        if model_id != "E2_%s_960_s0" % sensor:
            raise ValueError("unexpected development selection: " + model_id)
        evaluation = json.loads((root / "evaluations" / model_id / "result.json").read_text(encoding="utf-8"))
        if evaluation["status"] != "complete" or evaluation["sensor"] != sensor:
            raise ValueError("incomplete development evaluation: " + model_id)
        weights = Path(evaluation["weights"])
        if sha256(weights) != evaluation["weights_sha256"]:
            raise ValueError("weights hash mismatch: " + model_id)
        thresholds = {row["class_name"]: row["work_threshold"] for row in evaluation["classes"]}
        if set(thresholds) != set(names):
            raise ValueError("class mismatch: " + model_id)
        models[sensor] = {
            "model_id": model_id,
            "weights": str(weights),
            "weights_sha256": evaluation["weights_sha256"],
            "imgsz": evaluation["imgsz"],
            "thresholds": thresholds,
            "development_evaluation_sha256": sha256(root / "evaluations" / model_id / "result.json"),
            "development_passed": evaluation["all_classes_passed"],
        }
    payload = {
        "schema_version": "dji_recovery_confirmation_freeze_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "selection_source": str(comparison),
        "selection_source_sha256": sha256(comparison),
        "selection_rule": "seed 0 selected on development only; seeds 1 and 2 reported as replication",
        "development_split_historically_exposed": True,
        "confirmation_test_performed": False,
        "models": models,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "models": models}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    main(args.root)
