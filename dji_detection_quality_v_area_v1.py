"""Break down B4 development flame coverage by true box area for fixed candidates."""
import argparse
import collections
import json
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import digest, iou


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def area_bin(box):
    x1, y1, x2, y2 = box
    area = (x2-x1)*(y2-y1)
    return "<0.5%" if area < 0.005 else "0.5–2%" if area < 0.02 else ">=2%"


def score(rows, cls, threshold):
    counts = collections.defaultdict(lambda: collections.Counter())
    for row in rows:
        truth = [x for x in row["truth"] if x["class"] == cls]
        predictions = sorted((x for x in row["predictions"]
                              if x["class"] == cls and x["confidence"] >= threshold),
                             key=lambda x: x["confidence"], reverse=True)
        used = set()
        for prediction in predictions:
            candidates = [(iou(prediction["xyxy"], target["xyxy"]), index)
                          for index, target in enumerate(truth) if index not in used]
            best, index = max(candidates, default=(0.0, -1))
            if best >= 0.5:
                used.add(index)
        for index, target in enumerate(truth):
            group = area_bin(target["xyxy"])
            counts[group]["truth"] += 1
            counts[group]["matched"] += index in used
    return {group: dict(value) for group, value in counts.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    out = work / "V_area_development_v1.json"
    if out.exists():
        raise FileExistsError(out)
    specs = [
        ("E2_960", root / "evaluations/E2_V_960_s0/predictions.json",
         root / "evaluations/E2_V_960_s0/result.json", 1),
        ("E2_1280", work / "V1280_development/predictions.json",
         work / "V1280_development/result.json", 1),
        ("E2_1536", work / "V1536_development/predictions.json",
         work / "V1536_development/result.json", 1),
        ("E2_two_tiles_960", work / "V_tile2_960_development/predictions.json",
         work / "V_tile2_960_development/result.json", 1),
        ("C4_small_scale", work / "C4_development/predictions.json",
         work / "C4_development/result.json", 0),
    ]
    results = {}
    reference = None
    for name, predictions_path, result_path, cls in specs:
        predictions = load(predictions_path)["rows"]
        if name == "E2_two_tiles_960":
            threshold = load(result_path)["V_flame"]["work_threshold"]
        else:
            threshold = load(result_path)["classes"][cls]["work_threshold"]
        if len(predictions) != 61 or threshold is None:
            raise ValueError("candidate development incomplete: " + name)
        ids = [(row["observation_id"], row["image_sha256"])
               for row in predictions]
        if reference is None:
            reference = ids
        elif ids != reference:
            raise ValueError("candidate image order/hash differs: " + name)
        results[name] = {"predictions_sha256": digest(predictions_path),
                         "result_sha256": digest(result_path),
                         "work_threshold": threshold,
                         "by_truth_area": score(predictions, cls, threshold)}
    out.write_text(json.dumps({"schema_version": "dji_b4_v_development_area_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "images": 61, "results": results,
        "limits": "61 historically exposed B4 development images; area is normalized box area, not physical fire size"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value["by_truth_area"] for key, value in results.items()},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
