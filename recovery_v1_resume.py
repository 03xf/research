"""Resume an interrupted controlled run from its saved optimizer checkpoint."""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_config(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["COMET_MODE"] = "DISABLED"
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    path = run / "run_config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["purpose"] != "controlled" or config["status"] not in ("running", "resume_failed"):
        raise ValueError("expected an interrupted controlled run")
    if config["epochs"] != 100 or config["batch"] != 8:
        raise ValueError("run differs from the frozen protocol")
    data = Path(config["data"])
    if digest(data) != config["data_yaml_sha256"]:
        raise ValueError("dataset YAML changed")
    last = run / "weights/last.pt"
    if not last.is_file():
        raise FileNotFoundError(last)
    with (run / "results.csv").open(encoding="utf-8") as stream:
        completed = len(list(csv.DictReader(stream)))
    if not 0 < completed < config["epochs"]:
        raise ValueError("epoch count is not resumable")
    config["status"] = "running"
    config["resumed_from_completed_epochs"] = completed
    config["resume_checkpoint_sha256"] = digest(last)
    config["resume_entrypoint_sha256"] = digest(Path(__file__))
    config["resumed_utc"] = datetime.now(timezone.utc).isoformat()
    write_config(path, config)
    project = Path(__file__).resolve().parents[1] / "projects" / "ultralytics"
    sys.path.insert(0, str(project))
    from ultralytics import YOLO

    model = YOLO(str(last))
    for module in model.model.modules():
        if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
            module.approximate = "none"
    try:
        model.train(resume=str(last), device=config["device"])
    except BaseException as error:
        config.update({"status": "resume_failed", "error": repr(error),
                       "finished_utc": datetime.now(timezone.utc).isoformat()})
        write_config(path, config)
        raise
    with (run / "results.csv").open(encoding="utf-8") as stream:
        final_epochs = len(list(csv.DictReader(stream)))
    if final_epochs != config["epochs"]:
        raise ValueError(f"resumed run ended after {final_epochs} epochs")
    config.update({"status": "complete", "error": None,
                   "eligible_for_controlled_comparison": True,
                   "finished_utc": datetime.now(timezone.utc).isoformat(),
                   "completed_epochs": final_epochs})
    for relative in ("weights/best.pt", "weights/last.pt", "results.csv", "args.yaml"):
        artifact = run / relative
        if artifact.is_file():
            config[relative.replace("/", "_") + "_sha256"] = digest(artifact)
    write_config(path, config)
    print(json.dumps({"run": str(run), "status": "complete", "epochs": final_epochs}))


if __name__ == "__main__":
    main()
