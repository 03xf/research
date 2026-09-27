"""Build a new server-side diagnostic dataset with reviewed patches and quarantine."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path("/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7")
SOURCE = ROOT / "datasets_round56_deconflicted_dev_v2"
INVALID = ROOT / "datasets_round77_patched_train_v1"
PATCH = ROOT / "data_integrity/round77_approved_train_patches_v1.json"
V_TRIAGE = ROOT / "data_integrity/round72_v_empty_label_triage_v1.json"
T_TRIAGE = ROOT / "data_integrity/round74_t_empty_label_triage_v1.json"
SPLIT_AUDIT = ROOT / "data_integrity/round68_split_audit_v1.json"
OUT = ROOT / "datasets_round79_deconflicted_patched_v2"
REPORT = ROOT / "data_integrity/round79_dataset_preflight_v2.json"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_label(path, class_count):
    counts = [0] * class_count
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split()
        assert len(fields) == 5, str(path)
        cls = int(fields[0])
        assert 0 <= cls < class_count, str(path)
        x, y, w, h = [float(v) for v in fields[1:]]
        assert w > 0 and h > 0, str(path)
        assert -1e-6 <= x - w/2 and x + w/2 <= 1.000001, str(path)
        assert -1e-6 <= y - h/2 and y + h/2 <= 1.000001, str(path)
        counts[cls] += 1
    return counts


def main():
    if OUT.exists() or REPORT.exists():
        raise SystemExit("Refusing to overwrite Round79 output")
    assert SOURCE.is_dir() and INVALID.is_dir()
    invalid_yaml = yaml.safe_load((INVALID / "V/data.yaml").read_text())
    assert Path(invalid_yaml["path"]) == SOURCE / "V"
    patches = json.loads(PATCH.read_text())
    v_triage = json.loads(V_TRIAGE.read_text())
    t_triage = json.loads(T_TRIAGE.read_text())
    split = json.loads(SPLIT_AUDIT.read_text())
    assert patches["approved_count"] == 4 and not patches["blind_test_accessed"]
    assert v_triage["clear_hidden_positive_count"] == 51 and v_triage["ambiguous_count"] == 5
    for sensor in ("V", "T"):
        for key in ("session_overlap", "observation_id_overlap", "exact_image_sha256_overlap",
                    "source_session_video_timestamp_overlap", "dhash_distance_le_4_candidates"):
            assert not split["sensors"][sensor][key], (sensor, key)
    patch_map = {(p["sensor"], p["observation_id"]): p for p in patches["patches"]}
    v_quarantine = {r["observation_id"] for r in v_triage["decisions"]
                    if r["status"] != "negative_candidate_contact_level_requires_original_resolution"}
    t_quarantine = set(t_triage["do_not_train_as_empty_until_review"])
    assert len(v_quarantine) == 56 and len(t_quarantine) == 3
    assert {p["observation_id"] for p in patches["patches"] if p["sensor"] == "V"} <= v_quarantine
    assert {p["observation_id"] for p in patches["patches"] if p["sensor"] == "T"} <= t_quarantine
    excluded = {"V": v_quarantine - {oid for sensor, oid in patch_map if sensor == "V"},
                "T": t_quarantine - {oid for sensor, oid in patch_map if sensor == "T"}}
    counts = {}
    for sensor, class_count in (("V", 2), ("T", 1)):
        counts[sensor] = {}
        for split_name in ("train", "validation"):
            image_src = SOURCE / sensor / "images" / split_name
            label_src = SOURCE / sensor / "labels" / split_name
            image_dst = OUT / sensor / "images" / split_name
            label_dst = OUT / sensor / "labels" / split_name
            image_dst.mkdir(parents=True, exist_ok=False)
            label_dst.mkdir(parents=True, exist_ok=False)
            source_images = sorted(image_src.glob("*.jpg"))
            assert {p.stem for p in source_images} == {p.stem for p in label_src.glob("*.txt")}
            class_counts = [0] * class_count
            included = []
            for image in source_images:
                stem = image.stem
                if split_name == "train" and stem in excluded[sensor]:
                    continue
                original_label = label_src / (stem + ".txt")
                target_image = image_dst / image.name
                target_label = label_dst / original_label.name
                shutil.copy2(image, target_image)
                patch = patch_map.get((sensor, stem)) if split_name == "train" else None
                if patch is None:
                    shutil.copy2(original_label, target_label)
                else:
                    assert sha(original_label) == patch["source_empty_label_sha256"]
                    assert not original_label.read_text().strip()
                    assert sha(image) == patch["image_sha256"]
                    target_label.write_text(patch["yolo_line"] + "\n")
                for cls, num in enumerate(check_label(target_label, class_count)):
                    class_counts[cls] += num
                if split_name == "validation":
                    assert sha(target_image) == sha(image) and sha(target_label) == sha(original_label)
                included.append(stem)
            counts[sensor][split_name] = {"images": len(included), "labels": len(included),
                                          "class_instances": class_counts,
                                          "empty_labels": sum(not p.read_text().strip() for p in label_dst.glob("*.txt"))}
        config = yaml.safe_load((SOURCE / sensor / "data.yaml").read_text())
        config["path"] = str(OUT / sensor)
        target_config = OUT / sensor / "data.yaml"
        target_config.write_text(yaml.safe_dump(config, sort_keys=False))
        parsed = yaml.safe_load(target_config.read_text())
        assert Path(parsed["path"]).resolve() == (OUT / sensor).resolve()
        assert (Path(parsed["path"]) / parsed["train"]).is_dir()
        assert (Path(parsed["path"]) / parsed["val"]).is_dir()
        assert int(parsed["nc"]) == class_count
    assert counts["V"]["train"]["images"] == 351
    assert counts["T"]["train"]["images"] == 431
    report = {
        "schema_version": "dji_round79_deconflicted_patched_diagnostic_dataset_v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(SOURCE), "source_manifest_sha256": sha(SOURCE / "manifest.json"),
        "invalid_round77_dataset": str(INVALID),
        "invalid_round77_reason": "Copied YAML path points to Round56, so Round77 training would not consume its patches.",
        "derived_dataset": str(OUT),
        "approved_patch_file": str(PATCH), "approved_patch_sha256": sha(PATCH),
        "v_triage": str(V_TRIAGE), "v_triage_sha256": sha(V_TRIAGE),
        "t_triage": str(T_TRIAGE), "t_triage_sha256": sha(T_TRIAGE),
        "split_audit": str(SPLIT_AUDIT), "split_audit_sha256": sha(SPLIT_AUDIT),
        "excluded_train_ids": {sensor: sorted(ids) for sensor, ids in excluded.items()},
        "patched_train_ids": {sensor: sorted(oid for s, oid in patch_map if s == sensor)
                              for sensor in ("V", "T")},
        "counts": counts,
        "yaml_paths_resolve_to_derived_dataset": True,
        "all_labels_class_and_bounds_checked": True,
        "validation_copied_byte_identically": True,
        "source_labels_modified": False,
        "historically_exposed_development_validation": True,
        "blind_test_accessed": False,
        "training_authorization": "diagnostic_smoke_only_after_separate_run_config_review",
        "caveat": "Remaining unreviewed positive geometry and empty-label candidates prevent qualified final training or evaluation claims.",
    }
    (OUT / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"dataset": str(OUT), "report": str(REPORT), "counts": counts}))


if __name__ == "__main__":
    main()
