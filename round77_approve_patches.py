"""Approve four exact reviewed train patches with neighboring-frame evidence."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
PROPOSALS = ROOT / "data_integrity/round75_manual_patch_proposals_v1.json"
NEIGHBORS = ROOT / "data_integrity/round76_neighbor_review_v1/manifest.json"
OUT = ROOT / "data_integrity/round77_approved_train_patches_v1.json"
STATE = ROOT / "state.json"
BACKUP = ROOT / "data_integrity/state_before_round77_v1.json"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if OUT.exists() or BACKUP.exists():
        raise SystemExit("Refusing overwrite")
    proposal = json.loads(PROPOSALS.read_text())
    neighbors = json.loads(NEIGHBORS.read_text())
    assert not proposal["training_authorized"] and not proposal["blind_test_accessed"]
    assert not neighbors["blind_test_accessed"]
    by_id = {x["observation_id"]: x for x in neighbors["records"]}
    rows = []
    for item in proposal["proposals"]:
        assert item["observation_id"] in by_id
        neighbor = by_id[item["observation_id"]]
        assert len(neighbor["frames"]) >= 2
        for frame in neighbor["frames"]:
            assert sha(Path(frame["image"])) == frame["image_sha256"]
        source_label = Path(item["source_empty_label"])
        assert not source_label.read_text().strip()
        rows.append({
            "observation_id": item["observation_id"], "sensor": item["sensor"],
            "class_name": item["class_name"], "class_id": item["class_id"],
            "xyxy_px": item["xyxy_px"], "image": item["image"],
            "image_sha256": item["image_sha256"], "image_size": item["image_size"],
            "source_empty_label": item["source_empty_label"],
            "source_empty_label_sha256": item["source_empty_label_sha256"],
            "yolo_line": item["yolo_line"],
            "neighbor_review": str(NEIGHBORS), "neighbor_review_sha256": sha(NEIGHBORS),
            "decision": "approved_for_new_derived_train_dataset_only",
            "basis": item["basis"] + " Neighbor frames show the same burning target at the surrounding time points.",
            "original_label_modified": False,
        })
    report = {
        "schema_version": "dji_round77_approved_train_patches_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_source": str(PROPOSALS), "proposal_source_sha256": sha(PROPOSALS),
        "neighbor_review_source": str(NEIGHBORS), "neighbor_review_source_sha256": sha(NEIGHBORS),
        "approved_count": len(rows), "approved_for_training": True,
        "source_labels_modified": False, "validation_labels_modified": False,
        "blind_test_accessed": False, "patches": rows,
        "scope": "Only a newly built derived training dataset may apply these labels; no historical directory may be changed.",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    previous = STATE.read_bytes()
    state = json.loads(previous)
    assert state["stage"] == "round75_manual_train_patch_proposals_pending_second_review"
    BACKUP.write_bytes(previous)
    state["stage"] = "round77_train_patches_approved_building_derived_dataset"
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    state["round77_approved_train_patches"] = str(OUT)
    state["next_action"] = (
        "Build a new versioned derived dataset from Round56 with only the four Round77 patches; "
        "preserve all originals and development validation; run bounds/class/split preflight. "
        "Continue exact review of V hidden-positive smoke geometry and T obs_000548/840 before adding more patches. "
        "Do not start full training until preflight passes."
    )
    pending = STATE.with_name("state.round77.pending.json")
    if pending.exists():
        raise SystemExit("Pending state exists")
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    os.replace(str(pending), str(STATE))
    print(json.dumps({"report": str(OUT), "approved_count": len(rows), "stage": state["stage"]}))


if __name__ == "__main__":
    main()
