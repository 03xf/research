"""One-time fixed-rule T confirmation after B4 development selection."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import average_precision, digest, iou, totals


def suppress(boxes):
    kept = []
    for box in sorted(boxes, key=lambda x: x["confidence"], reverse=True):
        if all(box["class"] != previous["class"] or iou(box["xyxy"], previous["xyxy"]) <= 0.45
               for previous in kept):
            kept.append(box)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    out = work / "T_confirmation_fixed_v1.json"
    if out.exists():
        raise FileExistsError(out)
    freeze_path = work / "development_selection_v1.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    selected = freeze["T_selected"]
    if not selected or selected["threshold"] != 0.15:
        raise ValueError("T rule not frozen to 0.15")
    source = root / "evaluations/confirmation_frozen_v1/predictions_T.json"
    original = json.loads(source.read_text(encoding="utf-8"))["rows"]
    if len(original) != 194:
        raise ValueError("confirmation set changed")
    rows = [{**row, "predictions": suppress(row["predictions"])} for row in original]
    baseline = totals(original, 0, 0.14)
    candidate = totals(rows, 0, 0.15)
    ap50 = average_precision(rows, 0, 0.50)
    per_session = []
    for session in sorted({row["session_id"] for row in rows}):
        part = [row for row in rows if row["session_id"] == session]
        per_session.append({"session": session, "images": len(part),
                            "truth": sum(len(row["truth"]) for row in part),
                            **totals(part, 0, 0.15)})
    gate = candidate["precision"] >= 0.60 and candidate["recall"] >= 0.70 and ap50 >= 0.50
    report = {"schema_version": "dji_b4_T_fixed_confirmation_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "historically_exposed": True, "selection_uses_confirmation": False,
              "freeze_sha256": digest(freeze_path),
              "confirmation_predictions_sha256": digest(source),
              "rule": {"weights": "E2 T unchanged", "extra_nms_iou": 0.45,
                       "work_threshold": 0.15},
              "baseline_E2": baseline, "candidate": candidate,
              "AP50": ap50, "per_session": per_session,
              "gate_passed": gate,
              "deployed": False,
              "limits": ["postprocess of saved E2 confirmation predictions, not an independent test",
                         "historically exposed sessions", "IoU matching is not physical fire identity"]}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": baseline, "candidate": candidate,
                      "AP50": ap50, "gate_passed": gate,
                      "per_session": per_session}, ensure_ascii=False))


if __name__ == "__main__":
    main()
