"""Render representative paired confirmation annotations without changing labels."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


COLORS = {"smoke": (0, 215, 255), "flame": (0, 80, 255), "hotspot": (255, 220, 0)}


def box_area(box):
    x1, y1, x2, y2 = box["box_xyxy_px"]
    return max(0, x2 - x1) * max(0, y2 - y1)


def render(record, output):
    panels = []
    for sensor in ("V", "T"):
        info = record[sensor]
        image = cv2.imread(info["image"])
        if image is None:
            raise ValueError("unreadable image: " + info["image"])
        boxes = info["detections"] if sensor == "V" else info["hotspot_candidate_regions"]
        for item in boxes:
            x1, y1, x2, y2 = (round(v) for v in item["box_xyxy_px"])
            color = COLORS[item["class"]]
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 4)
            cv2.putText(image, item["class"], (x1, max(35, y1 - 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv2.LINE_AA)
        if sensor == "V":
            for point in info["source_point_candidates"]:
                x, y = (round(v) for v in point["point_xy_px"])
                cv2.drawMarker(image, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 32, 5)
        width = round(540 * image.shape[1] / image.shape[0])
        panels.append(cv2.resize(image, (width, 540), interpolation=cv2.INTER_AREA))
    canvas = np.full((595, sum(p.shape[1] for p in panels), 3), 245, dtype=np.uint8)
    x = 0
    for panel in panels:
        canvas[:540, x:x + panel.shape[1]] = panel
        x += panel.shape[1]
    cv2.putText(canvas, record["pair_id"] + " | V: red cross = flame-bottom proxy; T: hotspot region",
                (16, 577), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (35, 35, 35), 2, cv2.LINE_AA)
    if not cv2.imwrite(str(output), canvas):
        raise RuntimeError("failed to write " + str(output))


def main(args):
    if args.output.exists():
        raise FileExistsError(args.output)
    records = json.loads(args.records.read_text(encoding="utf-8"))["records"]
    sessions = defaultdict(list)
    for record in records:
        sessions[record["session_id"]].append(record)
    selected = {}
    for session, rows in sessions.items():
        for category in ("flame", "smoke"):
            scored = [(sum(box_area(box) for box in row["V"]["detections"]
                           if box["class"] == category), row) for row in rows]
            value, row = max(scored, key=lambda item: item[0])
            if value > 0:
                selected[row["pair_id"]] = row
    for row in records:
        if row["pair_id"] == "confirm_2_0089":
            selected[row["pair_id"]] = row
    args.output.mkdir(parents=True)
    for pair_id, record in sorted(selected.items()):
        render(record, args.output / (pair_id + ".png"))
    print(json.dumps({"previews": sorted(selected), "count": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
