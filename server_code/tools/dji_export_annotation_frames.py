#!/usr/bin/env python3
"""Export annotation candidate frames from the DJI videos.

This produces review material only. It copies no source media and does not
create labels. Existing JPEGs are skipped for resumability.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--output-root", required=True, type=Path)
    ap.add_argument("--jpeg-quality", type=int, default=82)
    ap.add_argument("--max-width", type=int, default=0, help="0 keeps original resolution")
    args = ap.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    observations = payload.get("observations", [])
    requests = defaultdict(list)
    for obs in observations:
        base = args.output_root / str(obs["batch_id"]) / str(obs["observation_id"])
        for sensor, key in (("T", "thermal"), ("V", "visible")):
            frame = obs.get("thermal_frame" if sensor == "T" else "visible_frame")
            source = obs.get("source_video", {}).get(key)
            if source and frame is not None:
                requests[source].append((int(frame), base, sensor, obs["observation_id"]))
    index = {}
    errors = []
    for source, items in sorted(requests.items()):
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            errors.append({"source": source, "error": "open_failed"})
            continue
        for frame_no, base, sensor, obs_id in sorted(items, key=lambda x: x[0]):
            out_path = base.with_name(base.name + "_" + sensor + ".jpg")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if out_path.exists():
                index.setdefault(obs_id, {})[sensor] = {"path": str(out_path), "frame": frame_no, "status": "existing"}
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, image = cap.read()
            if not ok or image is None:
                errors.append({"source": source, "frame": frame_no, "observation_id": obs_id, "error": "read_failed"})
                continue
            if args.max_width and image.shape[1] > args.max_width:
                scale = args.max_width / image.shape[1]
                image = cv2.resize(image, (args.max_width, int(round(image.shape[0] * scale))), interpolation=cv2.INTER_AREA)
            ok = cv2.imwrite(str(out_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality])
            if not ok:
                errors.append({"source": source, "frame": frame_no, "observation_id": obs_id, "error": "write_failed"})
                continue
            index.setdefault(obs_id, {})[sensor] = {"path": str(out_path), "frame": frame_no, "status": "written", "width": int(image.shape[1]), "height": int(image.shape[0])}
        cap.release()
        print(f"done {len(items)} frames {source}", flush=True)
    out = {"schema_version": "dji_annotation_frames_v1", "manifest": str(args.manifest), "output_root": str(args.output_root), "observation_count": len(observations), "exported_observation_count": len(index), "frame_count": sum(len(v) for v in index.values()), "errors": errors, "frames": index}
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "frames_index.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"observation_count": len(observations), "exported_observation_count": len(index), "frame_count": out["frame_count"], "error_count": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
