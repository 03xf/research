"""Build a new YOLO dataset from frozen recovery review decisions."""

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml


SENSORS = {"V": ("smoke", "flame"), "T": ("hotspot",)}
BOUND_EPSILON = 1e-6


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def text_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def normalize_labels(value, class_count, key):
    output = []
    clipped = 0
    counts = Counter()
    for line in value.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5 or not parts[0].isdigit():
            raise ValueError(f"invalid label fields: {key}: {line}")
        cls = int(parts[0])
        coords = [float(part) for part in parts[1:]]
        if cls not in range(class_count) or not all(math.isfinite(v) for v in coords):
            raise ValueError(f"invalid class or nonfinite box: {key}: {line}")
        x, y, width, height = coords
        if width <= 0 or height <= 0:
            raise ValueError(f"nonpositive box: {key}: {line}")
        x1, y1, x2, y2 = x - width / 2, y - height / 2, x + width / 2, y + height / 2
        if min(x1, y1) < -BOUND_EPSILON or max(x2, y2) > 1 + BOUND_EPSILON:
            raise ValueError(f"box exceeds image: {key}: {line}")
        if min(x1, y1) < 0 or max(x2, y2) > 1:
            x1, y1, x2, y2 = max(0.0, x1), max(0.0, y1), min(1.0, x2), min(1.0, y2)
            if x1 >= x2 or y1 >= y2:
                raise ValueError(f"clipped box has no area: {key}: {line}")
            line = (f"{cls} {(x1 + x2) / 2:.12f} {(y1 + y2) / 2:.12f} "
                    f"{x2 - x1:.12f} {y2 - y1:.12f}")
            clipped += 1
        output.append(line)
        counts[cls] += 1
    return "\n".join(output), counts, clipped


def build(root):
    root = root.resolve()
    preflight = json.loads((root / "preflight.json").read_text(encoding="utf-8"))
    ledger = json.loads((root / "sample_ledger.json").read_text(encoding="utf-8"))["records"]
    queue = json.loads((root / "review_queue.json").read_text(encoding="utf-8"))["items"]
    review_path = root / "review_decisions.json"
    reviews = json.loads(review_path.read_text(encoding="utf-8"))["decisions"]
    source = Path(preflight["source"]).resolve()
    dataset = root / "dataset_review_applied_v1"
    staging = root / "dataset_review_applied_v1.building"
    report_path = root / "review_application_v1.json"
    if dataset.exists() or staging.exists() or report_path.exists():
        raise FileExistsError("review dataset or report already exists")

    def key(row):
        return f"{row['sensor']}:{row['split']}:{row['observation_id']}"

    ledger_by_key = {key(row): row for row in ledger}
    queue_keys = {key(row) for row in queue}
    review_by_key = {row["key"]: row for row in reviews}
    if (len(ledger_by_key) != len(ledger) or len(queue_keys) != len(queue)
            or len(review_by_key) != len(reviews) or set(review_by_key) != queue_keys
            or not queue_keys.issubset(ledger_by_key)):
        raise ValueError("review, queue, or ledger keys disagree")
    if len(queue_keys) != 214:
        raise ValueError(f"expected 214 review decisions, found {len(queue_keys)}")
    for row in reviews:
        if row["status"] not in ("approved_complete", "confirmed_negative"):
            raise ValueError(f"unresolved review: {row['key']}")

    staging.mkdir()
    counts = {sensor: {} for sensor in SENSORS}
    changes = []
    clipped_boxes = []
    legacy_count = 0
    split_hashes = {sensor: {"train": set(), "validation": set()} for sensor in SENSORS}
    split_sessions = {sensor: {"train": set(), "validation": set()} for sensor in SENSORS}
    for row in sorted(ledger, key=key):
        sample_key = key(row)
        sensor, split = row["sensor"], row["split"]
        if sensor not in SENSORS or split not in ("train", "validation"):
            raise ValueError(f"invalid sample grouping: {sample_key}")
        image, label = Path(row["image"]), Path(row["label"])
        if source not in image.resolve().parents or source not in label.resolve().parents:
            raise ValueError(f"source path escapes dataset: {sample_key}")
        if digest(image) != row["image_sha256"] or digest(label) != row["label_sha256"]:
            raise ValueError(f"source bytes changed: {sample_key}")
        original = label.read_text(encoding="utf-8").strip()
        review = review_by_key.get(sample_key)
        if review:
            if (review["source_image_sha256"] != row["image_sha256"]
                    or review["source_label_sha256"] != row["label_sha256"]):
                raise ValueError(f"review source hashes disagree: {sample_key}")
            proposed = review["label_text"].strip()
        else:
            if row["review_status"] != "legacy_positive_pending_full_image_review" or not original:
                raise ValueError(f"unreviewed nonpositive sample: {sample_key}")
            proposed = original
            legacy_count += 1
        final_text, class_counts, clipped = normalize_labels(proposed, len(SENSORS[sensor]), sample_key)
        if review:
            if (review["status"] == "approved_complete") != bool(class_counts):
                raise ValueError(f"review status conflicts with boxes: {sample_key}")
        elif not class_counts:
            raise ValueError(f"empty legacy positive: {sample_key}")
        if clipped:
            clipped_boxes.append({"key": sample_key, "boxes": clipped})
        images_dir = staging / sensor / "images" / split
        labels_dir = staging / sensor / "labels" / split
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        destination_image = images_dir / image.name
        destination_label = labels_dir / label.name
        if destination_image.exists() or destination_label.exists():
            raise ValueError(f"duplicate destination: {sample_key}")
        shutil.copy2(image, destination_image)
        destination_label.write_text(final_text + ("\n" if final_text else ""), encoding="utf-8")
        if digest(destination_image) != row["image_sha256"]:
            raise ValueError(f"image copy differs: {sample_key}")
        split_hashes[sensor][split].add(row["image_sha256"])
        if row.get("session_id"):
            split_sessions[sensor][split].add(row["session_id"])
        bucket = counts[sensor].setdefault(split, {"images": 0, "reviewed": 0,
                                                   "legacy_positive_unreviewed": 0,
                                                   "positive_images": 0, "negative_images": 0,
                                                   "class_instances": Counter()})
        bucket["images"] += 1
        bucket["reviewed" if review else "legacy_positive_unreviewed"] += 1
        bucket["positive_images" if class_counts else "negative_images"] += 1
        for cls, count in class_counts.items():
            bucket["class_instances"][SENSORS[sensor][cls]] += count
        if review:
            changes.append({"key": sample_key, "status": review["status"],
                            "original_label_sha256": row["label_sha256"],
                            "applied_label_sha256": digest(destination_label),
                            "original_label_text": original,
                            "applied_label_text": final_text,
                            "changed": original != final_text})

    for sensor in SENSORS:
        if split_hashes[sensor]["train"] & split_hashes[sensor]["validation"]:
            raise ValueError(f"cross-split image hash overlap: {sensor}")
        if split_sessions[sensor]["train"] & split_sessions[sensor]["validation"]:
            raise ValueError(f"cross-split session overlap: {sensor}")
        config = yaml.safe_load((source / sensor / "data.yaml").read_text(encoding="utf-8"))
        config["path"] = str(dataset / sensor)
        (staging / sensor / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        if tuple(config["names"].values()) != SENSORS[sensor]:
            raise ValueError(f"unexpected class names: {sensor}")
    if legacy_count != len(ledger) - len(reviews):
        raise ValueError("legacy positive count disagrees with ledger")
    for sensor in SENSORS:
        for split in ("train", "validation"):
            bucket = counts[sensor][split]
            bucket["class_instances"] = dict(bucket["class_instances"])
            image_stems = {p.stem for p in (staging / sensor / "images" / split).glob("*.jpg")}
            label_stems = {p.stem for p in (staging / sensor / "labels" / split).glob("*.txt")}
            if image_stems != label_stems or len(image_stems) != bucket["images"]:
                raise ValueError(f"derived inventory mismatch: {sensor} {split}")
    report = {
        "schema_version": "dji_recovery_review_application_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(source),
        "derived_dataset": str(dataset),
        "review_decisions_sha256": digest(review_path),
        "review_queue_count": len(queue),
        "review_decision_count": len(reviews),
        "legacy_positive_unreviewed": legacy_count,
        "counts": counts,
        "edge_rounding_clipped": clipped_boxes,
        "reviewed_label_changes": changes,
        "historically_exposed_development_validation": True,
        "strictly_unseen_test_available": False,
        "absolute_visual_localization": "unavailable",
    }
    shutil.copy2(review_path, staging / "review_decisions_snapshot.json")
    write_json(staging / "manifest.json", report)
    staging.rename(dataset)
    write_json(report_path, report)
    print(json.dumps({"derived_dataset": str(dataset), "reviewed": len(reviews),
                      "legacy_positive_unreviewed": legacy_count, "counts": counts,
                      "edge_rounding_clipped": len(clipped_boxes)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    build(parser.parse_args().root)
