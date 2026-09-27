"""Apply the frozen B4 T development selection policy to seed-0 results."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "thermal_background_v1"
    output = work / "development_selection_v1.json"
    if output.exists():
        raise FileExistsError(output)
    policy_path = work / "selection_policy_v1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    baseline = policy["baseline"]
    if digest(Path(policy["baseline_result"])) != policy["baseline_result_sha256"]:
        raise ValueError("E2 baseline changed after policy freeze")
    rows = []
    val_signatures = []
    for mode in ("T1", "T2"):
        run_path = work / "runs" / f"{mode}_T_960_s0" / "run_config.json"
        result_path = work / "evaluations" / f"{mode}_T_960_s0" / "result.json"
        manifest_path = work / "datasets" / mode / "manifest.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if run["status"] != "complete" or result["status"] != "complete" or result["images"] != 66:
            raise ValueError("incomplete run/evaluation: " + mode)
        if run["weights_best.pt_sha256"] != result["weights_sha256"]:
            raise ValueError("weight hash mismatch: " + mode)
        c = result["classes"][0]
        if c["class_name"] != "hotspot" or c["ground_truth"] != 73:
            raise ValueError("development truth changed: " + mode)
        val_signatures.append({x["image"]: (x["image_sha256"], x["new_label_sha256"])
                               for x in manifest["records"] if x["split"] == "validation"})
        m = c["work_metrics"]
        eligible = bool(c["gate_passed"] and m and m["tp"] >= baseline["tp"] - 2
                        and m["fp"] <= baseline["fp"] - 3
                        and m["negative_false_positive_images"] < baseline["negative_false_positive_images"])
        rows.append({"mode": mode, "run": str(run_path), "run_sha256": digest(run_path),
                     "evaluation": str(result_path), "evaluation_sha256": digest(result_path),
                     "weights": result["weights"], "weights_sha256": result["weights_sha256"],
                     "threshold": c["work_threshold"], "P": m["precision"] if m else None,
                     "R": m["recall"] if m else None, "AP50": c["ap50"],
                     "tp": m["tp"] if m else None, "fp": m["fp"] if m else None,
                     "negative_false_positive_images": m["negative_false_positive_images"] if m else None,
                     "gate_passed": c["gate_passed"], "eligible": eligible})
    if val_signatures[0] != val_signatures[1]:
        raise ValueError("T1/T2 development images or labels differ")
    candidates = [row for row in rows if row["eligible"]]
    selected = min(candidates, key=lambda x: (x["fp"], -x["tp"], -x["AP50"], x["mode"])) if candidates else None
    payload = {"schema_version": "dji_b4_thermal_development_selection_v1",
               "created_utc": datetime.now(timezone.utc).isoformat(),
               "policy_sha256": digest(policy_path), "baseline": baseline,
               "candidates": rows, "selected_mode": selected["mode"] if selected else None,
               "seed_repetitions_required": [1, 2] if selected else [],
               "predeclared_confirmation_seed": 0,
               "confirmation_not_used_for_selection": True}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected_mode": payload["selected_mode"], "candidates": [
        {k: x[k] for k in ("mode", "P", "R", "AP50", "tp", "fp", "negative_false_positive_images", "eligible")}
        for x in rows]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
