"""Add small-scale copies of the 40 reviewed B4 flame training images to C3."""
import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from recovery_v1_prepare import check_label


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scaled_label(text, scale):
    result = []
    offset = (1.0 - scale) / 2.0
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5 or fields[0] != "0":
            raise ValueError("C3 label must contain only flame class 0")
        x, y, width, height = map(float, fields[1:])
        result.append("0 " + " ".join(f"{v:.8f}" for v in
                                  (offset + scale*x, offset + scale*y,
                                   scale*width, scale*height)))
    output = "\n".join(result) + ("\n" if result else "")
    check_label(output, 1)
    return output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / "detection_quality_v2"
    source = root / "flame_recall_v1/datasets/C3"
    target = work / "datasets/C4"
    if target.exists():
        raise FileExistsError(target)
    policy_path = work / "policy_C4.json"
    parent = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if parent["mode"] != "C3" or parent["counts"] != {"train": 427, "validation": 61}:
        raise ValueError("C3 parent dataset changed")
    reviewed = [record for record in parent["records"]
                if record["split"] == "train" and record.get("review_override")]
    if len(reviewed) != 40:
        raise ValueError("expected 40 reviewed flame images")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="C4.building.", dir=target.parent) as temp:
        staged = Path(temp)
        records = []
        for split in ("train", "validation"):
            for kind in ("images", "labels"):
                (staged / "V" / kind / split).mkdir(parents=True)
            for image in sorted((source / "V/images" / split).glob("*.jpg")):
                label = source / "V/labels" / split / (image.stem + ".txt")
                if not label.is_file():
                    raise FileNotFoundError(label)
                dest_image = staged / "V/images" / split / image.name
                dest_label = staged / "V/labels" / split / label.name
                shutil.copyfile(image, dest_image)
                shutil.copyfile(label, dest_label)
                records.append({"split": split, "image": image.name,
                                "image_sha256": digest(dest_image),
                                "label_sha256": digest(dest_label), "synthetic": False})
        for item in reviewed:
            image = source / "V/images/train" / item["image"]
            label = source / "V/labels/train" / (image.stem + ".txt")
            if digest(image) != item["source_image_sha256"]:
                raise ValueError("reviewed parent image changed: " + image.name)
            text = label.read_text(encoding="utf-8")
            if not text.strip():
                raise ValueError("reviewed augmentation source has no flame: " + image.name)
            with Image.open(image) as original:
                original = original.convert("RGB")
                width, height = original.size
                for scale in (0.50, 0.70):
                    name = f"c4_s{int(scale*100)}_{image.stem}"
                    output_image = staged / "V/images/train" / (name + ".jpg")
                    output_label = staged / "V/labels/train" / (name + ".txt")
                    small = original.resize((round(width*scale), round(height*scale)),
                                            getattr(Image, "Resampling", Image).LANCZOS)
                    canvas = Image.new("RGB", (width, height), (114, 114, 114))
                    canvas.paste(small, ((width-small.width)//2, (height-small.height)//2))
                    canvas.save(output_image, quality=95)
                    output_label.write_text(scaled_label(text, scale), encoding="utf-8")
                    records.append({"split": "train", "image": output_image.name,
                                    "image_sha256": digest(output_image),
                                    "label_sha256": digest(output_label),
                                    "synthetic": True, "parent_image": image.name,
                                    "parent_image_sha256": digest(image), "scale": scale})
        counts = {split: sum(row["split"] == split for row in records)
                  for split in ("train", "validation")}
        if counts != {"train": 507, "validation": 61}:
            raise ValueError("C4 count mismatch")
        hashes = {split: {row["image_sha256"] for row in records if row["split"] == split}
                  for split in counts}
        if len(hashes["train"]) != counts["train"] or hashes["train"] & hashes["validation"]:
            raise ValueError("duplicate or validation leakage")
        snapshot = source / "review_decisions_snapshot.json"
        shutil.copyfile(snapshot, staged / snapshot.name)
        (staged / "V/data.yaml").write_text(
            f"path: {target / 'V'}\ntrain: images/train\nval: images/validation\n"
            "names:\n  0: flame\nnc: 1\n", encoding="utf-8")
        manifest = {"schema_version": "dji_b4_flame_C4_small_scale_dataset_v1",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "derived_dataset": str(target), "source_dataset": str(source),
                    "source_dataset_manifest_sha256": digest(source / "manifest.json"),
                    "review_decisions_sha256": digest(snapshot),
                    "flame_review_decisions_sha256": parent["flame_review_decisions_sha256"],
                    "legacy_positive_unreviewed": parent["legacy_positive_unreviewed"],
                    "policy_sha256": digest(policy_path),
                    "counts": counts, "synthetic_count": 80,
                    "synthetic_source_count": 40,
                    "validation_unchanged": True,
                    "confirmation_training_excluded": True,
                    "records": records}
        (staged / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
        staged.rename(target)
    print(json.dumps({"dataset": str(target), "counts": counts,
                      "manifest_sha256": digest(target / "manifest.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
