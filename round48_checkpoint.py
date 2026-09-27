#!/usr/bin/env python3
"""Record Round47 diagnostic evidence and next training-label audit checkpoint."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7')
AUDIT = ROOT / 'data_integrity/round48_train_triage_v1'
STATE = ROOT / 'state.json'
DIAG = ROOT / 'validation_label_audit_v1/round47_frozen_model_diagnostic_v2/summary.json'
SOURCE = ROOT / 'datasets_round33_train_dedup_v1/V'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    if AUDIT.exists():
        raise FileExistsError(AUDIT)
    diag = json.loads(DIAG.read_text(encoding='utf-8'))
    if not diag['not_a_full_validation_or_blind_test'] or not diag['blind_test_accessed'] is False:
        raise ValueError('diagnostic scope mismatch')
    findings = {
        'obs_v7_train_0006': 'Visible flame and diffuse smoke; retained V label has flame only. Smoke extent needs independent box adjudication.',
        'obs_v7_train_0007': 'Visible flame and smoke; retained V label has only a small flame box, omitting smoke and much of visible flame. Redraw both.',
        'obs_v7_train_0024': 'Small visible flame near the far burn pile; retained V label calls a large foreground region smoke. Class and geometry require correction.',
        'obs_v7_train_0027': 'Two spatially distinct smoke sources; retained V label covers only the left source. Right source and grouping require redraw.',
    }
    rows = []
    for oid, finding in findings.items():
        image = SOURCE / 'images/train' / (oid + '.jpg')
        label = SOURCE / 'labels/train' / (oid + '.txt')
        if not image.is_file() or not label.is_file():
            raise FileNotFoundError(oid)
        rows.append({
            'observation_id': oid, 'finding': finding,
            'source_image': str(image), 'source_image_sha256': sha256(image),
            'source_label': str(label), 'source_label_sha256': sha256(label),
            'label_text': label.read_text(encoding='utf-8'),
            'geometry_approved': False,
        })
    report = {
        'schema_version': 'dji_round48_train_label_triage_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_duplicate_review': str(ROOT / 'data_integrity/round34_presence_review/round34_duplicate_review_checkpoint_v1.json'),
        'scope': 'four high-priority kept training frames from known same-source-time duplicate conflicts',
        'frames_reviewed': len(rows),
        'class_and_geometry_approved': 0,
        'source_train_modified': False,
        'derived_training_dataset_created': False,
        'blind_test_accessed': False,
        'next_action': 'Complete exact image-only V/T box adjudication for 35 conflicting training pairs, then build versioned training data and run split/label QC before retraining.',
        'rows': rows,
    }
    AUDIT.mkdir(parents=True)
    path = AUDIT / 'train_triage.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    state = json.loads(STATE.read_text(encoding='utf-8'))
    if state.get('stage') != 'round33_dedup_validation_failed':
        raise ValueError('state changed; refuse to overwrite stage')
    state['stage'] = 'round47_diagnostic_gate_not_met_training_label_audit'
    state['round47'] = {
        'diagnostic_summary': str(DIAG),
        'diagnostic_summary_sha256': sha256(DIAG),
        'train_triage': str(path),
        'train_triage_sha256': sha256(path),
        'development_subset_only': True,
        'validation_full_repair_complete': False,
        'training_label_repair_complete': False,
        'detection_gate_passed': False,
        'blind_test_accessed': False,
        'absolute_localization_permitted': False,
    }
    state['next_action'] = report['next_action']
    state['updated_utc'] = datetime.now(timezone.utc).isoformat()
    tmp = STATE.with_name('state.round48_tmp.json')
    with tmp.open('x', encoding='utf-8') as stream:
        json.dump(state, stream, indent=2, ensure_ascii=False)
    os.replace(str(tmp), str(STATE))
    print(json.dumps({'stage': state['stage'], 'report': str(path), 'diagnostic': str(DIAG)}))


if __name__ == '__main__':
    main()
