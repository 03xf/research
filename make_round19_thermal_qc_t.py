#!/usr/bin/env python3
"""Create a non-overwriting, train-only T hotspot label QC dataset."""
import hashlib
import json
from pathlib import Path

root = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
base = root / "datasets_round12_copy_abs/T"
out = root / "datasets_round19_thermal_qc_t/T"
audit = root / "round19_thermal_hotspot_visual_audit_v1.json"
if out.exists():
    raise SystemExit("output exists; refusing to overwrite")
review = json.loads(audit.read_text(encoding="utf-8"))
assert review["blind_test_accessed"] is False and review["validation_labels_modified"] is False
overrides = {r["observation_id"]: r["proposed_thermal_labels"] for r in review["records"] if r["proposed_thermal_labels"]}
assert len(overrides) == 6


def lines(labels):
    out_lines = []
    for item in labels:
        assert item["class"] == "hotspot"
        x1, y1, x2, y2 = map(float, item["bbox_xyxy"])
        assert 0 <= x1 < x2 <= 1280 and 0 <= y1 < y2 <= 1024
        out_lines.append(f"0 {(x1+x2)/2560:.8f} {(y1+y2)/2048:.8f} {(x2-x1)/1280:.8f} {(y2-y1)/1024:.8f}")
    return out_lines


manifest = {"schema_version": "dji_round19_thermal_train_label_qc_v1", "base_dataset": str(base), "audit": str(audit), "audit_sha256": hashlib.sha256(audit.read_bytes()).hexdigest(), "train_only_change": True, "validation_unchanged": True, "blind_test_accessed": False, "overridden": [], "counts": {}}
for split in ("train", "validation", "test"):
    src_images, src_labels = base / "images" / split, base / "labels" / split
    dst_images, dst_labels = out / "images" / split, out / "labels" / split
    dst_images.mkdir(parents=True)
    dst_labels.mkdir(parents=True)
    if not src_images.exists():
        continue
    for image in sorted(src_images.glob("*.jpg")):
        obs_id = image.stem
        (dst_images / image.name).symlink_to(image.resolve())
        old = src_labels / (obs_id + ".txt")
        new = dst_labels / (obs_id + ".txt")
        if split == "train" and obs_id in overrides:
            new.write_text("\n".join(lines(overrides[obs_id])) + "\n", encoding="utf-8")
            manifest["overridden"].append(obs_id)
        elif old.exists():
            new.symlink_to(old.resolve())
    manifest["counts"][split] = {"images": len(list(dst_images.glob("*.jpg"))), "labels": len(list(dst_labels.glob("*.txt")))}
assert set(manifest["overridden"]) == set(overrides)
assert manifest["counts"]["train"]["images"] == 499
assert manifest["counts"]["validation"]["images"] == 71
for label in (base / "labels/validation").glob("*.txt"):
    assert (out / "labels/validation" / label.name).read_bytes() == label.read_bytes()
(out / "data.yaml").write_text(f"path: {out}\ntrain: images/train\nval: images/validation\ntest: images/test\nnames:\n  0: hotspot\nnc: 1\n", encoding="utf-8")
(out / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False))
