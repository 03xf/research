#!/usr/bin/env python3
"""Run reproducible T/V inference on a timestamp-aligned B4 frame schedule.

This is deliberately provisional: detector gates are currently failed and no
T/V extrinsics are available, so output is not an absolute fire location.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import sys
sys.path.insert(0, "/home/member/xmy/xmy/code/projects/ultralytics")
from ultralytics import YOLO


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def names_for(model, classes):
    names = model.names
    return [str(names[int(c)]) if isinstance(names, dict) else str(names[int(c)]) for c in classes]


def infer(model, frame, sensor, frame_index, timestamp, conf, imgsz, device):
    result = model.predict(source=frame, imgsz=imgsz, conf=conf, device=device, verbose=False)[0]
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return {"boxes": [], "confidence": [], "class": [], "class_name": [], "centers": [], "sensor": sensor, "frame_index": frame_index, "timestamp_s": timestamp}
    coords = boxes.xyxy.detach().cpu().tolist()
    scores = boxes.conf.detach().cpu().tolist()
    cls = boxes.cls.detach().cpu().tolist()
    centers = [[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for b in coords]
    return {"boxes": coords, "confidence": scores, "class": cls, "class_name": names_for(model, cls), "centers": centers, "sensor": sensor, "frame_index": frame_index, "timestamp_s": timestamp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", required=True, type=Path)
    ap.add_argument("--v-weights", required=True, type=Path)
    ap.add_argument("--t-weights", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.10)
    ap.add_argument("--device", default="0")
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing to overwrite")
    schedule = json.loads(args.schedule.read_text(encoding="utf-8"))
    v_model, t_model = YOLO(str(args.v_weights)), YOLO(str(args.t_weights))
    for model in (v_model, t_model):
        for module in model.model.modules():
            if type(module).__name__ == "GELU" and not hasattr(module, "approximate"):
                module.approximate = "none"
    observations, group_summaries = [], []
    started = datetime.now(timezone.utc).isoformat()
    for group_index, group in enumerate(schedule["groups"], 1):
        tcap = cv2.VideoCapture(group["thermal_source"])
        vcap = cv2.VideoCapture(group["visible_source"])
        if not tcap.isOpened() or not vcap.isOpened():
            group_summaries.append({"pair_key": group["pair_key"], "status": "open_failed"})
            if tcap.isOpened(): tcap.release()
            if vcap.isOpened(): vcap.release()
            continue
        boxes_t = boxes_v = 0
        for match in group["matches"]:
            tf, vf = int(match["thermal_frame"]), int(match["visible_frame"])
            if not tcap.set(cv2.CAP_PROP_POS_FRAMES, tf):
                continue
            tok, tframe = tcap.read()
            if not vcap.set(cv2.CAP_PROP_POS_FRAMES, vf):
                continue
            vok, vframe = vcap.read()
            if not tok or tframe is None or not vok or vframe is None:
                continue
            td = infer(t_model, tframe, "T", tf, match["thermal_timestamp_s"], args.conf, args.imgsz, args.device)
            vd = infer(v_model, vframe, "V", vf, match["visible_timestamp_s"], args.conf, args.imgsz, args.device)
            boxes_t += len(td["boxes"])
            boxes_v += len(vd["boxes"])
            status = "temporal_candidate" if td["boxes"] and vd["boxes"] else ("thermal_only" if td["boxes"] else ("visible_only" if vd["boxes"] else "no_detection"))
            observations.append({"observation_id": f"B4:{group['pair_key']}:{tf}", "batch_id": "B4", "session_id": group["pair_key"].split("/")[-3] if "/" in group["pair_key"] else None, "video_group": group["pair_key"].split("/")[-1], "timestamp_s": match["thermal_timestamp_s"], "thermal_timestamp_s": match["thermal_timestamp_s"], "visible_timestamp_s": match["visible_timestamp_s"], "thermal_frame": tf, "visible_frame": vf, "thermal_detection": td, "visible_detection": vd, "association_status": status, "sync_delta_s": match["predicted_sync_delta_s"], "spatial_correspondence": "unverified", "fire_event_id": None, "track_id": None, "metadata_reference": {"thermal_source": group["thermal_source"], "visible_source": group["visible_source"], "schedule": str(args.schedule)}})
        tcap.release(); vcap.release()
        group_summaries.append({"pair_key": group["pair_key"], "status": "complete", "scheduled_pairs": len(group["matches"]), "observation_count": sum(1 for x in observations if x["metadata_reference"]["thermal_source"] == group["thermal_source"]), "thermal_box_count": boxes_t, "visible_box_count": boxes_v})
        print(f"[{group_index}/{len(schedule['groups'])}] {group_summaries[-1]}", flush=True)
    status_counts = Counter(x["association_status"] for x in observations)
    payload = {"schema_version": "dji_b4_aligned_inference_v1", "created_utc": datetime.now(timezone.utc).isoformat(), "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(), "schedule": str(args.schedule), "v_weights": str(args.v_weights), "v_weights_sha256": sha(args.v_weights), "t_weights": str(args.t_weights), "t_weights_sha256": sha(args.t_weights), "imgsz": args.imgsz, "conf": args.conf, "device": args.device, "provisional_detector": True, "model_gate": "failed", "absolute_localization": "unavailable", "spatial_correspondence": "unverified; no Matrice 4T extrinsics", "summary": {"group_count": len(schedule["groups"]), "observation_count": len(observations), "status_counts": dict(status_counts), "thermal_box_count": sum(len(x["thermal_detection"]["boxes"]) for x in observations), "visible_box_count": sum(len(x["visible_detection"]["boxes"]) for x in observations)}, "group_summaries": group_summaries, "observations": observations}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
