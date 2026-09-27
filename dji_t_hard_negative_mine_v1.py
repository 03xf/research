"""Find T detections outside user-reviewed B4 source boxes in training-only images."""
import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from recovery_v1_evaluate import digest, iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    out = work / "T_hard_negative_mining_v1_complete"
    if out.exists():
        raise FileExistsError(out)
    queue_dir = root / "thermal_background_v1/review_queue_frozen_v1"
    queue_path = queue_dir / "queue.json"
    decisions_path = queue_dir / "decisions.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))["records"]
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))["decisions"]
    if len(queue) != 32:
        raise ValueError("T review cohort changed")
    os.environ["WANDB_MODE"] = "disabled"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "projects/ultralytics"))
    from ultralytics import YOLO
    weights = root / "runs/E2_T_960_s0/weights/best.pt"
    model = YOLO(str(weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    hits = []
    for row in queue:
        key = row["key"]
        decision = decisions[key]
        image = Path(row["T_image"])
        if digest(image) != row["T_sha256"] or decision["outcome"] != "usable":
            raise ValueError("reviewed image changed or unusable: " + key)
        result = model.predict(source=str(image), imgsz=960, conf=0.05,
                               iou=0.7, max_det=300, device="1", half=False,
                               save=False, verbose=False)[0]
        height, width = result.orig_shape
        truths = [box["xyxy"] for box in decision["boxes"] if box["kind"] == "source"]
        for coords, score in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
            pred = [coords[0]/width, coords[1]/height, coords[2]/width, coords[3]/height]
            best = max((iou(pred, truth) for truth in truths), default=0.0)
            if best >= 0.05 or score < 0.14:
                continue
            hits.append({"key": key, "kind": row["kind"], "session_id": row["session_id"],
                         "T_image": str(image), "V_image": row["V_image"],
                         "T_sha256": row["T_sha256"], "V_sha256": row["V_sha256"],
                         "score": round(float(score), 6), "bbox": [round(x, 6) for x in pred],
                         "max_iou_to_reviewed_source": round(best, 6),
                         "source_boxes": truths})
    hits.sort(key=lambda row: row["score"], reverse=True)
    out.mkdir(parents=True)
    (out / "candidates.json").write_text(json.dumps({"queue_sha256": digest(queue_path),
         "decisions_sha256": digest(decisions_path), "weights_sha256": digest(weights),
         "count": len(hits), "candidates": hits}, ensure_ascii=False, indent=2) + "\n",
         encoding="utf-8")
    previews = []
    for hit in hits[:24]:
        canvas = Image.new("RGB", (900, 320), "white")
        draw = ImageDraw.Draw(canvas)
        for index, sensor in enumerate(("V", "T")):
            with Image.open(hit[f"{sensor}_image"]) as source:
                thumb = source.convert("RGB")
                thumb.thumbnail((440, 275))
                canvas.paste(thumb, (index*450, 24))
                if sensor == "T":
                    box = hit["bbox"]
                    width, height = thumb.size
                    draw.rectangle((index*450+box[0]*width, 24+box[1]*height,
                                    index*450+box[2]*width, 24+box[3]*height),
                                   outline="yellow", width=3)
        draw.text((5, 3), f"{hit['key']} score={hit['score']:.3f} iou={hit['max_iou_to_reviewed_source']:.3f}", fill="black")
        previews.append(canvas)
    sheet_path = None
    if previews:
        sheet = Image.new("RGB", (1800, 320*((len(previews)+1)//2)), "white")
        for index, preview in enumerate(previews):
            sheet.paste(preview, ((index%2)*900, (index//2)*320))
        sheet_path = out / "contact_sheet.jpg"
        sheet.save(sheet_path, quality=90)
    print(json.dumps({"candidate_count": len(hits), "top": hits[:5],
                      "contact_sheet": str(sheet_path) if sheet_path else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
