"""Derive honest image-space source candidates from frozen confirmation labels."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CLASSES = {"V": ("smoke", "flame"), "T": ("hotspot",)}


def sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def labels(text, sensor, width, height):
    result = []
    for line in text.splitlines():
        if not line.strip():
            continue
        values = line.split()
        if len(values) != 5:
            raise ValueError("invalid YOLO label: " + line)
        category = int(values[0])
        if category not in range(len(CLASSES[sensor])):
            raise ValueError("invalid class: " + line)
        x, y, w, h = (float(value) for value in values[1:])
        if w <= 0 or h <= 0 or min(x - w / 2, y - h / 2) < -1e-6 or max(x + w / 2, y + h / 2) > 1 + 1e-6:
            raise ValueError("invalid bounds: " + line)
        result.append({"class": CLASSES[sensor][category],
                       "box_xyxy_px": [round((x - w / 2) * width, 2),
                                       round((y - h / 2) * height, 2),
                                       round((x + w / 2) * width, 2),
                                       round((y + h / 2) * height, 2)],
                       "box_xyxy_normalized": [round(x - w / 2, 6), round(y - h / 2, 6),
                                               round(x + w / 2, 6), round(y + h / 2, 6)]})
    return result


def main(args):
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = read_json(args.manifest)
    decisions = read_json(args.decisions)["decisions"]
    evaluation = read_json(args.evaluation)
    lrf = read_json(args.lrf)["items"]
    if evaluation["status"] != "complete" or evaluation["decisions_sha256"] != sha256(args.decisions):
        raise ValueError("confirmation labels and evaluation do not match")
    if evaluation["manifest_sha256"] != sha256(args.manifest):
        raise ValueError("confirmation manifest and evaluation do not match")
    if len(decisions) != manifest["pair_count"] or set(decisions) != {p["pair_id"] for p in manifest["pairs"]}:
        raise ValueError("incomplete frozen decisions")

    lrf_sessions = {item["session_id"] for item in lrf}
    records = []
    csv_rows = []
    counts = Counter()
    session_counts = {}
    for pair in manifest["pairs"]:
        pair_id = pair["pair_id"]
        decision = decisions[pair_id]
        if any(decision[sensor]["status"] != "complete" for sensor in CLASSES):
            raise ValueError("incomplete decision: " + pair_id)
        detections = {}
        for sensor in CLASSES:
            size = pair[sensor]["size"]
            detections[sensor] = labels(decision[sensor]["label_text"], sensor, size[0], size[1])
            for box in detections[sensor]:
                counts[box["class"]] += 1
        source_points = []
        for index, box in enumerate(detections["V"]):
            if box["class"] != "flame":
                continue
            left, _, right, bottom = box["box_xyxy_px"]
            point = [round((left + right) / 2, 2), bottom]
            source_points.append({"visible_detection_index": index,
                                  "point_xy_px": point,
                                  "coordinate_system": "V image, top-left origin",
                                  "method": "flame_box_bottom_center_proxy",
                                  "ground_contact_verified": False,
                                  "point_error_px": None,
                                  "point_error_unavailable_reason": "independent ground burning-source point labels absent"})
            csv_rows.append({"pair_id": pair_id, "session_id": pair["session_id"],
                             "visible_image": pair["V"]["file"], "source_point_x_px": point[0],
                             "source_point_y_px": point[1], "source_point_status": "heuristic_candidate",
                             "thermal_hotspot_count": sum(b["class"] == "hotspot" for b in detections["T"]),
                             "same_physical_target_status": "unverified_time_candidate",
                             "lrf_reference_wgs84": "", "absolute_visual_wgs84": ""})
        if not source_points:
            csv_rows.append({"pair_id": pair_id, "session_id": pair["session_id"],
                             "visible_image": pair["V"]["file"], "source_point_x_px": "",
                             "source_point_y_px": "", "source_point_status": "unavailable_no_visible_flame",
                             "thermal_hotspot_count": len(detections["T"]),
                             "same_physical_target_status": "unverified_time_candidate",
                             "lrf_reference_wgs84": "", "absolute_visual_wgs84": ""})
        record = {"pair_id": pair_id, "session_id": pair["session_id"],
                  "video_group": pair["video_group"],
                  "V": {"image": pair["V"]["file"], "image_sha256": pair["V"]["sha256"],
                        "pts_s": pair["V"]["pts_s"], "size": pair["V"]["size"],
                        "detections": detections["V"], "source_point_candidates": source_points},
                  "T": {"image": pair["T"]["file"], "image_sha256": pair["T"]["sha256"],
                        "pts_s": pair["T"]["pts_s"], "size": pair["T"]["size"],
                        "hotspot_candidate_regions": detections["T"]},
                  "tv_pairing": "within_50ms_time_candidate_only",
                  "same_physical_target": "unverified",
                  "lrf_reference_wgs84": None,
                  "lrf_association": "no_capture_group_for_confirmation_session" if pair["session_id"] not in lrf_sessions else "unverified",
                  "absolute_visual_wgs84": None,
                  "absolute_visual_unavailable_reason": "Matrice 4T calibration and validated target geometry absent"}
        records.append(record)
        session_counts[pair["session_id"]] = session_counts.get(pair["session_id"], 0) + 1

    args.output.mkdir(parents=True)
    details = args.output / "image_localization_records.json"
    details.write_text(json.dumps({"schema_version": "dji_confirmation_image_localization_v1",
                                   "created_utc": datetime.now(timezone.utc).isoformat(),
                                   "manifest_sha256": sha256(args.manifest),
                                   "decisions_sha256": sha256(args.decisions),
                                   "evaluation_sha256": sha256(args.evaluation),
                                   "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_file = args.output / "source_point_candidates.csv"
    with csv_file.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    summary = {"schema_version": "dji_confirmation_localization_summary_v1",
               "pair_count": len(records), "session_pair_counts": session_counts,
               "reviewed_box_counts": dict(counts),
               "visible_flame_bottom_center_candidates": counts["flame"],
               "pairs_without_visible_flame_source_candidate": sum(not r["V"]["source_point_candidates"] for r in records),
               "physically_verified_tv_pairs": 0,
               "lrf_capture_groups_for_confirmation_sessions": sum(item["session_id"] in session_counts for item in lrf),
               "verified_ground_burning_source_points": 0,
               "source_point_pixel_error": None,
               "absolute_visual_localization": "unavailable",
               "method_limit": "Flame-box lower midpoint is an image-space proxy, not a verified ground contact point.",
               "records_sha256": sha256(details), "csv_sha256": sha256(csv_file)}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--lrf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
