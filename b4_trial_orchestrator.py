#!/usr/bin/env python3
"""Run the isolated B4 50-observation training and follow-up stages."""
import copy
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/home/member/xmy/xmy")
RESULTS = BASE / "results/dji_all_batches"
TRIAL = BASE / "results/dji_adaptation/b4_trial_v3"
TOOLS = BASE / "code/tools"
PY = "/home/member/bin/python"
GLOBAL_MANIFEST = RESULTS / "annotation_manifest.json"
CANDIDATES = RESULTS / "b4_fire_candidates_v3.json"
FRAMES = RESULTS / "annotation_frames/frames_index.json"
WEIGHTS = BASE / "weights/detection/ultralytics/train/exp69/weights/best.pt"
STATE = TRIAL / "state.json"
LOG = TRIAL / "orchestrator.log"

TRAIN_GROUPS = {
    "train": {
        "DJI_20260908105248_0002",
        "DJI_20260908105253_0001",
        "DJI_20260908105257_0001",
        "DJI_20260908105258_0002",
        "DJI_20260908105259_0001",
    },
    "validation": {"DJI_20260908105300_0001", "DJI_20260908105306_0001"},
    "test": {"DJI_20260908105258_0001"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_state(status, **extra):
    TRIAL.mkdir(parents=True, exist_ok=True)
    payload = {"status": status, "updated_utc": now(), **extra}
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, STATE)


def log(message):
    TRIAL.mkdir(parents=True, exist_ok=True)
    line = f"{now()} {message}\n"
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="", flush=True)


def run(cmd, log_name):
    path = TRIAL / log_name
    log("$ " + " ".join(map(str, cmd)))
    with path.open("a", encoding="utf-8") as fh:
        return subprocess.run([str(x) for x in cmd], stdout=fh, stderr=subprocess.STDOUT, check=False).returncode


def prepare_manifest():
    source = json.loads(GLOBAL_MANIFEST.read_text(encoding="utf-8"))
    ids = json.loads(CANDIDATES.read_text(encoding="utf-8"))["observation_ids"]
    by_id = {x["observation_id"]: x for x in source["observations"]}
    rows = []
    for oid in ids:
        row = copy.deepcopy(by_id[oid])
        group = row.get("video_group")
        split = next((s for s, groups in TRAIN_GROUPS.items() if group in groups), "excluded")
        row["split"] = split
        quality = row.get("annotation", {}).get("annotation_quality")
        if split != "train" and quality == "weak":
            row["annotation"]["annotation_quality"] = "unusable"
            row.setdefault("metadata_reference", {})["weak_excluded_from_eval"] = True
        rows.append(row)
    payload = {
        "schema_version": "dji_b4_trial_manifest_v3",
        "created_utc": now(),
        "source_manifest": str(GLOBAL_MANIFEST),
        "candidate_manifest": str(CANDIDATES),
        "split_policy": {k: sorted(v) for k, v in TRAIN_GROUPS.items()},
        "observations": rows,
        "summary": {
            "observation_count": len(rows),
            "by_split": dict(Counter(x["split"] for x in rows)),
            "quality": dict(Counter(x["annotation"]["annotation_quality"] for x in rows)),
            "weak_policy": "train_only",
        },
    }
    path = TRIAL / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (TRIAL / "split_policy.json").write_text(json.dumps(payload["split_policy"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, rows


def build_datasets(manifest):
    datasets = {}
    for sensor in ("V", "T"):
        out = TRIAL / "datasets" / sensor
        cmd = [PY, TOOLS / "dji_build_yolo_dataset.py", "--manifest", manifest, "--frames-index", FRAMES, "--sensor", sensor, "--output", out, "--copy-images"]
        if run(cmd, f"dataset_{sensor}.log"):
            raise RuntimeError(f"dataset build failed: {sensor}")
        datasets[sensor] = out / "data.yaml"
    return datasets


def train(datasets):
    def complete_run(sensor, run_dir):
        best = run_dir / "weights/best.pt"
        results_csv = run_dir / "results.csv"
        config = run_dir / "run_config.json"
        if not (best.exists() and results_csv.exists() and config.exists()):
            return None
        cfg = json.loads(config.read_text(encoding="utf-8"))
        if not cfg.get("finished_utc"):
            cfg["finished_utc"] = now()
            cfg["completion_note"] = "artifacts_complete; post-training callback status recovered by orchestrator"
            config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"returncode": 0, "run_dir": str(run_dir), "best": str(best), "results_csv": str(results_csv), "config": str(config), "recovered_artifacts": True}

    results = {}
    pending = []
    for sensor in ("V", "T"):
        candidates = sorted((TRIAL / "runs").glob(f"{sensor}_full*"), key=lambda p: p.stat().st_mtime, reverse=True)
        found = next((complete_run(sensor, p) for p in candidates if p.is_dir()), None)
        if found:
            results[sensor] = found
        else:
            pending.append(sensor)
    if not pending:
        write_state("training_complete", sensors=results, epochs=30)
        return results
    processes = {}
    env = os.environ.copy()
    env["WANDB_MODE"] = "disabled"
    env["WANDB_DISABLED"] = "true"
    for sensor, device in (("V", "0"), ("T", "1")):
        if sensor not in pending:
            continue
        name = f"{sensor}_full"
        suffix = 0
        while (TRIAL / "runs" / name).exists():
            suffix += 1
            name = f"{sensor}_full_retry{suffix}"
        out = TRIAL / "runs"
        log_path = TRIAL / f"train_{sensor}.log"
        fh = log_path.open("a", encoding="utf-8")
        cmd = [PY, TOOLS / "dji_train_adaptation.py", "--weights", WEIGHTS, "--data", datasets[sensor], "--sensor", sensor, "--project", out, "--name", name, "--epochs", "30", "--imgsz", "640", "--batch", "8", "--freeze", "10", "--lr0", "0.001", "--device", device, "--workers", "2", "--seed", "0"]
        log("$ " + " ".join(map(str, cmd)))
        p = subprocess.Popen([str(x) for x in cmd], stdout=fh, stderr=subprocess.STDOUT, env=env)
        processes[sensor] = {"pid": p.pid, "process": p, "log": str(log_path), "run_dir": str(out / name), "started_utc": now()}
        fh.close()
    write_state("training_running", sensors={s: {k: v for k, v in x.items() if k != "process"} for s, x in processes.items()}, epochs=30)
    for sensor, info in processes.items():
        code = info["process"].wait()
        results[sensor] = {"returncode": code, **{k: v for k, v in info.items() if k != "process"}}
        write_state("training_running", sensors=results, epochs=30)
        run_dir = Path(info["run_dir"])
        best = run_dir / "weights/best.pt"
        results_csv = run_dir / "results.csv"
        config = run_dir / "run_config.json"
        log_text = Path(info["log"]).read_text(encoding="utf-8", errors="replace") if Path(info["log"]).exists() else ""
        if code != 0 and best.exists() and results_csv.exists() and config.exists() and "on_train_end" in log_text and "wandb" in log_text.lower():
            cfg = json.loads(config.read_text(encoding="utf-8"))
            cfg["finished_utc"] = now()
            cfg["completion_note"] = "training artifacts complete; W&B post-training callback failed"
            config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results[sensor]["returncode"] = 0
            results[sensor]["recovered_postprocess_error"] = True
        elif code != 0:
            raise RuntimeError(f"{sensor} training failed with return code {code}")
        if not best.exists() or not results_csv.exists() or not config.exists():
            raise RuntimeError(f"{sensor} training artifacts incomplete: {run_dir}")
        results[sensor]["best"] = str(best)
        results[sensor]["results_csv"] = str(results_csv)
    write_state("training_complete", sensors=results, epochs=30)
    return results


def validate(weights, datasets):
    validation = TRIAL / "validation"
    for sensor, device in (("V", "0"), ("T", "1")):
        for split in ("val", "test"):
            name = f"{sensor}_{split}"
            cmd = [PY, TOOLS / "run_detection_baseline.py", "--weights", weights[sensor]["best"], "--data", datasets[sensor], "--mode", "val", "--split", split, "--project", validation, "--name", name, "--device", device, "--imgsz", "640", "--batch", "8", "--workers", "2", "--plots"]
            if run(cmd, f"validation_{sensor}_{split}.log"):
                raise RuntimeError(f"validation failed: {sensor}/{split}")
    write_state("validation_complete", validation_dir=str(validation), sensors=weights)


def infer_50(weights, rows):
    sys.path.insert(0, str(TOOLS.parent / "projects" / "ultralytics"))
    from ultralytics import YOLO
    frames = json.loads(FRAMES.read_text(encoding="utf-8"))["frames"]
    out_dir = TRIAL / "inference_50"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_results = {}
    for sensor, device in (("V", "0"), ("T", "1")):
        model = YOLO(weights[sensor]["best"])
        records = {}
        for row in rows:
            oid = row["observation_id"]
            source = frames[oid][sensor]["path"]
            result = model.predict(source=source, imgsz=640, conf=0.1, device=device, verbose=False)[0]
            boxes = result.boxes
            records[oid] = {"observation_id": oid, "sensor": sensor, "source": source, "timestamp_s": row["timestamp_s"], "frame_index": row["thermal_frame" if sensor == "T" else "visible_frame"], "boxes": boxes.xyxy.detach().cpu().tolist() if boxes is not None else [], "confidence": boxes.conf.detach().cpu().tolist() if boxes is not None else [], "class": boxes.cls.detach().cpu().tolist() if boxes is not None else []}
        path = out_dir / f"{sensor}.json"
        path.write_text(json.dumps({"weights": weights[sensor]["best"], "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        all_results[sensor] = records
    return all_results


def associate(results, rows):
    out = []
    for row in rows:
        oid = row["observation_id"]
        if oid not in results["V"] or oid not in results["T"]:
            continue
        v, t = results["V"][oid], results["T"][oid]
        vb, tb = v["boxes"], t["boxes"]
        if vb and tb:
            status = "paired" if len(vb) == 1 and len(tb) == 1 else "ambiguous"
        elif vb:
            status = "visible_only"
        elif tb:
            status = "thermal_only"
        else:
            status = "no_detection"
        out.append({"observation_id": oid, "batch_id": row["batch_id"], "video_group": row["video_group"], "timestamp_s": row["timestamp_s"], "sync_delta_s": row["sync_delta_s"], "visible_detection": v, "thermal_detection": t, "association_status": status, "annotation_reference": row["annotation"]})
    path = TRIAL / "association" / "tv_association.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "dji_b4_trial_association_v1", "summary": dict(Counter(x["association_status"] for x in out)), "observations": out}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main():
    try:
        if not WEIGHTS.exists():
            raise RuntimeError(f"base weights missing: {WEIGHTS}")
        write_state("preparing_datasets")
        manifest, rows = prepare_manifest()
        datasets = build_datasets(manifest)
        weights = train(datasets)
        validate(weights, datasets)
        write_state("inference_50_running", sensors=weights)
        results = infer_50(weights, rows)
        write_state("association_running", sensors=weights)
        association = associate(results, rows)
        write_state("b4_trial_complete", sensors=weights, association=str(association), finished_utc=now())
        log("B4 trial complete")
    except Exception as exc:
        write_state("failed", reason=repr(exc))
        log("B4 trial failed: " + repr(exc))
        raise


if __name__ == "__main__":
    main()
