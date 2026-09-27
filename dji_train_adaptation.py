#!/usr/bin/env python3
"""Controlled DJI-domain micro-fine-tuning entry point.

It refuses to start until train/validation label files exist.  V and T
experiments are launched separately by passing their own dataset YAML.
"""
import argparse
import importlib.util
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys

TOOLS_DIR = Path(__file__).resolve().parent
ULTRALYTICS_ROOT = TOOLS_DIR.parent / "projects" / "ultralytics"
sys.path.insert(0, str(ULTRALYTICS_ROOT))
from ultralytics import YOLO  # noqa: E402


def yaml_text(path):
    return Path(path).read_text(encoding="utf-8")


def check_labels(data_yaml):
    preflight_path = TOOLS_DIR / "dji_yolo_dataset_preflight.py"
    spec = importlib.util.spec_from_file_location("dji_yolo_dataset_preflight", str(preflight_path))
    preflight = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preflight)
    report = preflight.inspect(Path(data_yaml))
    if report["errors"]:
        raise SystemExit("dataset preflight failed: " + "; ".join(report["errors"][:10]))
    text = yaml_text(data_yaml)
    if "train:" not in text or "val:" not in text:
        raise SystemExit("dataset YAML must define train and val")
    # Ultralytics resolves relative paths from the YAML directory.  We only
    # validate explicit label roots supplied through the usual dataset layout.
    root = Path(data_yaml).parent
    for line in text.splitlines():
        if line.strip().startswith("path:"):
            value = line.split(":", 1)[1].split("#", 1)[0].strip().strip("'\"")
            root = Path(value) if Path(value).is_absolute() else (root / value)
            break
    labels = []
    for part in ("train", "val"):
        line = next((x.strip() for x in text.splitlines() if x.strip().startswith(part + ":")), "")
        if not line:
            continue
        value = line.split(":", 1)[1].split("#", 1)[0].strip().strip("'\"")
        image_dir = (root / value) if not Path(value).is_absolute() else Path(value)
        # Standard YOLO layout is <root>/images/<split> and <root>/labels/<split>.
        labels.append(image_dir.parent.parent / "labels" / image_dir.name)
    files = [p for d in labels if d.exists() for p in d.rglob("*.txt")]
    if not files:
        raise SystemExit("no YOLO label files found; annotate DJI observations before training")
    return {"label_dirs": [str(x) for x in labels], "label_file_count": len(files), "preflight_splits": report["splits"]}


def env_snapshot():
    try:
        torch_version = __import__("torch").__version__
        cuda = __import__("torch").version.cuda
    except Exception:
        torch_version, cuda = None, None
    return {"python": sys.version, "platform": platform.platform(), "torch": torch_version, "cuda": cuda, "hostname": platform.node()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--sensor", choices=("V", "T"), required=True)
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--freeze", type=int, default=10)
    ap.add_argument("--lr0", type=float, default=0.001)
    ap.add_argument("--device", default="0")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", action="store_true", help="cap the run to 1 epoch")
    args = ap.parse_args()
    if not args.weights.exists():
        raise SystemExit(f"weights not found: {args.weights}")
    if not args.data.exists():
        raise SystemExit(f"dataset YAML not found: {args.data}")
    label_info = check_labels(args.data)
    epochs = 1 if args.smoke else args.epochs
    args.project.mkdir(parents=True, exist_ok=True)
    run_dir = args.project / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    config = {"sensor": args.sensor, "base_weights": str(args.weights), "dataset": str(args.data), "epochs": epochs, "imgsz": args.imgsz, "batch": args.batch, "freeze": args.freeze, "lr0": args.lr0, "device": args.device, "workers": args.workers, "seed": args.seed, "label_info": label_info, "environment": env_snapshot(), "started_utc": datetime.now(timezone.utc).isoformat()}
    (run_dir / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    model = YOLO(str(args.weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    model.train(data=str(args.data), epochs=epochs, imgsz=args.imgsz, batch=args.batch, freeze=args.freeze, lr0=args.lr0, device=args.device, workers=args.workers, seed=args.seed, project=str(args.project), name=args.name, exist_ok=True)
    config["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
