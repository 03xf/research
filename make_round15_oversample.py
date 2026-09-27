import json
import os
from pathlib import Path

BASE = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/datasets_round12_copy_abs")
OUT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/datasets_round15_oversample")
REPEATS = {"V": 3, "T": 2}
NAMES = {"V": ["smoke", "flame"], "T": ["hotspot"]}


def link_tree(src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for p in src.iterdir():
        q = dst / p.name
        if q.exists() or q.is_symlink():
            continue
        q.symlink_to(p.resolve())


manifest = {"schema_version": "dji_oversample_v1", "base": str(BASE), "train_only_change": True, "blind_test_accessed": False, "sensors": {}}
for sensor in ("V", "T"):
    src = BASE / sensor
    dst = OUT / sensor
    for part in ("images/train", "images/validation", "images/test", "labels/train", "labels/validation", "labels/test"):
        link_tree(src / part, dst / part)
    train_images = sorted((src / "images/train").glob("*.jpg"))
    entries = []
    positive = 0
    for im in train_images:
        label = src / "labels/train" / (im.stem + ".txt")
        classes = []
        if label.exists():
            for line in label.read_text().splitlines():
                if line.strip():
                    try:
                        classes.append(int(line.split()[0]))
                    except Exception:
                        pass
        is_target = (0 in classes)
        if is_target:
            positive += 1
        entries.extend([str(im.resolve())] * (REPEATS[sensor] if is_target else 1))
    list_path = dst / "train_oversampled.txt"
    list_path.write_text("\n".join(entries) + "\n")
    (dst / "data.yaml").write_text(
        "path: %s\ntrain: %s\nval: images/validation\ntest: images/test\nnames:\n" % (dst, list_path)
        + "\n".join("  %d: %s" % (i, n) for i, n in enumerate(NAMES[sensor]))
        + "\nnc: %d\n" % len(NAMES[sensor])
    )
    manifest["sensors"][sensor] = {"base_train_images": len(train_images), "oversampled_entries": len(entries), "target_positive_images": positive, "repeat_factor": REPEATS[sensor], "data_yaml": str(dst / "data.yaml")}
(OUT / "dataset_manifest.json").parent.mkdir(parents=True, exist_ok=True)
(OUT / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
