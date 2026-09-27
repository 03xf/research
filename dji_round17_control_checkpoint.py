#!/usr/bin/env python3
"""Record Round17 controlled comparisons without touching datasets or blind test."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
state_path = root / "state.json"
design_path = root / "round17_control_design.json"
if design_path.exists():
    raise SystemExit("design exists; refusing to overwrite")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


base = root / "runs_round14_960/V_960_recovery5/weights/best.pt"
original = root / "datasets_round12_copy_abs/V/data.yaml"
reviewed = root / "datasets_round16_reviewed_v/V/data.yaml"
run_root = root / "runs_round17_control"
runs = {
    "original_labels_adamw": run_root / "V_base_labels_adamw_wandboff",
    "reviewed_labels_adamw": root / "runs_round16_reviewed_v/V_640_full",
    "reviewed_labels_auto": run_root / "V_reviewed_labels_auto_wandboff",
}
assert all(path.exists() for path in (base, original, reviewed))
assert all(path.exists() for path in runs.values())

doc = {
    "schema_version": "dji_round17_optimizer_label_control_v1",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "question": "Separate the effects of seven train-only label changes from optimizer choice.",
    "common_base_weights": str(base),
    "common_base_weights_sha256": sha(base),
    "fixed_conditions": {
        "imgsz": 640,
        "batch": 8,
        "epochs": 100,
        "seed": 0,
        "validation_labels_unchanged": True,
        "blind_test_accessed": False,
    },
    "original_data_yaml": str(original),
    "original_data_yaml_sha256": sha(original),
    "reviewed_data_yaml": str(reviewed),
    "reviewed_data_yaml_sha256": sha(reviewed),
    "cells": {key: {"run": str(path), "status": "running" if key != "reviewed_labels_adamw" else "validation_failed", "run_config": str(path / "run_config.json")} for key, path in runs.items()},
    "missing_cell": "original_labels_auto; launch after GPU capacity is available if needed for full 2x2 comparison",
    "caution": "Round16 is not comparable to Round12 because base weights, optimizer and labels changed together; use this controlled matrix only. Auto optimizer may override requested lr0.",
    "next_action": "Validate both active runs on the unchanged validation split, complete the fourth cell if resources permit, and compare per-class metrics without opening blind test.",
}
design_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
state["stage"] = "round17_control_training"
state["round17"] = {"design": str(design_path), "status": "two_controls_running", "blind_test_accessed": False}
state["next_action"] = doc["next_action"]
state["updated_utc"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(design_path)
