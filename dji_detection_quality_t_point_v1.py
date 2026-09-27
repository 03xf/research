"""Fixed T NMS/threshold point comparison on the existing 50 reviewed pairs."""
import argparse
import collections
import json
from datetime import datetime, timezone
from pathlib import Path

from dji_source_truth_eval_v2 import matched
from recovery_v1_evaluate import digest, iou


def filter_boxes(boxes):
    kept = []
    for box in sorted((x for x in boxes if x["class_name"] == "hotspot"
                       and x["confidence"] >= 0.15),
                      key=lambda item: item["confidence"], reverse=True):
        if all(iou(box["bbox_xyxy_px"], old["bbox_xyxy_px"]) <= 0.45 for old in kept):
            kept.append(box)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    out = work / "T_source_points_fixed_v1.json"
    if out.exists():
        raise FileExistsError(out)
    freeze_path = work / "development_selection_v1.json"
    confirmation_path = work / "T_confirmation_fixed_v1.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze["T_selected"]["threshold"] != 0.15 or not confirmation_path.is_file():
        raise ValueError("T candidate not frozen or confirmation not done")
    queue_path = root / "source_truth_review_v1/queue.json"
    decisions_path = root / "source_truth_review_v1/decisions.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))["tasks"]
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))["decisions"]
    counts = collections.Counter()
    by_batch = collections.defaultdict(collections.Counter)
    by_state = collections.defaultdict(collections.Counter)
    rows = []
    import cv2
    for task in queue:
        choice = decisions[task["task_id"]]
        if choice["frame_status"] != "usable":
            continue
        frame = Path(task["thermal_frame"])
        path = root / "tracking_v2" / (task["clip_id"] + "_E2_s0") / "T/detections.json"
        tracking = json.loads(path.read_text(encoding="utf-8"))["rows"]
        row = next((item for item in tracking if item["frame_file"] == frame.name), None)
        if row is None:
            raise ValueError("tracking frame absent: " + str(frame))
        image = cv2.imread(str(frame))
        if image is None:
            raise FileNotFoundError(frame)
        height, width = image.shape[:2]
        state = choice["source_state"]
        points = choice["T"]["points"] if state in ("active_fire", "residual_heat") else []
        before = [x for x in row["detections"] if x["class_name"] == "hotspot"]
        after = filter_boxes(before)
        old_pairs = matched(points, before, width, height)
        new_pairs = matched(points, after, width, height)
        batch = "B4" if task["clip_id"].startswith(("multiple_boxes", "paired_negative", "visible_")) else "B3"
        for counter in (counts, by_batch[batch], by_state[state]):
            counter["truth"] += len(points)
            counter["baseline_matched"] += len(old_pairs)
            counter["candidate_matched"] += len(new_pairs)
            counter["baseline_detections"] += len(before)
            counter["candidate_detections"] += len(after)
            if not points and before:
                counter["baseline_no_point_frame_with_detection"] += 1
            if not points and after:
                counter["candidate_no_point_frame_with_detection"] += 1
        rows.append({"task_id": task["task_id"], "clip_id": task["clip_id"],
                     "batch": batch, "state": state,
                     "truth": len(points), "baseline_matched": len(old_pairs),
                     "candidate_matched": len(new_pairs),
                     "baseline_detections": len(before), "candidate_detections": len(after)})
    result = {"schema_version": "dji_b4_T_point_fixed_comparison_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "freeze_sha256": digest(freeze_path),
              "confirmation_sha256": digest(confirmation_path),
              "source_queue_sha256": digest(queue_path),
              "source_decisions_sha256": digest(decisions_path),
              "rule": "E2 T tracking boxes; extra NMS 0.45 and confidence >=0.15; no retracking",
              "totals": dict(counts), "by_batch": {k: dict(v) for k, v in by_batch.items()},
              "by_state": {k: dict(v) for k, v in by_state.items()}, "rows": rows,
              "limits": "The 50 pairs are historically exposed; no-point detections are not necessarily nonfire. Source coverage differs from detector IoU metrics."}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"totals": result["totals"], "by_batch": result["by_batch"],
                      "by_state": result["by_state"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
