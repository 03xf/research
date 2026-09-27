"""Build a small, immutable V/T source-truth review queue from existing clips."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True, help="recovery_v1 directory")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--per-clip", type=int, default=10)
    args = ap.parse_args()

    clips_root = args.root / "video_clips"
    out = args.output or args.root / "source_truth_review_v1"
    if out.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {out}")
    out.mkdir(parents=True)

    tasks = []
    clip_records = []
    for manifest_path in sorted(clips_root.glob("*_pts_v2/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        clip_id = manifest_path.parent.name
        pairs = manifest.get("pairs", [])
        if not pairs:
            continue
        count = min(args.per_clip, len(pairs))
        indexes = sorted({round(i * (len(pairs) - 1) / max(1, count - 1)) for i in range(count)})
        selected = [pairs[i] for i in indexes]
        clip_records.append({
            "clip_id": clip_id,
            "manifest": str(manifest_path),
            "manifest_sha256": sha(manifest_path),
            "source": manifest.get("source", {}),
            "pair_count": len(pairs),
            "selected_count": len(selected),
        })
        for ordinal, pair in enumerate(selected):
            tasks.append({
                "task_id": f"{clip_id}:{ordinal:02d}",
                "clip_id": clip_id,
                "ordinal": ordinal,
                "pair_index": indexes[ordinal],
                "thermal_frame": str(manifest_path.parent / "T" / pair["thermal_frame"]),
                "visible_frame": str(manifest_path.parent / "V" / pair["visible_frame"]),
                "thermal_pts_s": pair.get("thermal_pts_s"),
                "visible_pts_s": pair.get("visible_pts_s"),
                "delta_s": pair.get("delta_s"),
                "source": manifest.get("source", {}),
            })

    if not tasks:
        raise RuntimeError(f"no *_pts_v2 clip manifests found under {clips_root}")
    payload = {
        "schema_version": "dji_source_truth_review_queue_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sampling": {"per_clip": args.per_clip, "rule": "evenly spaced decoded PTS pairs from existing 5 Hz clips"},
        "clips": clip_records,
        "task_count": len(tasks),
        "tasks": tasks,
        "annotation_schema": {
            "V": "zero or more [x_norm,y_norm,fire_id] source contact points",
            "T": "zero or more [x_norm,y_norm,fire_id] hotspot/source candidate points",
            "tv_relation": "same_source | different_source | unknown",
            "source_state": "active_fire | residual_heat | hot_background | no_source | unknown",
            "thermal_background": "none | hot_background | unknown",
            "frame_status": "usable | unknown",
        },
    }
    (out / "queue.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "decisions.json").write_text(json.dumps({"schema_version": "dji_source_truth_decisions_v1", "decisions": {}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "clip_count": len(clip_records), "task_count": len(tasks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
