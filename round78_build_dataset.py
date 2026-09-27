"""Build and preflight a new derived dataset applying only approved Round77 patches."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
SOURCE = ROOT / "datasets_round56_deconflicted_dev_v2"
PATCHES = ROOT / "data_integrity/round77_approved_train_patches_v1.json"
OUT = ROOT / "datasets_round77_patched_train_v1"
REPORT = ROOT / "data_integrity/round78_dataset_preflight_v1.json"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def label_rows(path, class_count):
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split()
        assert len(fields) == 5
        cls = int(fields[0])
        vals = [float(x) for x in fields[1:]]
        assert 0 <= cls < class_count
        x, y, w, h = vals
        assert w > 0 and h > 0 and -1e-6 <= x-w/2 and x+w/2 <= 1.000001
        assert -1e-6 <= y-h/2 and y+h/2 <= 1.000001
        rows.append((cls, vals))
    return rows


def main():
    if OUT.exists() or REPORT.exists():
        raise SystemExit("Refusing overwrite")
    assert SOURCE.is_dir()
    patches = json.loads(PATCHES.read_text())
    assert patches["approved_for_training"] and not patches["blind_test_accessed"]
    assert patches["source_labels_modified"] is False
    shutil.copytree(SOURCE, OUT)
    applied = []
    for patch in patches["patches"]:
        target = OUT / patch["sensor"] / "labels/train" / (patch["observation_id"] + ".txt")
        source = SOURCE / patch["sensor"] / "labels/train" / (patch["observation_id"] + ".txt")
        assert target.is_file() and source.is_file()
        assert sha(source) == patch["source_empty_label_sha256"] and not source.read_text().strip()
        target.write_text(patch["yolo_line"] + "\n")
        applied.append({"observation_id": patch["observation_id"], "sensor": patch["sensor"],
                        "source_label": str(source), "source_label_sha256": sha(source),
                        "derived_label": str(target), "derived_label_sha256": sha(target),
                        "yolo_line": patch["yolo_line"], "patch_record": str(PATCHES)})
    counts = {}
    for sensor, class_count in (("V", 2), ("T", 1)):
        counts[sensor] = {}
        for split in ("train", "validation"):
            image_dir = OUT / sensor / "images" / split
            label_dir = OUT / sensor / "labels" / split
            images = sorted(image_dir.glob("*.jpg"))
            labels = sorted(label_dir.glob("*.txt"))
            assert {p.stem for p in images} == {p.stem for p in labels}
            class_counts = [0] * class_count
            for label in labels:
                for cls, _ in label_rows(label, class_count):
                    class_counts[cls] += 1
            counts[sensor][split] = {"images": len(images), "labels": len(labels),
                                     "class_instances": class_counts,
                                     "empty_labels": sum(not p.read_text().strip() for p in labels)}
    source_manifest = json.loads((SOURCE / "manifest.json").read_text())
    assert source_manifest["blind_test_accessed"] is False
    assert source_manifest["validation_is_historically_exposed"] is True
    report = {
        "schema_version": "dji_round78_patched_train_dataset_preflight_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(SOURCE), "source_dataset_sha256": sha(SOURCE / "manifest.json"),
        "derived_dataset": str(OUT), "source_manifest_blind_test_accessed": False,
        "historically_exposed_development_validation": True,
        "validation_copied_without_patch": True, "blind_test_accessed": False,
        "patches_applied_count": len(applied), "patches_applied": applied,
        "counts": counts,
        "preflight": {"image_label_stems_match": True, "bounds_and_classes_valid": True,
                       "validation_labels_unchanged": all(
                           sha(OUT / sensor / "labels/validation" / name) == sha(SOURCE / sensor / "labels/validation" / name)
                           for sensor in ("V", "T") for name in [p.name for p in (SOURCE / sensor / "labels/validation").glob("*.txt")]),
                       "source_labels_unchanged": True, "training_authorized": False},
        "next_action": "Run 3-epoch smoke training only after configuration review; no formal validation gate or blind-test access yet.",
    }
    assert report["preflight"]["validation_labels_unchanged"]
    (OUT / "manifest_round78.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"dataset": str(OUT), "report": str(REPORT), "counts": counts}))


if __name__ == "__main__":
    main()
