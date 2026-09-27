#!/usr/bin/env python3
"""Server-only preflight and frozen-model diagnostic evaluation (never training)."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7')
DATA = ROOT / 'validation_label_audit_v1/round47_dev_diagnostic_v3'
OUT = ROOT / 'validation_label_audit_v1/round47_frozen_model_diagnostic_v2'
MODELS = {
    'V': ROOT / 'runs_round33_dedup/V_full100/weights/best.pt',
    'T': ROOT / 'runs_round33_dedup/T_full100/weights/best.pt',
}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def preflight():
    from PIL import Image
    manifest_path = DATA / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = manifest['records']
    if manifest['counts'] != {'V': 61, 'T': 66} or len(records) != 127:
        raise ValueError('manifest count mismatch')
    if manifest['training_authorized'] or manifest['blind_test_accessed'] or manifest['threshold_selection_authorized']:
        raise ValueError('invalid scope flags')
    counts = {'V': 0, 'T': 0}
    instances = {'V': [0, 0], 'T': [0]}
    for row in records:
        sensor = row['sensor']
        oid = row['observation_id']
        image = DATA / sensor / 'images/validation' / (oid + '.jpg')
        label = DATA / sensor / 'labels/validation' / (oid + '.txt')
        if not image.is_symlink() or not image.is_file() or not label.is_file():
            raise ValueError('broken derived sample: ' + oid)
        if sha256(image) != row['source_image_sha256'] or sha256(label) != row['selected_label_sha256']:
            raise ValueError('derived sample hash mismatch: ' + oid)
        Image.open(image).verify()
        n = 0
        for line in label.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) != 5:
                raise ValueError('bad label line: ' + oid)
            cls = int(parts[0])
            vals = [float(x) for x in parts[1:]]
            if cls not in range(len(instances[sensor])) or not all(0 <= v <= 1 for v in vals):
                raise ValueError('bad label values: ' + oid)
            if vals[2] <= 0 or vals[3] <= 0:
                raise ValueError('zero box: ' + oid)
            instances[sensor][cls] += 1
            n += 1
        if n != row['instances']:
            raise ValueError('label count mismatch: ' + oid)
        counts[sensor] += 1
    if counts != manifest['counts']:
        raise ValueError('record counts mismatch')
    for model in MODELS.values():
        if not model.is_file():
            raise FileNotFoundError(model)
    return {
        'status': 'passed', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'manifest': str(manifest_path), 'manifest_sha256': sha256(manifest_path),
        'counts': counts, 'instances': instances,
        'patch_count': sum(r['patched'] for r in records),
        'historically_exposed_dev_subset': True,
        'training_authorized': False, 'blind_test_accessed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    if OUT.exists():
        raise FileExistsError(OUT)
    report = preflight()
    OUT.mkdir(parents=True)
    (OUT / 'preflight.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not args.evaluate:
        print(json.dumps(report))
        return
    from ultralytics import YOLO
    metrics_out = {}
    for sensor, model_path in MODELS.items():
        model = YOLO(str(model_path))
        result = model.val(
            data=str(DATA / sensor / 'data.yaml'), split='val', imgsz=640,
            batch=8, device=0, workers=2, plots=True, verbose=False,
            project=str(OUT), name=sensor, exist_ok=False,
        )
        box = result.box
        metrics_out[sensor] = {
            'model': str(model_path), 'model_sha256': sha256(model_path),
            'dataset': str(DATA / sensor / 'data.yaml'),
            'images': report['counts'][sensor],
            'instances_by_class': report['instances'][sensor],
            'precision': [float(x) for x in box.p],
            'recall': [float(x) for x in box.r],
            'ap50': [float(x) for x in box.ap50],
            'map50': float(box.map50), 'map50_95': float(box.map),
            'save_dir': str(result.save_dir),
        }
        (OUT / (sensor + '_metrics.json')).write_text(json.dumps(metrics_out[sensor], indent=2), encoding='utf-8')
    summary = {
        'schema_version': 'dji_round47_frozen_model_diagnostic_v2',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'diagnose label and model behavior on a restricted historically exposed development subset',
        'not_a_full_validation_or_blind_test': True,
        'do_not_claim_gate_pass': True,
        'training_performed': False,
        'blind_test_accessed': False,
        'preflight': report,
        'metrics': metrics_out,
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'summary': str(OUT / 'summary.json'), 'metrics': metrics_out}))


if __name__ == '__main__':
    main()
