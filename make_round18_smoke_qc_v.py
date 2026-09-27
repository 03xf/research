#!/usr/bin/env python3
"""Build a separate V dataset from visually reviewed train-only smoke labels."""
import hashlib
import json
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
base = root / "datasets_round16_reviewed_v/V"
out = root / "datasets_round18_smoke_qc_v/V"
if out.exists():
    raise SystemExit("output exists; refusing to overwrite")
audits = [root / name for name in (
    "round18_smoke_label_review_v1.json",
    "round18_b1b3_smoke_visual_audit_v1.json",
    "round18_b4_weak_smoke_audit_v1.json",
)]
override_ids = {"obs_000808", "obs_v7_train_0008", "obs_v7_train_0009", "obs_000049", "obs_000484", "obs_000313", "obs_000534"}
exclude_ids = {"obs_v7_train_0013", "obs_000112", "obs_000324", "obs_000414", "obs_000574", "obs_000604", "obs_000825"}
assert not override_ids & exclude_ids


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(labels):
    rows = []
    for label in labels:
        x1, y1, x2, y2 = map(float, label["bbox_xyxy"])
        assert 0 <= x1 < x2 <= 1920 and 0 <= y1 < y2 <= 1080
        cls = {"smoke": 0, "flame": 1}[label["class"]]
        rows.append(f"{cls} {(x1+x2)/3840:.8f} {(y1+y2)/2160:.8f} {(x2-x1)/1920:.8f} {(y2-y1)/1080:.8f}")
    return rows


reviews = {}
for audit in audits:
    source = json.loads(audit.read_text(encoding="utf-8"))
    assert source["blind_test_accessed"] is False and source["validation_labels_modified"] is False
    for item in source["records"]:
        assert item["observation_id"] not in reviews
        reviews[item["observation_id"]] = item
assert override_ids | exclude_ids <= reviews.keys()
manifest = {"schema_version": "dji_round18_train_only_smoke_qc_v1", "base_dataset": str(base), "audits": [{"path": str(path), "sha256": sha(path)} for path in audits], "overridden": [], "excluded": [], "counts": {}, "validation_unchanged": True, "blind_test_accessed": False, "semantics": "Manual proposals on training images only; not gold-standard validation truth"}
for split in ("train", "validation", "test"):
    src_images, src_labels = base / "images" / split, base / "labels" / split
    dst_images, dst_labels = out / "images" / split, out / "labels" / split
    dst_images.mkdir(parents=True)
    dst_labels.mkdir(parents=True)
    if not src_images.exists():
        continue
    for image in sorted(src_images.glob("*.jpg")):
        obs_id = image.stem
        if split == "train" and obs_id in exclude_ids:
            manifest["excluded"].append(obs_id)
            continue
        (dst_images / image.name).symlink_to(image.resolve())
        label_src = src_labels / (obs_id + ".txt")
        label_dst = dst_labels / (obs_id + ".txt")
        if split == "train" and obs_id in override_ids:
            proposed = reviews[obs_id]["proposed_visible_labels"]
            assert proposed
            label_dst.write_text("\n".join(lines(proposed)) + "\n", encoding="utf-8")
            manifest["overridden"].append(obs_id)
        elif label_src.exists():
            label_dst.symlink_to(label_src.resolve())
    manifest["counts"][split] = {"images": len(list(dst_images.glob("*.jpg"))), "labels": len(list(dst_labels.glob("*.txt")))}
assert set(manifest["overridden"]) == override_ids
assert set(manifest["excluded"]) == exclude_ids
assert manifest["counts"]["train"]["images"] == 468
assert manifest["counts"]["validation"]["images"] == 71
for label in (base / "labels/validation").glob("*.txt"):
    assert (out / "labels/validation" / label.name).read_bytes() == label.read_bytes()
(out / "data.yaml").write_text(f"path: {out}\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n  0: smoke\n  1: flame\nnc: 2\n", encoding="utf-8")
(out / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False))
