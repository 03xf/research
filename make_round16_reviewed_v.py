#!/usr/bin/env python3
"""Build a train-only V dataset with eight reviewed frames, preserving v12."""
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
BASE = ROOT / "datasets_round12_copy_abs/V"
OUT = ROOT / "datasets_round16_reviewed_v/V"
AUDIT = ROOT / "round16_visual_audit_v1.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label_lines(labels):
    lines = []
    for item in labels:
        x1, y1, x2, y2 = map(float, item["bbox_xyxy"])
        cls = 0 if item["class"] == "smoke" else 1
        x = (x1 + x2) / (2 * 1920)
        y = (y1 + y2) / (2 * 1080)
        w = (x2 - x1) / 1920
        h = (y2 - y1) / 1080
        assert 0 < x < 1 and 0 < y < 1 and 0 < w <= 1 and 0 < h <= 1
        lines.append("%d %.8f %.8f %.8f %.8f" % (cls, x, y, w, h))
    return lines


audit = json.loads(AUDIT.read_text(encoding="utf-8"))
review = {r["observation_id"]: r for r in audit["records"]}
if OUT.exists():
    raise SystemExit("output exists; refusing to overwrite")
manifest = {"schema_version": "dji_round16_reviewed_v_dataset_v1", "base": str(BASE), "base_manifest_sha256": sha(ROOT / "manifest_round12.json"), "audit": str(AUDIT), "audit_sha256": sha(AUDIT), "train_only_change": True, "validation_unchanged": True, "blind_test_accessed": False, "excluded": [], "overridden": [], "counts": {}}
for split in ("train", "validation", "test"):
    images_src = BASE / "images" / split
    labels_src = BASE / "labels" / split
    images_dst = OUT / "images" / split
    labels_dst = OUT / "labels" / split
    images_dst.mkdir(parents=True)
    labels_dst.mkdir(parents=True)
    if not images_src.exists():
        continue
    for image in sorted(images_src.glob("*.jpg")):
        obs_id = image.stem
        entry = review.get(obs_id) if split == "train" else None
        if entry and entry["action"] == "exclude_from_v_training_pending_review":
            manifest["excluded"].append(obs_id)
            continue
        (images_dst / image.name).symlink_to(image.resolve())
        old_label = labels_src / (obs_id + ".txt")
        new_label = labels_dst / (obs_id + ".txt")
        if entry:
            new_label.write_text("\n".join(label_lines(entry["proposed_visible_labels"])) + "\n", encoding="utf-8")
            manifest["overridden"].append(obs_id)
        elif old_label.exists():
            new_label.symlink_to(old_label.resolve())
    manifest["counts"][split] = {"images": len(list(images_dst.glob("*.jpg"))), "labels": len(list(labels_dst.glob("*.txt")))}
(OUT / "data.yaml").write_text("path: %s\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n  0: smoke\n  1: flame\nnc: 2\n" % OUT, encoding="utf-8")
(OUT / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert manifest["counts"]["validation"]["images"] == 71
assert len(manifest["overridden"]) == 7 and len(manifest["excluded"]) == 1
print(json.dumps(manifest, ensure_ascii=False, indent=2))
