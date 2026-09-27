"""Compare frozen development evaluations without selecting a lucky seed."""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def choose(rows):
    candidates = [row for row in rows if row["family"] in ("E1", "E2") and row["seed"] == 0]
    if not candidates:
        return None
    best = max(candidates, key=lambda row: (row["passed_classes"],
                                            row["worst_class_recall"], row["mean_ap50"],
                                            -row["imgsz"]))
    at_640 = next((row for row in candidates if row["imgsz"] == 640), None)
    if (at_640 and at_640["passed_classes"] == best["passed_classes"]
            and best["worst_class_recall"] - at_640["worst_class_recall"] < 0.02
            and best["mean_ap50"] - at_640["mean_ap50"] < 0.02):
        best = at_640
    return {"model_id": best["model_id"], "imgsz": best["imgsz"],
            "selection_basis": "seed 0 only; replicate before final reporting",
            "passed_classes": best["passed_classes"],
            "worst_class_recall": best["worst_class_recall"],
            "mean_ap50": best["mean_ap50"]}


def build(root, name):
    root = root.resolve()
    output_json = root / (name + ".json")
    output_csv = root / (name + ".csv")
    if output_json.exists() or output_csv.exists():
        raise FileExistsError(name)
    model_rows = []
    class_rows = []
    hashes = set()
    for path in sorted((root / "evaluations").glob("*/result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("status") != "complete":
            continue
        model_id = result["model_id"]
        family = model_id.split("_")[0]
        if family not in ("E0", "E1", "E2"):
            continue
        hashes.add(result["dataset_manifest_sha256"])
        seed = int(model_id.rsplit("_s", 1)[1]) if "_s" in model_id else None
        recalls = [row["work_metrics"]["recall"] if row["work_metrics"] else 0.0
                   for row in result["classes"]]
        model_rows.append({"model_id": model_id, "family": family,
                           "sensor": result["sensor"], "seed": seed,
                           "imgsz": result["imgsz"],
                           "passed_classes": result["passed_class_count"],
                           "total_classes": len(result["classes"]),
                           "worst_class_recall": min(recalls),
                           "mean_ap50": sum(row["ap50"] for row in result["classes"]) / len(result["classes"]),
                           "all_classes_passed": result["all_classes_passed"]})
        for entry in result["classes"]:
            work = entry["work_metrics"] or {}
            class_rows.append({"model_id": model_id, "family": family,
                               "sensor": result["sensor"], "seed": seed,
                               "imgsz": result["imgsz"], "class": entry["class_name"],
                               "ground_truth": entry["ground_truth"],
                               "threshold": entry["work_threshold"],
                               "P": work.get("precision"), "R": work.get("recall"),
                               "AP50": entry["ap50"], "AP50_95": entry["ap50_95"],
                               "negative_images": entry["negative_images"],
                               "negative_false_positive_images": work.get("negative_false_positive_images"),
                               "passed": entry["gate_passed"]})
    if len(hashes) != 1:
        raise ValueError("evaluation dataset manifests differ")
    by_sensor = defaultdict(list)
    for row in model_rows:
        by_sensor[row["sensor"]].append(row)
    selection = {sensor: choose(rows) for sensor, rows in by_sensor.items()}
    payload = {"schema_version": "dji_recovery_model_comparison_v1",
               "created_utc": datetime.now(timezone.utc).isoformat(),
               "dataset_manifest_sha256": next(iter(hashes)),
               "selection_priority": ["passed class count", "worst class recall", "mean AP50",
                                      "640 pixels if recall and AP50 differ by less than 0.02"],
               "historical_E0_is_baseline_only": True,
               "provisional_seed0_selection": selection,
               "model_rows": model_rows, "class_rows": class_rows,
               "development_split_historically_exposed": True,
               "confirmation_test_performed": False}
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with output_csv.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(class_rows[0]))
        writer.writeheader()
        writer.writerows(class_rows)
    print(json.dumps({"output": str(output_json), "model_count": len(model_rows),
                      "selection": selection}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    build(args.root, args.name)
