"""Exploratory B4-priority T hotspot tracking and source-point comparison."""
import argparse
import collections
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dji_source_truth_eval_v2 import matched
from recovery_v1_evaluate import digest, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--selection", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--tracker", type=Path, required=True)
    ap.add_argument("--device", default="1")
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = args.root.resolve()
    queue_path = root / "source_truth_review_v1/queue.json"
    truth_path = root / "source_truth_review_v1/decisions.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))["decisions"]
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    selected = next((x for x in selection["candidates"] if x["mode"] == selection["selected_mode"]), None)
    if selected is None or not selected["eligible"]:
        raise ValueError("no development-qualified T candidate")
    weights = Path(selected["weights"])
    evaluation_path = Path(selected["evaluation"])
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if (digest(weights) != selected["weights_sha256"]
            or digest(evaluation_path) != selected["evaluation_sha256"]
            or evaluation["classes"][0]["work_threshold"] != selected["threshold"]
            or len(queue["tasks"]) != 50 or set(truth) != {x["task_id"] for x in queue["tasks"]}):
        raise ValueError("candidate or point cohort changed")
    sys.path.insert(0, "/home/member/xmy/xmy/code/projects/ultralytics")
    import cv2
    import recovery_v1_track_clips_v2 as track

    args.output.mkdir(parents=True)
    track_rows = {}
    summaries = {}
    for clip in queue["clips"]:
        clip_id = clip["clip_id"]
        start = time.monotonic()
        summary = track.run_sensor(root / "video_clips" / clip_id, "T", weights,
                                   evaluation, args.output / clip_id / "T", 960,
                                   args.device, args.tracker)
        elapsed = time.monotonic() - start
        summaries[clip_id] = {**summary, "processing_seconds": elapsed,
                              "processing_fps": summary["frames"] / elapsed}
        path = args.output / clip_id / "T/detections.json"
        track_rows[clip_id] = {x["frame_file"]: x for x in json.loads(path.read_text())["rows"]}
    by_clip = collections.defaultdict(collections.Counter)
    by_batch = collections.defaultdict(collections.Counter)
    totals = collections.Counter()
    rows = []
    batch_by_clip = {x["clip_id"]: x["source"]["batch_id"] for x in queue["clips"]}
    for task in queue["tasks"]:
        decision = truth[task["task_id"]]
        if decision["frame_status"] != "usable":
            continue
        clip_id = task["clip_id"]
        frame = Path(task["thermal_frame"])
        frame_result = track_rows[clip_id].get(frame.name)
        if frame_result is None:
            raise ValueError("point frame missing in track result: " + str(frame))
        image = cv2.imread(str(frame))
        if image is None:
            raise ValueError("point frame unreadable: " + str(frame))
        height, width = image.shape[:2]
        detections = [x for x in frame_result["detections"] if x["class_name"] == "hotspot"]
        eligible = decision["source_state"] in ("active_fire", "residual_heat")
        points = decision["T"]["points"] if eligible else []
        pairs = matched(points, detections, width, height)
        row = {"task_id": task["task_id"], "clip_id": clip_id,
               "batch": batch_by_clip[clip_id], "source_state": decision["source_state"],
               "truth": len(points), "matched": len(pairs), "missed": len(points)-len(pairs),
               "detections": len(detections),
               "negative_frame_with_detection": int(not points and bool(detections))}
        rows.append(row)
        for counter in (totals, by_clip[clip_id], by_batch[batch_by_clip[clip_id]]):
            for name in ("truth", "matched", "missed", "detections", "negative_frame_with_detection"):
                counter[name] += row[name]
    if totals["truth"] != 72 or by_batch["B4"]["truth"] != 52:
        raise ValueError("T truth support changed")
    result = {"schema_version": "dji_b4_thermal_tracking_point_eval_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "exploratory_historically_exposed": True,
              "method": "same ByteTrack and point-inside-box greedy one-to-one matching as E2; T active-fire and residual-heat points",
              "baseline_E2": {"matched": "54/72", "B4_matched": "34/52", "negative_frames_with_detection": 9},
              "selection_sha256": digest(args.selection),
              "truth_queue_sha256": digest(queue_path), "truth_decisions_sha256": digest(truth_path),
              "tracker_sha256": digest(args.tracker),
              "totals": dict(totals), "by_batch": {k: dict(v) for k, v in by_batch.items()},
              "by_clip": {k: dict(v) for k, v in by_clip.items()},
              "tracking": summaries, "rows": rows}
    write_json(args.output / "result.json", result)
    print(json.dumps({"totals": dict(totals), "B4": dict(by_batch["B4"]),
                      "minimum_processing_fps": min(x["processing_fps"] for x in summaries.values())},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
