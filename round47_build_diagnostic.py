#!/usr/bin/env python3
"""Build a non-training, non-blind diagnostic validation subset from reviewed labels."""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7')
SRC = ROOT / 'datasets_round27_labels_fixed_v1'
AUDIT = ROOT / 'validation_label_audit_v1'
OUT = AUDIT / 'round47_dev_diagnostic_v3'
V_EXCLUDE = {
    'obs_v7_val_0002', 'obs_v7_val_0004', 'obs_v7_val_0006',
    'obs_v7_val_0008', 'obs_v7_val_0010', 'obs_v7_val_0012',
    'obs_v7_val_0014', 'obs_v7_val_0016', 'obs_v7_val_0018',
    'obs_v7_val_0020',
}
T_EXCLUDE = {'obs_000556', 'obs_000566', 'obs_000652', 'obs_000661', 'obs_000697'}
PATCH_PROVENANCES = [
    AUDIT / 'round41_partial_thermal_patches/provenance.json',
    AUDIT / 'round43_approved_empty_T_patches/provenance.json',
    AUDIT / 'round46_approved_empty_T_patches_v1/provenance.json',
]


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def parse_label(path, nc):
    count = 0
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError('invalid YOLO field count: ' + str(path))
        cls = int(parts[0])
        xywh = [float(v) for v in parts[1:]]
        if not (0 <= cls < nc and all(0 <= v <= 1 for v in xywh) and xywh[2] > 0 and xywh[3] > 0):
            raise ValueError('invalid YOLO values: ' + str(path))
        if xywh[0]-xywh[2]/2 < -1e-7 or xywh[0]+xywh[2]/2 > 1+1e-7 or xywh[1]-xywh[3]/2 < -1e-7 or xywh[1]+xywh[3]/2 > 1+1e-7:
            raise ValueError('YOLO box out of bounds: ' + str(path))
        count += 1
    return count


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    if not str(OUT).startswith('/home/member/xmy/xmy/'):
        raise ValueError('outside allowed server scope')
    patches = {}
    provenance_hashes = []
    for prov in PATCH_PROVENANCES:
        provenance_hashes.append({'path': str(prov), 'sha256': sha256(prov)})
        data = json.loads(prov.read_text(encoding='utf-8'))
        for row in data['patches']:
            oid = row['observation_id']
            if oid in patches:
                raise ValueError('duplicate patch: ' + oid)
            patches[oid] = row
    if len(patches) != 18:
        raise ValueError('expected 18 reviewed thermal patches, got ' + str(len(patches)))
    if any(oid in T_EXCLUDE for oid in patches):
        raise ValueError('excluded thermal ID has a patch')
    records = []
    for sensor, exclusions, nc, names in [
        ('V', V_EXCLUDE, 2, ['smoke', 'flame']),
        ('T', T_EXCLUDE, 1, ['hotspot']),
    ]:
        src_images = SRC / sensor / 'images/validation'
        src_labels = SRC / sensor / 'labels/validation'
        images = sorted(src_images.glob('*.jpg'))
        if len(images) != 71:
            raise ValueError(f'expected 71 {sensor} images, got {len(images)}')
        if not exclusions.issubset({p.stem for p in images}):
            raise ValueError('unknown exclusions for ' + sensor)
        dst = OUT / sensor
        (dst / 'images/validation').mkdir(parents=True)
        (dst / 'images/train').mkdir(parents=True)
        (dst / 'labels/validation').mkdir(parents=True)
        for image in images:
            oid = image.stem
            if oid in exclusions:
                continue
            label = src_labels / (oid + '.txt')
            if not label.is_file():
                raise FileNotFoundError(label)
            selected = label
            patch = patches.get(oid) if sensor == 'T' else None
            if patch:
                if sha256(image) != patch['source_image_sha256'] or sha256(label) != patch['source_label_sha256']:
                    raise ValueError('patch source changed: ' + oid)
                selected = Path(patch['patch_label'])
                if sha256(selected) != patch['patch_label_sha256']:
                    raise ValueError('patch hash changed: ' + oid)
            instances = parse_label(selected, nc)
            os.symlink(image, dst / 'images/validation' / image.name)
            shutil.copyfile(selected, dst / 'labels/validation' / label.name)
            records.append({
                'sensor': sensor, 'observation_id': oid,
                'source_image': str(image), 'source_image_sha256': sha256(image),
                'source_label': str(label), 'source_label_sha256': sha256(label),
                'selected_label': str(selected), 'selected_label_sha256': sha256(selected),
                'patched': bool(patch), 'instances': instances,
            })
        yaml = 'path: ' + str(dst) + '\ntrain: images/train\nval: images/validation\nnames:\n' + ''.join(f'  {i}: {n}\n' for i, n in enumerate(names)) + f'nc: {nc}\n'
        (dst / 'data.yaml').write_text(yaml, encoding='utf-8')
    counts = {s: sum(r['sensor'] == s for r in records) for s in ('V','T')}
    if counts != {'V': 61, 'T': 66}:
        raise ValueError('unexpected diagnostic subset counts: ' + str(counts))
    manifest = {
        'schema_version': 'dji_round47_dev_diagnostic_v3',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_dataset': str(SRC),
        'source_dataset_yaml_warning': 'The source data.yaml points to older roots; this derived subset uses new absolute roots.',
        'status': 'development_diagnostic_only',
        'historical_validation_model_exposure': True,
        'training_authorized': False,
        'threshold_selection_authorized': False,
        'blind_test_accessed': False,
        'full_validation_claim_authorized': False,
        'source_validation_modified': False,
        'V_excluded': sorted(V_EXCLUDE),
        'T_excluded': sorted(T_EXCLUDE),
        'counts': counts,
        'patch_provenances': provenance_hashes,
        'records': records,
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'root': str(OUT), 'counts': counts, 'patched_T': sum(r['patched'] for r in records)}))


if __name__ == '__main__':
    main()
