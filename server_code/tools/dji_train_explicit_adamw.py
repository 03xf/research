#!/usr/bin/env python3
"""Separate, provenance-rich DJI training entry point with explicit AdamW."""
import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parent / "projects" / "ultralytics"))
from ultralytics import YOLO


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--epochs", type=int, required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr0", type=float, default=0.0005)
    ap.add_argument("--weight-decay", type=float, default=0.0005)
    ap.add_argument("--device", default="0")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if not args.weights.is_file() or not args.data.is_file():
        raise SystemExit("missing weights or dataset YAML")
    run = args.project / args.name
    if run.exists():
        raise SystemExit("run directory exists; refusing to overwrite")
    run.mkdir(parents=True)
    import torch
    config = {"base_weights": str(args.weights), "base_weights_sha256": sha(args.weights), "data": str(args.data), "data_yaml_sha256": sha(args.data), "epochs": args.epochs, "imgsz": args.imgsz, "batch": args.batch, "freeze": 0, "optimizer": "AdamW", "lr0": args.lr0, "weight_decay": args.weight_decay, "device": args.device, "workers": args.workers, "seed": args.seed, "validation_split_only": True, "blind_test_accessed": False, "environment": {"python": sys.version, "platform": platform.platform(), "torch": torch.__version__, "cuda": torch.version.cuda}, "started_utc": datetime.now(timezone.utc).isoformat()}
    (run / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    model = YOLO(str(args.weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    model.train(data=str(args.data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, freeze=0, optimizer="AdamW", lr0=args.lr0, weight_decay=args.weight_decay, device=args.device, workers=args.workers, seed=args.seed, project=str(args.project), name=args.name, exist_ok=True)
    config["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (run / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
