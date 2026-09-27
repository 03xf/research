"""Create conservative, review-only bbox proposals for four obvious train hidden positives."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
DATA = ROOT / "datasets_round56_deconflicted_dev_v2"
OUT = ROOT / "data_integrity/round75_manual_patch_proposals_v1.json"
STATE = ROOT / "state.json"
BACKUP = ROOT / "data_integrity/state_before_round75_v1.json"

PROPOSALS = [
    {"observation_id": "obs_000002", "sensor": "V", "class_name": "flame", "class_id": 1,
     "xyxy_px": [1020, 270, 1290, 430],
     "basis": "Visible flame tongues at the upper-right edge of the branch pile; compact box excludes the person and most dry branches."},
    {"observation_id": "obs_000135", "sensor": "V", "class_name": "flame", "class_id": 1,
     "xyxy_px": [870, 350, 1280, 770],
     "basis": "Residual visible flame tongues and smoke at the center of the burned branch pile; box covers the burning core without surrounding bare ground."},
    {"observation_id": "obs_000105", "sensor": "V", "class_name": "flame", "class_id": 1,
     "xyxy_px": [700, 590, 1250, 1080],
     "basis": "Large visible flame at the lower center; box is clipped at the image bottom because the flame exits the frame."},
    {"observation_id": "obs_000294", "sensor": "T", "class_name": "hotspot", "class_id": 0,
     "xyxy_px": [260, 120, 690, 960],
     "basis": "Elongated bright thermal burning core corresponding to the visible fire scene; excludes most dark vegetation to the right."},
]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if OUT.exists() or BACKUP.exists():
        raise SystemExit("Refusing overwrite")
    rows = []
    for item in PROPOSALS:
        image = DATA / item["sensor"] / "images/train" / (item["observation_id"] + ".jpg")
        label = DATA / item["sensor"] / "labels/train" / (item["observation_id"] + ".txt")
        assert image.is_file() and label.is_file()
        assert not label.read_text().strip(), item["observation_id"]
        with Image.open(image) as source:
            width, height = source.size
        x1, y1, x2, y2 = item["xyxy_px"]
        assert 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
        x = ((x1 + x2) / 2) / width
        y = ((y1 + y2) / 2) / height
        w = (x2 - x1) / width
        h = (y2 - y1) / height
        rows.append({
            **item,
            "image": str(image), "image_sha256": sha(image), "image_size": [width, height],
            "source_empty_label": str(label), "source_empty_label_sha256": sha(label),
            "yolo_line": f"{item['class_id']} {x:.8f} {y:.8f} {w:.8f} {h:.8f}",
            "review_status": "manual_proposal_pending_second_review",
            "training_authorized": False,
        })
    report = {
        "schema_version": "dji_round75_manual_patch_proposals_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(DATA), "source_dataset_manifest_sha256": sha(DATA / "manifest.json"),
        "purpose": "Review-only exact-pixel proposals for four obvious hidden positives; not applied to any dataset.",
        "source_labels_modified": False, "validation_labels_modified": False,
        "blind_test_accessed": False, "training_authorized": False,
        "proposals": rows,
        "next_action": "Second-review each proposal against paired sensor and neighboring frames, then copy only approved labels into a new versioned derived dataset with provenance.",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    previous = STATE.read_bytes()
    state = json.loads(previous)
    assert state["stage"] == "round74_vt_train_empty_label_qc_pending_exact_boxes"
    BACKUP.write_bytes(previous)
    state["stage"] = "round75_manual_train_patch_proposals_pending_second_review"
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    state["round75_manual_patch_proposals"] = str(OUT)
    state["next_action"] = (
        "Second-review Round75 boxes and neighboring frames; do not apply proposals automatically. "
        "Continue exact review of remaining clear V hidden positives and T obs_000548/840, resolve 3 provisional boxes "
        "and 26 train conflicts. Once patches are approved, build a fresh versioned train-only derived dataset, run label preflight, "
        "then controlled V/T smoke/full training."
    )
    pending = STATE.with_name("state.round75.pending.json")
    if pending.exists():
        raise SystemExit("Pending state exists")
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    os.replace(str(pending), str(STATE))
    print(json.dumps({"report": str(OUT), "proposal_count": len(rows), "stage": state["stage"]}))


if __name__ == "__main__":
    main()
