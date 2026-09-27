"""Mark interrupted training runs without altering their checkpoints."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def mark(root, name):
    run = root / "runs" / name
    config_path = run / "run_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["status"] != "running" or config["purpose"] != "controlled":
        raise ValueError(f"not an active controlled run: {name}")
    with (run / "results.csv").open(encoding="utf-8") as stream:
        epochs = list(csv.DictReader(stream))
    config.update({
        "status": "interrupted_by_user",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "completed_epochs": len(epochs),
        "eligible_for_controlled_comparison": False,
        "interruption_reason": "user requested pause",
    })
    for relative in ("weights/best.pt", "weights/last.pt", "results.csv"):
        path = run / relative
        if path.is_file():
            config[relative.replace("/", "_") + "_sha256"] = digest(path)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run": name, "status": config["status"], "completed_epochs": len(epochs)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    for run_name in args.names:
        mark(args.root, run_name)
