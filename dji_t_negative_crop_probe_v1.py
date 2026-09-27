"""Probe source-free thermal crops from reviewed B4 training frames for hard negatives."""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from recovery_v1_evaluate import digest, iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    out = work / "T_negative_crop_probe_v1"
    if out.exists():
        raise FileExistsError(out)
    queue_path = root / "thermal_background_v1/review_queue_frozen_v1/queue.json"
    decisions_path = root / "thermal_background_v1/review_queue_frozen_v1/decisions.json"
    records = json.loads(queue_path.read_text(encoding="utf-8"))["records"]
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))["decisions"]
    if len(records) != 32:
        raise ValueError("review cohort changed")
    os.environ["WANDB_MODE"] = "disabled"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "projects/ultralytics"))
    from ultralytics import YOLO
    weights = root / "runs/E2_T_960_s0/weights/best.pt"
    model = YOLO(str(weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    out.mkdir(parents=True)
    hits = []
    tested = 0
    for record in records:
        key = record["key"]
        decision = decisions[key]
        image = Path(record["T_image"])
        if digest(image) != record["T_sha256"] or decision["outcome"] != "usable":
            raise ValueError("review source changed: " + key)
        sources = [box["xyxy"] for box in decision["boxes"] if box["kind"] == "source"]
        with Image.open(image) as original:
            original = original.convert("RGB")
            width, height = original.size
            for x in (0.0, 0.3, 0.6):
                for y in (0.0, 0.3, 0.6):
                    region = [x, y, x+0.4, y+0.4]
                    # No visible or heat-source label may intersect this crop.
                    if any(iou(region, source) > 0.0 or
                           (max(region[0], source[0]) < min(region[2], source[2])
                            and max(region[1], source[1]) < min(region[3], source[3]))
                           for source in sources):
                        continue
                    crop = original.crop((round(x*width), round(y*height),
                                          round((x+0.4)*width), round((y+0.4)*height)))
                    result = model.predict(source=np.asarray(crop)[:, :, ::-1].copy(),
                                           imgsz=960, conf=0.14, iou=0.7,
                                           max_det=100, device="1", half=False,
                                           save=False, verbose=False)[0]
                    tested += 1
                    if not len(result.boxes):
                        continue
                    scores = result.boxes.conf.cpu().tolist()
                    best_index = max(range(len(scores)), key=lambda index: scores[index])
                    box = result.boxes.xyxy.cpu().tolist()[best_index]
                    name = f"{key}_{round(x*10)}{round(y*10)}"
                    crop_path = out / (name + ".jpg")
                    crop.save(crop_path, quality=95)
                    hits.append({"key": key, "session_id": record["session_id"],
                                 "T_image": str(image), "V_image": record["V_image"],
                                 "T_sha256": record["T_sha256"], "crop": region,
                                 "crop_file": str(crop_path), "crop_sha256": digest(crop_path),
                                 "best_score": round(float(scores[best_index]), 6),
                                 "best_box_px": [round(v, 2) for v in box],
                                 "prediction_count": len(scores)})
    hits.sort(key=lambda row: row["best_score"], reverse=True)
    (out / "candidates.json").write_text(json.dumps({"queue_sha256": digest(queue_path),
        "decisions_sha256": digest(decisions_path), "weights_sha256": digest(weights),
        "tested_source_free_crops": tested, "candidate_count": len(hits),
        "candidates": hits}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tiles = []
    for hit in hits[:32]:
        tile = Image.new("RGB", (1000, 280), "white")
        draw = ImageDraw.Draw(tile)
        for index, name in enumerate(("V_image", "T_image", "crop_file")):
            with Image.open(hit[name]) as src:
                preview = src.convert("RGB")
                preview.thumbnail((320, 245))
                tile.paste(preview, (index*330, 25))
                if name == "T_image":
                    x1, y1, x2, y2 = hit["crop"]
                    draw.rectangle((330+x1*preview.width, 25+y1*preview.height,
                                    330+x2*preview.width, 25+y2*preview.height),
                                   outline="yellow", width=3)
                if name == "crop_file":
                    x1, y1, x2, y2 = hit["best_box_px"]
                    with Image.open(hit[name]) as full_crop:
                        fx, fy = full_crop.size
                    draw.rectangle((660+x1*preview.width/fx, 25+y1*preview.height/fy,
                                    660+x2*preview.width/fx, 25+y2*preview.height/fy),
                                   outline="red", width=3)
        draw.text((5, 3), f"{hit['key']} score={hit['best_score']:.3f} crop={hit['crop']}", fill="black")
        tiles.append(tile)
    if tiles:
        sheet = Image.new("RGB", (2000, 280*((len(tiles)+1)//2)), "white")
        for index, tile in enumerate(tiles):
            sheet.paste(tile, ((index%2)*1000, (index//2)*280))
        sheet.save(out / "contact_sheet.jpg", quality=90)
    print(json.dumps({"tested_crops": tested, "candidate_count": len(hits),
                      "top": hits[:5]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
