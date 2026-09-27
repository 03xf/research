#!/usr/bin/env python3
"""Wait for Round17 controls, validate on the unchanged split, and checkpoint."""
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORK = Path("/home/member/xmy/xmy")
ROOT = WORK / "results/dji_adaptation/b4_trial_v7"
DESIGN = ROOT / "round17_control_design_v2.json"
OUT = ROOT / "validation_round17_control"
STATE = ROOT / "state.json"
sys.path.insert(0, str(WORK / "code/projects/ultralytics"))
from ultralytics import YOLO


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def absolute(path):
    p = Path(path)
    return p if p.is_absolute() else WORK / p


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_completion(run):
    cfg = run / "run_config.json"
    results = run / "results.csv"
    weights = run / "weights/best.pt"
    if not all(p.is_file() for p in (cfg, results, weights)):
        return False
    config = read(cfg)
    if not config.get("finished_utc"):
        return False
    return len(list(csv.DictReader(results.open(encoding="utf-8")))) == 100


def label_counts(data_yaml):
    counts = Counter()
    for label in (data_yaml.parent / "labels/validation").glob("*.txt"):
        for line in label.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[int(line.split()[0])] += 1
    return counts


def validate(name, run):
    folder = OUT / name
    metrics_file = folder / "metrics.json"
    if metrics_file.exists():
        return read(metrics_file)
    if folder.exists():
        raise RuntimeError(f"partial validation directory exists; inspect before retry: {folder}")
    config = read(run / "run_config.json")
    data_yaml = absolute(config.get("data") or config.get("dataset"))
    weights = run / "weights/best.pt"
    model = YOLO(str(weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    metrics = model.val(data=str(data_yaml), split="val", imgsz=640, batch=8, conf=0.001, device="0", project=str(OUT), name=name, exist_ok=False, plots=True, verbose=False)
    names = model.names
    counts = label_counts(data_yaml)
    box = metrics.box
    class_ids = [int(x) for x in box.ap_class_index]
    classes = {}
    for index, cls in enumerate(class_ids):
        title = names[cls] if isinstance(names, dict) else names[cls]
        classes[title] = {"precision": float(box.p[index]), "recall": float(box.r[index]), "mAP50": float(box.ap50[index]), "mAP50_95": float(box.ap[index]), "validation_instances": counts[cls]}
    payload = {"schema_version": "dji_round17_control_validation_v1", "run": str(run), "data": str(data_yaml), "data_yaml_sha256": sha(data_yaml), "weights": str(weights), "weights_sha256": sha(weights), "split": "validation", "blind_test_accessed": False, "imgsz": 640, "batch": 8, "confidence_for_AP": 0.001, "classes": classes, "generated_utc": datetime.now(timezone.utc).isoformat()}
    metrics_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main():
    design = read(DESIGN)
    cells = {name: absolute(cell["run"]) for name, cell in design["cells"].items()}
    active = ["original_labels_adamw", "reviewed_labels_auto", "original_labels_auto"]
    deadline = time.monotonic() + 3 * 3600
    while not all(valid_completion(cells[name]) for name in active):
        if time.monotonic() > deadline:
            raise RuntimeError("Round17 training did not complete within 3 hours; inspect run logs")
        time.sleep(60)
    OUT.mkdir(parents=True, exist_ok=True)
    results = {name: validate(name, run) for name, run in cells.items()}
    gate = {"precision": 0.60, "recall": 0.70, "mAP50": 0.50}
    comparison = {}
    for name, result in results.items():
        classes = result["classes"]
        comparison[name] = {cls: {key: round(row[key], 6) for key in gate} for cls, row in classes.items()}
        comparison[name]["gate_passed"] = all(row["validation_instances"] >= 20 and all(row[key] >= threshold for key, threshold in gate.items()) for row in classes.values())
    report = {"schema_version": "dji_round17_control_comparison_v1", "design": str(DESIGN), "validation_only": True, "blind_test_accessed": False, "gate": gate, "results": comparison, "interpretation": "Compare cells with the same base checkpoint, image size, epoch count and validation split. Auto optimizer may override requested learning rate. No conclusion about generalization can be drawn from the sealed blind test.", "generated_utc": datetime.now(timezone.utc).isoformat()}
    out = OUT / "comparison.json"
    if out.exists():
        raise RuntimeError(f"comparison already exists: {out}")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state = read(STATE)
    state["stage"] = "round17_validation_complete" if any(row["gate_passed"] for row in comparison.values()) else "round17_validation_failed_next_dataset_review"
    state["round17"] = {"design": str(DESIGN), "status": state["stage"], "comparison": str(out), "blind_test_accessed": False}
    state["next_action"] = "If gate passed, freeze model and then open blind test. Otherwise review Round18 smoke-label proposals, audit hotspot labels, and keep blind test sealed. Continue timestamp-aligned B4 sampling and LRF reference matching without absolute localization."
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"comparison": str(out), "stage": state["stage"], "results": comparison}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
