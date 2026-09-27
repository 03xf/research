#!/usr/bin/env python3
"""Long-running DJI adaptation pipeline.

The process waits for an explicit ANNOTATION_READY marker.  Once the reviewed
manifest passes validation it builds V/T datasets, runs smoke and short
training, validates the resulting weights, and performs resumable adapted
inference.  It never starts from partial/unlabeled annotations.
"""
import json
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/home/member/xmy/xmy")
RESULTS = BASE / "results/dji_all_batches"
ADAPT = BASE / "results/dji_adaptation"
TOOLS = BASE / "code/tools"
MARKER = RESULTS / "ANNOTATION_READY"
MANIFEST = RESULTS / "annotation_manifest.json"
FRAMES = RESULTS / "annotation_frames/frames_index.json"
DATA_ROOT = Path("/home/member/xmy/data/苏州放火_实验数据集")
BASE_WEIGHTS = BASE / "weights/detection/ultralytics/train/exp69/weights/best.pt"
PY = "/home/member/bin/python"
LOG = ADAPT / "orchestrator.log"
STATE = ADAPT / "orchestrator_state.json"


def log(message):
    ADAPT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(datetime.now(timezone.utc).isoformat() + " " + message + "\n")
    print(message, flush=True)


def run(cmd):
    log("$ " + " ".join(map(str, cmd)))
    with LOG.open("a", encoding="utf-8") as fh:
        return subprocess.run([str(x) for x in cmd], stdout=fh, stderr=subprocess.STDOUT, check=False).returncode


def write_state(status, **extra):
    payload = {"status": status, "updated_utc": datetime.now(timezone.utc).isoformat(), **extra}
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    frames = json.loads(FRAMES.read_text(encoding="utf-8")).get("frames", {})
    counts = Counter()
    errors = []
    for obs in data.get("observations", []):
        ann = obs.get("annotation", {})
        quality = ann.get("annotation_quality")
        counts[quality] += 1
        if quality not in {"clear", "weak", "ambiguous", "unusable"}:
            errors.append((obs.get("observation_id"), "annotation_quality"))
            continue
        for key, allowed in (("visible_labels", {"smoke", "flame"}), ("thermal_labels", {"hotspot"})):
            for label in ann.get(key, []) or []:
                if not isinstance(label, dict) or label.get("class") not in allowed:
                    errors.append((obs.get("observation_id"), key))
                box = label.get("bbox_xyxy") if isinstance(label, dict) else None
                if box is not None and (not isinstance(box, list) or len(box) != 4):
                    errors.append((obs.get("observation_id"), "bbox"))
        if obs.get("observation_id") not in frames:
            errors.append((obs.get("observation_id"), "frame_missing"))
    return data, counts, errors


def batch_roots(inventory):
    roots = {}
    data_root = Path(inventory.get("data_root", DATA_ROOT))
    for group in inventory.get("groups", []):
        for source in (group.get("thermal_video"), group.get("visible_video")):
            if not source:
                continue
            try:
                rel = Path(source).relative_to(data_root)
                roots[group["batch_id"]] = data_root / rel.parts[0]
            except Exception:
                continue
    return roots


def find_best(run_dir):
    best = run_dir / "weights/best.pt"
    return best if best.exists() else None


def main():
    ADAPT.mkdir(parents=True, exist_ok=True)
    write_state("waiting_for_annotation_marker")
    log("orchestrator started; waiting for " + str(MARKER))
    while True:
        if not MARKER.exists():
            time.sleep(60)
            continue
        try:
            manifest, counts, errors = validate_manifest()
            if errors:
                write_state("annotation_validation_failed", error_count=len(errors), examples=errors[:20], quality_counts=dict(counts))
                log(f"annotation validation failed: {len(errors)} errors")
                time.sleep(300)
                continue
            if not BASE_WEIGHTS.exists():
                write_state("failed", reason="base_weights_missing")
                return
            write_state("building_datasets", quality_counts=dict(counts))
            for sensor in ("V", "T"):
                out = ADAPT / "datasets" / f"{sensor}_v1"
                code = run([PY, str(TOOLS / "dji_build_yolo_dataset.py"), "--manifest", str(MANIFEST), "--frames-index", str(FRAMES), "--sensor", sensor, "--output", str(out), "--copy-images"])
                if code:
                    write_state("dataset_build_failed", sensor=sensor, returncode=code)
                    return
            weights = {}
            for sensor, device in (("V", "0"), ("T", "1")):
                data = ADAPT / "datasets" / f"{sensor}_v1/data.yaml"
                smoke_name = f"{sensor}_v1_smoke"
                smoke_dir = ADAPT / "runs" / smoke_name
                code = run([PY, str(TOOLS / "dji_train_adaptation.py"), "--weights", str(BASE_WEIGHTS), "--data", str(data), "--sensor", sensor, "--project", str(ADAPT / "runs"), "--name", smoke_name, "--epochs", "3", "--smoke", "--device", device])
                if code:
                    write_state("smoke_training_failed", sensor=sensor, returncode=code)
                    return
                smoke_best = find_best(smoke_dir)
                if not smoke_best:
                    write_state("smoke_training_failed", sensor=sensor, reason="best_weight_missing")
                    return
                full_name = f"{sensor}_v1_full"
                full_dir = ADAPT / "runs" / full_name
                code = run([PY, str(TOOLS / "dji_train_adaptation.py"), "--weights", str(smoke_best), "--data", str(data), "--sensor", sensor, "--project", str(ADAPT / "runs"), "--name", full_name, "--epochs", "10", "--device", device])
                if code:
                    write_state("full_training_failed", sensor=sensor, returncode=code)
                    return
                best = find_best(full_dir)
                if not best:
                    write_state("full_training_failed", sensor=sensor, reason="best_weight_missing")
                    return
                weights[sensor] = best
                eval_dir = ADAPT / "validation" / sensor
                code = run([PY, str(TOOLS / "run_detection_baseline.py"), "--weights", str(best), "--data", str(data), "--mode", "val", "--split", "val", "--project", str(eval_dir), "--name", "val", "--device", device, "--imgsz", "640", "--batch", "8", "--workers", "2"])
                if code:
                    write_state("validation_failed", sensor=sensor, returncode=code)
                    return
            inventory = json.loads((RESULTS / "inventory.json").read_text(encoding="utf-8"))
            roots = batch_roots(inventory)
            infer_root = ADAPT / "inference"
            for sensor, device in (("V", "0"), ("T", "1")):
                for batch, root in sorted(roots.items()):
                    out = infer_root / batch / sensor
                    code = run([PY, str(TOOLS / "dji_batch_inference.py"), "--root", str(root), "--weights", str(weights[sensor]), "--output", str(out), "--sensor", sensor, "--vid-stride", "300", "--device", device])
                    if code:
                        write_state("adapted_inference_failed", sensor=sensor, batch=batch, returncode=code)
                        return
            for batch in roots:
                run([PY, str(TOOLS / "dji_detection_summary.py"), "--root", str(infer_root / batch), "--output", str(ADAPT / "summary" / f"{batch}.json")])
            common = ["--inventory", str(RESULTS / "inventory.json"), "--sync-dir", str(RESULTS / "sync"), "--inference-root", str(infer_root)]
            run([PY, str(TOOLS / "dji_batch_association.py"), *common, "--output", str(ADAPT / "tv_association.json")])
            run([PY, str(TOOLS / "dji_tv_tracking.py"), "--input", str(ADAPT / "tv_association.json"), "--output", str(ADAPT / "tv_tracking.json")])
            write_state("complete", weights={k: str(v) for k, v in weights.items()}, quality_counts=dict(counts))
            log("adaptation pipeline complete")
            return
        except Exception as exc:
            write_state("failed", reason=repr(exc))
            log("orchestrator exception: " + repr(exc))
            return


if __name__ == "__main__":
    main()
