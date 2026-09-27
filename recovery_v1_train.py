"""Explicit, provenance-rich training entry point for the recovery dataset."""

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
import yaml


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["COMET_MODE"] = "DISABLED"
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--epochs", type=int, required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="0")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--purpose", choices=("diagnostic", "controlled"), default="diagnostic")
    args = ap.parse_args()
    if not args.weights.is_file() or not args.data.is_file():
        raise SystemExit("weights or data YAML missing")
    provenance = {}
    if args.purpose == "controlled":
        dataset = args.data.parent.parent.resolve()
        manifest_path = dataset / "manifest.json"
        snapshot = dataset / "review_decisions_snapshot.json"
        if not manifest_path.is_file() or not snapshot.is_file():
            raise SystemExit("controlled training requires dataset manifest and frozen review snapshot")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data_config = yaml.safe_load(args.data.read_text(encoding="utf-8"))
        if (Path(manifest["derived_dataset"]).resolve() != dataset
                or Path(data_config["path"]).resolve() != args.data.parent.resolve()
                or manifest["review_decisions_sha256"] != sha(snapshot)):
            raise SystemExit("controlled training dataset provenance mismatch")
        provenance = {"dataset_manifest_sha256": sha(manifest_path),
                      "review_decisions_sha256": sha(snapshot),
                      "legacy_positive_unreviewed": manifest["legacy_positive_unreviewed"]}
    run = args.project / args.name
    if run.exists():
        raise SystemExit(f"refusing to overwrite {run}")
    run.mkdir(parents=True)
    config = {
        "status": "running", "purpose": args.purpose,
        "base_weights": str(args.weights), "base_weights_sha256": sha(args.weights),
        "data": str(args.data), "data_yaml_sha256": sha(args.data),
        "entrypoint_sha256": sha(Path(__file__)), **provenance,
        "epochs": args.epochs, "imgsz": args.imgsz, "batch": args.batch,
        "optimizer": "AdamW", "lr0": 0.001, "weight_decay": 0.0005,
        "device": args.device, "workers": args.workers, "seed": args.seed,
        "amp": False, "cache": False, "deterministic": True,
        "validation_split_only": True, "blind_test_accessed": False,
        "environment": {"python": sys.version, "platform": platform.platform(),
                         "torch": torch.__version__, "cuda": torch.version.cuda},
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    (run / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    project = Path(__file__).resolve().parents[1] / "projects" / "ultralytics"
    sys.path.insert(0, str(project))
    from ultralytics import YOLO
    model = YOLO(str(args.weights))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    try:
        model.train(data=str(args.data), epochs=args.epochs, imgsz=args.imgsz,
                    batch=args.batch, freeze=0, optimizer="AdamW", lr0=0.001,
                    weight_decay=0.0005, device=args.device, workers=args.workers,
                    seed=args.seed, deterministic=True, amp=False, cache=False,
                    project=str(args.project), name=args.name, exist_ok=True,
                    verbose=False)
    except Exception as exc:
        config.update({"status": "failed", "error": repr(exc)})
        config["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (run / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
        raise
    config.update({"status": "complete", "finished_utc": datetime.now(timezone.utc).isoformat()})
    for name in ("weights/best.pt", "weights/last.pt", "results.csv", "args.yaml"):
        path = run / name
        if path.is_file():
            config[name.replace("/", "_") + "_sha256"] = sha(path)
    (run / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"run": str(run), "status": config["status"]}))


if __name__ == "__main__":
    main()
