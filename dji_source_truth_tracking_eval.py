"""Compare completed source truth points with frozen E2 tracking outputs."""

from __future__ import annotations

import argparse
import collections
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def image_size(path: Path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        import cv2
        im = cv2.imread(str(path))
        if im is None:
            raise ValueError(f"unreadable image: {path}")
        return im.shape[1], im.shape[0]


def point_inside(point, box, width, height):
    x, y = point[0] * width, point[1] * height
    x1, y1, x2, y2 = box
    return x1 <= x <= x2 and y1 <= y <= y2


def distance_to_candidate(point, detection, width, height):
    candidate = detection.get("source_point_image_normalized")
    if not candidate:
        box = detection["bbox_xyxy_px"]
        candidate = [((box[0] + box[2]) / 2) / width, box[3] / height]
    return math.hypot(point[0] - candidate[0], point[1] - candidate[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True, help="recovery_v1 directory")
    args = ap.parse_args()
    root = args.root
    truth_root = root / "source_truth_review_v1"
    queue = json.loads((truth_root / "queue.json").read_text(encoding="utf-8"))
    decisions = json.loads((truth_root / "decisions.json").read_text(encoding="utf-8"))["decisions"]
    tasks = {row["task_id"]: row for row in queue["tasks"]}
    tracking = {}
    for manifest in (root / "tracking_v2").glob("*/manifest.json"):
        if "_E2_s0" not in manifest.parent.name:
            continue
        clip = manifest.parent.name[:-len("_E2_s0")]
        tracking[clip] = {}
        for sensor in ("V", "T"):
            path = manifest.parent / sensor / "detections.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                tracking[clip][sensor] = {row["frame_file"]: row for row in data["rows"]}

    rows = []
    sensor_summary = collections.Counter()
    relation_summary = collections.Counter()
    same_source_summary = collections.Counter()
    clip_summary = collections.defaultdict(collections.Counter)
    distance_values = collections.defaultdict(list)
    for task_id, decision in decisions.items():
        task = tasks[task_id]
        clip = task["clip_id"]
        clip_track = tracking.get(clip, {})
        pair_result = {"task_id": task_id, "clip_id": clip, "source_state": decision.get("source_state"),
                       "tv_relation": decision.get("tv_relation"), "frame_status": decision.get("frame_status"),
                       "sensors": {}}
        relation_summary[decision.get("tv_relation")] += 1
        for sensor, frame_key in (("V", "visible_frame"), ("T", "thermal_frame")):
            frame_name = Path(task[frame_key]).name
            truth_points = decision.get(sensor, {}).get("points", [])
            row = clip_track.get(sensor, {}).get(frame_name, {"detections": []})
            detections = [d for d in row.get("detections", []) if d.get("class_name") == ("flame" if sensor == "V" else "hotspot")]
            width, height = image_size(Path(task[frame_key]))
            matches = []
            for point in truth_points:
                inside = [d for d in detections if point_inside(point, d["bbox_xyxy_px"], width, height)]
                ranked = sorted(detections, key=lambda d: distance_to_candidate(point, d, width, height))
                best = inside[0] if inside else (ranked[0] if ranked else None)
                distance = distance_to_candidate(point, best, width, height) if best else None
                matches.append({"fire_id": point[2], "matched": bool(inside), "track_id": best.get("track_id") if best and inside else None,
                                "nearest_distance_norm": distance, "detection_count": len(detections)})
                if distance is not None:
                    distance_values[sensor].append(distance)
                sensor_summary[f"{sensor}_{'matched' if inside else 'missed'}"] += 1
            false_positive = not truth_points and bool(detections)
            if false_positive:
                sensor_summary[f"{sensor}_false_positive_no_truth"] += 1
            sensor_summary[f"{sensor}_frames_with_truth"] += bool(truth_points)
            sensor_summary[f"{sensor}_frames_with_detection"] += bool(detections)
            pair_result["sensors"][sensor] = {"frame_file": frame_name, "truth_points": truth_points,
                                                "detections": detections, "matches": matches,
                                                "false_positive_no_truth": false_positive}
            clip_summary[clip][f"{sensor}_truth_points"] += len(truth_points)
            clip_summary[clip][f"{sensor}_matched_points"] += sum(m["matched"] for m in matches)
            clip_summary[clip][f"{sensor}_frames_with_detection"] += bool(detections)
        if decision.get("tv_relation") == "same_source":
            v_ok = any(m["matched"] for m in pair_result["sensors"]["V"]["matches"])
            t_ok = any(m["matched"] for m in pair_result["sensors"]["T"]["matches"])
            same_source_summary["total"] += 1
            same_source_summary["V_detected"] += v_ok
            same_source_summary["T_detected"] += t_ok
            same_source_summary["both_detected"] += v_ok and t_ok
        rows.append(pair_result)

    def stats(values):
        if not values:
            return {"count": 0, "mean": None, "median": None, "p95": None}
        vals = sorted(values)
        return {"count": len(vals), "mean": sum(vals) / len(vals), "median": vals[len(vals)//2], "p95": vals[min(len(vals)-1, math.ceil(len(vals)*0.95)-1)]}

    summary = {"schema_version": "dji_source_truth_tracking_eval_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
               "truth_summary": str(truth_root / "summary.json"), "rows": len(rows),
               "sensor_summary": dict(sensor_summary), "relation_summary": dict(relation_summary),
               "same_source_pair_summary": dict(same_source_summary),
               "candidate_point_distance_norm": {sensor: stats(values) for sensor, values in distance_values.items()},
               "clip_summary": {clip: dict(counter) for clip, counter in sorted(clip_summary.items())},
               "interpretation": "inside_bbox is the primary diagnostic match; unknown relations are excluded from same-source accuracy; this is not a detector re-evaluation or geographic localization accuracy.",
               "tracking_truth_ready": True}
    out = truth_root / "tracking_evaluation.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = ["# 火源真值与冻结跟踪结果对照", "", f"人工真值对：{len(rows)} 对。", "", "## 总体诊断", ""]
    report.append(f"- V 真值点匹配：{sensor_summary.get('V_matched', 0)}；漏匹配：{sensor_summary.get('V_missed', 0)}。")
    report.append(f"- T 真值点匹配：{sensor_summary.get('T_matched', 0)}；漏匹配：{sensor_summary.get('T_missed', 0)}。")
    report.append(f"- 无真值点但有检测的 V 帧：{sensor_summary.get('V_false_positive_no_truth', 0)}；T 帧：{sensor_summary.get('T_false_positive_no_truth', 0)}。")
    report.append(f"- 人工确认同一火源的 42 对中，V 覆盖 {same_source_summary.get('V_detected', 0)} 对，T 覆盖 {same_source_summary.get('T_detected', 0)} 对，V/T 同时覆盖 {same_source_summary.get('both_detected', 0)} 对。")
    report.append(f"- V 候选点距离统计：{stats(distance_values.get('V', []))}。")
    report.append(f"- T 候选点距离统计：{stats(distance_values.get('T', []))}。")
    report += ["", "`inside_bbox` 只用于诊断检测是否覆盖人工源点；未确认同源关系不计入同源准确率，也不产生经纬度误差。", ""]
    (truth_root / "TRACKING_EVALUATION.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"output": str(out), "report": str(truth_root / 'TRACKING_EVALUATION.md'), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
