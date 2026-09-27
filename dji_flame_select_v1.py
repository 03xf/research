"""Choose C1/C2/C3 using development data only and predeclare seed-0 deployment."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dji_flame_recall_dataset_v1 import digest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    work = args.root.resolve() / 'flame_recall_v1'
    output = work / 'preliminary_selection_v1.json'
    if output.exists():
        raise FileExistsError(output)
    val_maps = []
    candidates = []
    for mode in ('C1', 'C2', 'C3'):
        path = work / 'evaluations' / f'{mode}_V_flame_960_s0' / 'result.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        if report['status'] != 'complete' or report['images'] != 61:
            raise ValueError(f'incomplete development result {mode}')
        category = report['classes'][0]
        if category['class_name'] != 'flame' or category['ground_truth'] != 24:
            raise ValueError(f'development label cohort changed {mode}')
        manifest = json.loads((work / 'datasets' / mode / 'manifest.json').read_text(encoding='utf-8'))
        val_maps.append({row['image']: (row['source_image_sha256'], row['new_label_sha256'])
                         for row in manifest['records'] if row['split'] == 'validation'})
        run = json.loads((work / 'runs' / f'{mode}_V_flame_960_s0' / 'run_config.json').read_text(encoding='utf-8'))
        if run['status'] != 'complete' or run['weights_best.pt_sha256'] != report['weights_sha256']:
            raise ValueError(f'training/evaluation weight mismatch {mode}')
        candidates.append({'mode': mode, 'evaluation': str(path),
                           'evaluation_sha256': digest(path),
                           'weights': report['weights'],
                           'weights_sha256': report['weights_sha256'],
                           'threshold': category['work_threshold'],
                           'P': category['work_metrics']['precision'] if category['work_metrics'] else None,
                           'R': category['work_metrics']['recall'] if category['work_metrics'] else None,
                           'AP50': category['ap50'], 'gate_passed': category['gate_passed'],
                           'false_positive': category['work_metrics']['fp'] if category['work_metrics'] else None})
    if not val_maps[0] == val_maps[1] == val_maps[2]:
        raise ValueError('C1/C2/C3 development images or labels differ')
    baseline_path = args.root.resolve() / 'evaluations' / 'E2_V_960_s0' / 'result.json'
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    baseline_flame = next(x for x in baseline['classes'] if x['class_name'] == 'flame')
    baseline_work = baseline_flame['work_metrics']
    eligible = [x for x in candidates if x['gate_passed'] and x['R'] > baseline_work['recall']]
    selected = max(eligible, key=lambda x: (x['R'], x['AP50'], x['P'], -int(x['mode'][1:]))) if eligible else None
    payload = {'schema_version': 'dji_flame_preliminary_development_selection_v1',
               'created_utc': datetime.now(timezone.utc).isoformat(),
               'selection_source': '61-image development split only; no new confirmation access',
               'rule': 'gate P>=0.60,R>=0.70,AP50>=0.50 and R above E2; highest R, then AP50, then P, then simpler C mode',
               'E2_development_result_sha256': digest(baseline_path),
               'E2_development_flame': {'P': baseline_work['precision'],
                                        'R': baseline_work['recall'],
                                        'AP50': baseline_flame['ap50']},
               'candidates': candidates, 'selected_mode': selected['mode'] if selected else None,
               'seed_repetitions_required': [1, 2] if selected else [],
               'predeclared_confirmation_and_deployment_seed': 0,
               'confirmation_not_used_for_selection': True}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'selected_mode': payload['selected_mode'],
                      'candidates': [{k: x[k] for k in ('mode', 'P', 'R', 'AP50', 'threshold', 'gate_passed')}
                                     for x in candidates]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
