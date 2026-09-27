#!/usr/bin/env python3
"""Reproduce the legacy smoke detector and run inference on new sources."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

TOOLS_DIR = Path(__file__).resolve().parent
ULTRALYTICS_ROOT = TOOLS_DIR.parent / "projects" / "ultralytics"
sys.path.insert(0, str(ULTRALYTICS_ROOT))

from ultralytics import YOLO  # noqa: E402


def load_model(weights: str) -> YOLO:
    model = YOLO(weights)
    # Older checkpoints can deserialize GELU without the attribute expected by
    # torch 2.4. This is a checkpoint compatibility fix, not a model change.
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    return model


def run_validation(args: argparse.Namespace) -> Dict[str, Any]:
    model = load_model(args.weights)
    metrics = model.val(
        data=args.data,
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=args.device,
        project=args.project,
        name=args.name,
        exist_ok=True,
        plots=args.plots,
    )
    result = {str(k): float(v) for k, v in metrics.results_dict.items()}
    output_dir = Path(args.project) / args.name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def run_prediction(args: argparse.Namespace) -> None:
    model = load_model(args.weights)
    results = model.predict(
        source=args.source,
        imgsz=args.imgsz,
        device=args.device,
        conf=args.conf,
        project=args.project,
        name=args.name,
        exist_ok=True,
        save=args.save,
        save_txt=args.save_txt,
        stream=True,
        vid_stride=args.vid_stride,
        verbose=True,
    )
    output_dir = Path(args.project) / args.name
    output_dir.mkdir(parents=True, exist_ok=True)
    detections = []
    for result in results:
        boxes = result.boxes
        detections.append(
            {
                "source": str(result.path),
                "boxes": boxes.xyxy.detach().cpu().tolist() if boxes is not None else [],
                "confidence": boxes.conf.detach().cpu().tolist() if boxes is not None else [],
                "class": boxes.cls.detach().cpu().tolist() if boxes is not None else [],
            }
        )
    (output_dir / "detections.json").write_text(
        json.dumps(detections, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"saved {len(detections)} frame records to {output_dir / 'detections.json'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--mode", choices=("val", "predict"), default="val")
    parser.add_argument("--split", default="val")
    parser.add_argument("--source")
    parser.add_argument("--project", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--device", default="0")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--save-txt", action="store_true")
    parser.add_argument("--plots", action="store_true")
    parser.add_argument("--vid-stride", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.mode == "predict" and not args.source:
        raise SystemExit("--source is required for --mode predict")
    if args.mode == "val":
        run_validation(args)
    else:
        run_prediction(args)


if __name__ == "__main__":
    main()
