"""Freeze reviewed B4 thermal labels and build single-variable T1/T2 datasets."""
import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_prepare import check_label


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def labels(boxes):
    lines = []
    for box in boxes:
        if box["kind"] != "source":
            continue
        x1, y1, x2, y2 = box["xyxy"]
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("invalid source box")
        lines.append("0 " + " ".join(f"{number:.8f}" for number in
                                   ((x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1)))
    result = "\n".join(lines) + ("\n" if lines else "")
    check_label(result, 1)
    return result


def validate(root, queue, decisions):
    records = queue["records"]
    by_key = {row["key"]: row for row in records}
    if len(records) != 32 or len(by_key) != 32 or set(decisions) != set(by_key):
        raise ValueError("all 32 pairs must have a decision before freezing")
    for key, row in by_key.items():
        decision = decisions[key]
        if decision["T_sha256"] != row["T_sha256"] or decision["V_sha256"] != row["V_sha256"]:
            raise ValueError("decision image hash mismatch: " + key)
        if digest(Path(row["T_image"])) != row["T_sha256"] or digest(Path(row["V_image"])) != row["V_sha256"]:
            raise ValueError("queue image changed: " + key)
        if decision["outcome"] not in ("usable", "uncertain"):
            raise ValueError("invalid decision outcome: " + key)
        if decision["outcome"] == "usable":
            labels(decision["boxes"])
        elif decision["boxes"]:
            raise ValueError("uncertain item has boxes: " + key)
    return by_key


def build(root, work, mode, records, decisions, frozen_decisions):
    source = root / "dataset_review_applied_v1"
    output = work / "datasets" / mode
    if output.exists():
        raise FileExistsError(output)
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if Path(source_manifest["derived_dataset"]).resolve() != source.resolve():
        raise ValueError("source dataset path mismatch")
    output.parent.mkdir(exist_ok=True)
    old_by_id = {key: row for key, row in records.items() if row["kind"] == "existing"}
    entries = []
    with tempfile.TemporaryDirectory(prefix=mode+".building.", dir=output.parent) as temporary:
        temp = Path(temporary)
        for split in ("train", "validation"):
            images = source / "T/images" / split
            source_labels = source / "T/labels" / split
            dest_images = temp / "T/images" / split
            dest_labels = temp / "T/labels" / split
            dest_images.mkdir(parents=True)
            dest_labels.mkdir(parents=True)
            for image in sorted(images.glob("*.jpg")):
                label = source_labels / (image.stem + ".txt")
                if not label.exists():
                    raise FileNotFoundError(label)
                row = old_by_id.get(image.stem) if split == "train" else None
                decision = decisions[row["key"]] if row else None
                if decision and decision["outcome"] == "uncertain":
                    continue
                text = labels(decision["boxes"]) if decision else label.read_text(encoding="utf-8")
                check_label(text.strip(), 1)
                if row and digest(image) != row["T_sha256"]:
                    raise ValueError("source training image changed: " + image.stem)
                shutil.copyfile(image, dest_images / image.name)
                (dest_labels / label.name).write_text(text, encoding="utf-8")
                entries.append({"split": split, "image": image.name,
                                "image_sha256": digest(dest_images / image.name),
                                "original_label_sha256": digest(label),
                                "new_label_sha256": digest(dest_labels / label.name),
                                "review_override": bool(decision), "new_frame": False})
        if mode == "T2":
            for key, row in records.items():
                if row["kind"] != "new" or decisions[key]["outcome"] != "usable":
                    continue
                image = Path(row["T_image"])
                image_dest = temp / "T/images/train" / (key + ".jpg")
                label_dest = temp / "T/labels/train" / (key + ".txt")
                if image_dest.exists():
                    raise ValueError("new ID collision: " + key)
                shutil.copyfile(image, image_dest)
                label_dest.write_text(labels(decisions[key]["boxes"]), encoding="utf-8")
                entries.append({"split": "train", "image": image_dest.name,
                                "image_sha256": digest(image_dest),
                                "original_label_sha256": None,
                                "new_label_sha256": digest(label_dest),
                                "review_override": True, "new_frame": True,
                                "source_session": row["session_id"], "source_pts_s": row["T_pts_s"]})
        by_split = {split: [x for x in entries if x["split"] == split]
                    for split in ("train", "validation")}
        train_hashes = {x["image_sha256"] for x in by_split["train"]}
        validation_hashes = {x["image_sha256"] for x in by_split["validation"]}
        if len(train_hashes) != len(by_split["train"]) or train_hashes & validation_hashes:
            raise ValueError("train duplicate or validation overlap")
        original_snapshot = source / "review_decisions_snapshot.json"
        shutil.copyfile(original_snapshot, temp / original_snapshot.name)
        shutil.copyfile(frozen_decisions, temp / "thermal_review_decisions_snapshot.json")
        (temp / "T/data.yaml").write_text(
            f"path: {output / 'T'}\ntrain: images/train\nval: images/validation\nnames:\n  0: hotspot\nnc: 1\n",
            encoding="utf-8")
        manifest = {"schema_version": "dji_b4_thermal_background_dataset_v1",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "mode": mode, "derived_dataset": str(output),
                    "source_dataset": str(source),
                    "source_manifest_sha256": digest(source / "manifest.json"),
                    "review_decisions_sha256": digest(original_snapshot),
                    "thermal_review_decisions_sha256": digest(frozen_decisions),
                    "legacy_positive_unreviewed": source_manifest["legacy_positive_unreviewed"],
                    "counts": {split: len(by_split[split]) for split in by_split},
                    "reviewed_existing_count": len(old_by_id),
                    "uncertain_existing_excluded": sum(decisions[x["key"]]["outcome"] == "uncertain"
                                                       for x in old_by_id.values()),
                    "new_usable_added": sum(x["new_frame"] for x in entries),
                    "class_mapping": {"0": "hotspot"},
                    "confirmation_training_excluded": True,
                    "development_historically_exposed": True,
                    "records": entries}
        (temp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.rename(output)
    return output, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "thermal_background_v1"
    queue_dir = work / "review_queue_v1"
    queue_path = queue_dir / "queue.json"
    decisions_path = queue_dir / "decisions.json"
    freeze_path = work / "review_frozen_v1.json"
    if freeze_path.exists() or (work / "datasets/T1").exists() or (work / "datasets/T2").exists():
        raise FileExistsError("thermal review already frozen or datasets exist")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))["decisions"]
    records = validate(root, queue, decisions)
    frozen_dir = work / "review_queue_frozen_v1"
    frozen_dir.mkdir()
    shutil.copyfile(queue_path, frozen_dir / "queue.json")
    shutil.copyfile(decisions_path, frozen_dir / "decisions.json")
    snapshot = frozen_dir / "decisions.json"
    diff_rows = []
    for key, row in records.items():
        old = Path(row["original_label"]).read_text(encoding="utf-8")
        new = labels(decisions[key]["boxes"]) if decisions[key]["outcome"] == "usable" else None
        diff_rows.append({"key": key, "session_id": row["session_id"], "kind": row["kind"],
                          "outcome": decisions[key]["outcome"],
                          "old_source_boxes": len(old.splitlines()),
                          "new_source_boxes": len(new.splitlines()) if new is not None else None,
                          "background_boxes": sum(x["kind"] == "background" for x in decisions[key]["boxes"]),
                          "label_changed": old != new if new is not None else None})
    with (work / "label_diff_v1.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(diff_rows[0]))
        writer.writeheader()
        writer.writerows(diff_rows)
    # T1 changes only existing reviewed training images. T2 adds usable new frames.
    t1, m1 = build(root, work, "T1", records, decisions, snapshot)
    t2, m2 = build(root, work, "T2", records, decisions, snapshot)
    t1_records = {x["image"]: x for x in m1["records"]}
    if any(t1_records.get(x["image"], {}).get("new_label_sha256") != x["new_label_sha256"]
           for x in m2["records"] if not x["new_frame"]):
        raise ValueError("T1/T2 existing labels differ")
    result = {"schema_version": "dji_b4_thermal_review_frozen_v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "queue_sha256": digest(queue_path), "decisions_sha256": digest(decisions_path),
              "pair_count": 32, "usable_count": sum(x["outcome"] == "usable" for x in decisions.values()),
              "uncertain_count": sum(x["outcome"] == "uncertain" for x in decisions.values()),
              "T1_manifest_sha256": digest(t1 / "manifest.json"),
              "T2_manifest_sha256": digest(t2 / "manifest.json"),
              "label_diff": str(work / "label_diff_v1.csv"),
              "T1_train_count": m1["counts"]["train"],
              "T2_train_count": m2["counts"]["train"],
              "validation_count": m1["counts"]["validation"]}
    freeze_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
