"""Append the B4 flame experiment checkpoint to recovery status without erasing history."""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dji_flame_recall_dataset_v1 import digest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / 'flame_recall_v1'
    status_path = root / 'status_current.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    queue = work / 'review_queue_v1'
    decisions = json.loads((queue / 'review_decisions.json').read_text(encoding='utf-8'))['decisions']
    c2_run_path = work / 'runs' / 'C2_V_flame_960_s0' / 'run_config.json'
    c3_run_path = work / 'runs' / 'C3_V_flame_960_s0' / 'run_config.json'
    current_stage = ('flame_recall_C2_C3_training' if len(decisions) == 40 and
                     c2_run_path.is_file() and c3_run_path.is_file() else
                     'flame_recall_C1_dev_complete_review_pending')
    previous = status.get('stage')
    if previous != current_stage:
        history = root / 'status_history'
        history.mkdir(exist_ok=True)
        backup = history / ('pre_flame_recall_v1_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
        shutil.copyfile(status_path, backup)
    c1_data = work / 'datasets' / 'C1' / 'manifest.json'
    c1_run = work / 'runs' / 'C1_V_flame_960_s0' / 'run_config.json'
    c1_eval = work / 'evaluations' / 'C1_V_flame_960_s0' / 'result.json'
    attribution = work / 'frozen_E2_miss_attribution_v1' / 'attribution.json'
    run = json.loads(c1_run.read_text(encoding='utf-8'))
    evaluation = json.loads(c1_eval.read_text(encoding='utf-8'))
    if run['status'] != 'complete' or evaluation['status'] != 'complete':
        raise ValueError('C1 must be complete before checkpoint')
    category = evaluation['classes'][0]
    status['updated_utc'] = datetime.now(timezone.utc).isoformat()
    status['stage'] = current_stage
    status['flame_recall_v1'] = {
        'focus': 'B4 V flame misses',
        'frozen_E2_V_T_and_location_rules_unchanged': True,
        'training_source': 'B4 training-only V video DJI_202609081040_006',
        'review_queue_path': str(queue), 'review_queue_count': 40,
        'review_decision_count': len(decisions),
        'review_complete': len(decisions) == 40,
        'review_queue_sha256': digest(queue / 'queue.json'),
        'review_decisions_sha256': digest(queue / 'review_decisions.json'),
        'C1_dataset_manifest_sha256': digest(c1_data),
        'C1_run_config_sha256': digest(c1_run),
        'C1_weights_sha256': run['weights_best.pt_sha256'],
        'C1_development_result_sha256': digest(c1_eval),
        'C1_development': {'threshold': category['work_threshold'],
                           'P': category['work_metrics']['precision'],
                           'R': category['work_metrics']['recall'],
                           'AP50': category['ap50'],
                           'gate_passed': category['gate_passed']},
        'frozen_E2_miss_attribution_sha256': digest(attribution),
        'new_confirmation_evaluation_done': False,
        'C2_C3_pending_manual_review': len(decisions) < 40,
        'C2_dataset_manifest_sha256': digest(work / 'datasets' / 'C2' / 'manifest.json') if (work / 'datasets' / 'C2' / 'manifest.json').is_file() else None,
        'C3_dataset_manifest_sha256': digest(work / 'datasets' / 'C3' / 'manifest.json') if (work / 'datasets' / 'C3' / 'manifest.json').is_file() else None,
        'C2_train_status': json.loads(c2_run_path.read_text(encoding='utf-8'))['status'] if c2_run_path.is_file() else None,
        'C3_train_status': json.loads(c3_run_path.read_text(encoding='utf-8'))['status'] if c3_run_path.is_file() else None,
        'frozen_flame_review_sha256': digest(work / 'review_frozen_v1.json') if (work / 'review_frozen_v1.json').is_file() else None,
        'historical_V_train_labels_unreviewed': 335,
        'source_video_fixed_viewpoint_limit': True,
        'next_action': 'finish C2/C3; evaluate development; repeat selected mode seeds 1 and 2; freeze candidate; one confirmation comparison'}
    temp = status_path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, status_path)
    print(json.dumps({'stage': status['stage'], 'review_decisions': len(decisions),
                      'C1_development': status['flame_recall_v1']['C1_development']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
