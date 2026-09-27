"""Prepare a traceable diagnostic dataset for the DJI recovery experiment.

Run on the server. This never changes the source dataset or historical state.json.
"""

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml
from PIL import Image


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
SOURCE_NAME = "datasets_round56_deconflicted_dev_v2"
SENSORS = {"V": ("smoke", "flame"), "T": ("hotspot",)}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def check_label(text, class_count):
    counts = Counter()
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError("YOLO label must contain five fields")
        cls = int(fields[0])
        x, y, w, h = (float(value) for value in fields[1:])
        if cls not in range(class_count) or not all(math.isfinite(v) for v in (x, y, w, h)):
            raise ValueError("invalid class or non-finite box")
        if w <= 0 or h <= 0 or x - w / 2 < -1e-6 or x + w / 2 > 1 + 1e-6:
            raise ValueError("horizontal box bounds invalid")
        if y - h / 2 < -1e-6 or y + h / 2 > 1 + 1e-6:
            raise ValueError("vertical box bounds invalid")
        counts[cls] += 1
    return dict(counts)


def current_status(root):
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    return {
        "recorded_stage": state.get("stage"),
        "recorded_updated_utc": state.get("updated_utc"),
        "round77_invalid_yaml": yaml.safe_load(
            (root / "datasets_round77_patched_train_v1/V/data.yaml").read_text(encoding="utf-8")
        )["path"] == str(root / SOURCE_NAME / "V"),
        "round79_exists": (root / "datasets_round79_deconflicted_patched_v2").exists(),
        "development_set_historically_exposed": True,
        "strictly_unseen_test_available": False,
        "absolute_visual_localization_available": False,
    }


def prepare(root, out):
    source = root / SOURCE_NAME
    if not source.is_dir():
        raise FileNotFoundError(source)
    if out.exists():
        raise FileExistsError(out)
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    original = {
        row["observation_id"]: row
        for row in json.loads((root / "manifest_round12.json").read_text(encoding="utf-8"))["observations"]
    }
    v_triage = json.loads((root / "data_integrity/round72_v_empty_label_triage_v1.json").read_text(encoding="utf-8"))
    t_triage = json.loads((root / "data_integrity/round74_t_empty_label_triage_v1.json").read_text(encoding="utf-8"))
    patches = json.loads((root / "data_integrity/round77_approved_train_patches_v1.json").read_text(encoding="utf-8"))
    split = json.loads((root / "data_integrity/round68_split_audit_v1.json").read_text(encoding="utf-8"))
    patch_map = {(row["sensor"], row["observation_id"]): row for row in patches["patches"]}
    v_status = {row["observation_id"]: row["status"] for row in v_triage["decisions"]}
    t_status = {row["observation_id"]: row["status"] for row in t_triage["decisions"]}
    if patches["approved_count"] != 4 or not patches["approved_for_training"]:
        raise ValueError("unexpected approved patch list")
    for sensor in SENSORS:
        for key in ("session_overlap", "observation_id_overlap", "exact_image_sha256_overlap",
                    "source_session_video_timestamp_overlap", "dhash_distance_le_4_candidates"):
            if split["sensors"][sensor][key]:
                raise ValueError(f"split conflict: {sensor} {key}")

    # This version quarantines every empty train label, including four partial patches.
    # A single corrected box cannot certify all objects in its image are annotated.
    records = []
    review = []
    counts = {}
    out.mkdir(parents=True)
    dataset = out / "dataset_diagnostic_v1"
    for sensor, names in SENSORS.items():
        counts[sensor] = {}
        for split_name in ("train", "validation"):
            src_images = source / sensor / "images" / split_name
            src_labels = source / sensor / "labels" / split_name
            dst_images = dataset / sensor / "images" / split_name
            dst_labels = dataset / sensor / "labels" / split_name
            dst_images.mkdir(parents=True)
            dst_labels.mkdir(parents=True)
            images = sorted(src_images.glob("*.jpg"))
            if {p.stem for p in images} != {p.stem for p in src_labels.glob("*.txt")}:
                raise ValueError(f"image/label inventory mismatch: {sensor} {split_name}")
            included = 0
            excluded = 0
            class_counts = Counter()
            for image in images:
                label = src_labels / (image.stem + ".txt")
                label_text = label.read_text(encoding="utf-8")
                image_hash, label_hash = digest(image), digest(label)
                boxes = check_label(label_text, len(names))
                with Image.open(image) as handle:
                    dimensions = list(handle.size)
                source_record = original.get(image.stem)
                if source_record is None:
                    raise ValueError(f"observation absent from complete manifest: {image.stem}")
                patch = patch_map.get((sensor, image.stem))
                if split_name == "train" and not boxes:
                    review_status = "approved_single_box_but_full_image_pending" if patch else "empty_label_pending_full_image_review"
                    include = False
                elif split_name == "train":
                    review_status = "legacy_positive_pending_full_image_review"
                    include = True
                else:
                    review_status = "development_label_pending_independent_review"
                    include = True
                record = {
                    "observation_id": image.stem, "sensor": sensor, "split": split_name,
                    "batch_id": source_record.get("batch_id"), "session_id": source_record.get("session_id"),
                    "video_group": source_record.get("video_group"), "source_video": source_record.get("source_video"),
                    "timestamp_s": source_record.get("timestamp_s"), "image": str(image), "image_sha256": image_hash,
                    "image_size": dimensions, "label": str(label), "label_sha256": label_hash,
                    "class_counts": {names[int(k)]: v for k, v in boxes.items()}, "included_in_diagnostic": include,
                    "review_status": review_status, "triage_status": (v_status if sensor == "V" else t_status).get(image.stem),
                    "proposed_patch": patch["yolo_line"] if patch else None,
                    "independent_reviewer": None, "full_image_complete": False,
                }
                records.append(record)
                if review_status != "legacy_positive_pending_full_image_review":
                    review.append({"observation_id": image.stem, "sensor": sensor, "split": split_name,
                                   "priority": 1 if patch or (split_name == "train" and not boxes) else 2,
                                   "image": str(image), "label": str(label), "review_status": review_status})
                if include:
                    shutil.copy2(image, dst_images / image.name)
                    shutil.copy2(label, dst_labels / label.name)
                    if digest(dst_images / image.name) != image_hash or digest(dst_labels / label.name) != label_hash:
                        raise ValueError(f"copy mismatch: {sensor} {split_name} {image.stem}")
                    included += 1
                    class_counts.update(boxes)
                else:
                    excluded += 1
            counts[sensor][split_name] = {"source": len(images), "included": included, "excluded": excluded,
                                          "class_instances": {names[k]: class_counts[k] for k in range(len(names))}}
        config = yaml.safe_load((source / sensor / "data.yaml").read_text(encoding="utf-8"))
        config["path"] = str(dataset / sensor)
        (dataset / sensor / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        parsed = yaml.safe_load((dataset / sensor / "data.yaml").read_text(encoding="utf-8"))
        if Path(parsed["path"]).resolve() != (dataset / sensor).resolve():
            raise ValueError(f"YAML points away from derived dataset: {sensor}")
        for key in ("train", "val"):
            if not (Path(parsed["path"]) / parsed[key]).is_dir():
                raise ValueError(f"missing YAML split: {sensor} {key}")
    report = {
        "schema_version": "dji_recovery_preparation_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source), "source_manifest_sha256": digest(source / "manifest.json"),
        "derived_dataset": str(dataset), "counts": counts, "review_queue_count": len(review),
        "round77_invalid": current_status(root)["round77_invalid_yaml"],
        "yaml_paths_point_to_derived_dataset": True, "all_copied_bytes_match_source": True,
        "all_train_empty_labels_quarantined": True, "four_partial_patches_quarantined": True,
        "development_labels_unchanged_and_historically_exposed": True,
        "blind_test_accessed": False,
        "training_status": "diagnostic_only_pending_full_image_and_independent_development_review",
    }
    write_new(out / "current_status.json", current_status(root))
    write_new(out / "sample_ledger.json", {"schema_version": "dji_recovery_sample_ledger_v1", "records": records})
    write_new(out / "review_queue.json", {"schema_version": "dji_recovery_review_queue_v1", "items": review})
    write_new(out / "review_decisions.json", {"schema_version": "dji_recovery_review_decisions_v1", "decisions": []})
    write_new(dataset / "manifest.json", report)
    write_new(out / "preflight.json", report)
    print(json.dumps({"output": str(out), "counts": counts, "review_queue": len(review)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    prepare(args.root, args.out or args.root / "recovery_v1")
