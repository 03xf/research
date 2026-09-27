"""Freeze the predeclared seed-0 flame candidate after seed-1/2 replication."""
import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from dji_flame_recall_dataset_v1 import digest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    work = args.root.resolve() / 'flame_recall_v1'
    output = work / 'candidate_freeze_v1.json'
    if output.exists():
        raise FileExistsError(output)
    selection_path = work / 'preliminary_selection_v1.json'
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    mode = selection['selected_mode']
    if mode not in ('C1', 'C2', 'C3') or selection['predeclared_confirmation_and_deployment_seed'] != 0:
        raise ValueError('no eligible or seed-0 candidate')
    results = []
    for seed in (0, 1, 2):
        path = work / 'evaluations' / f'{mode}_V_flame_960_s{seed}' / 'result.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        run_path = work / 'runs' / f'{mode}_V_flame_960_s{seed}' / 'run_config.json'
        run = json.loads(run_path.read_text(encoding='utf-8'))
        if (report['status'] != 'complete' or run['status'] != 'complete'
                or run['weights_best.pt_sha256'] != report['weights_sha256']):
            raise ValueError('replicate incomplete or weight mismatch: ' + str(seed))
        category = report['classes'][0]
        if category['class_name'] != 'flame' or category['ground_truth'] != 24:
            raise ValueError('development truth changed for replicate')
        results.append({'seed': seed, 'evaluation_result': str(path),
                        'evaluation_sha256': digest(path),
                        'weights': report['weights'], 'weights_sha256': report['weights_sha256'],
                        'threshold': category['work_threshold'],
                        'P': category['work_metrics']['precision'] if category['work_metrics'] else None,
                        'R': category['work_metrics']['recall'] if category['work_metrics'] else None,
                        'AP50': category['ap50'], 'gate_passed': category['gate_passed']})
    seed0 = results[0]
    selected = next(x for x in selection['candidates'] if x['mode'] == mode)
    if selected['weights_sha256'] != seed0['weights_sha256'] or selected['threshold'] != seed0['threshold']:
        raise ValueError('seed-0 result changed after development selection')
    payload = {'schema_version': 'dji_single_flame_candidate_freeze_v1',
               'created_utc': datetime.now(timezone.utc).isoformat(),
               'selection_sha256': digest(selection_path),
               'mode': mode, 'deployment_seed': 0,
               'weights': seed0['weights'], 'weights_sha256': seed0['weights_sha256'],
               'development_result': seed0['evaluation_result'],
               'development_result_sha256': seed0['evaluation_sha256'],
               'threshold': seed0['threshold'], 'class_mapping': {'0': 'flame'},
               'selection_uses_confirmation': False,
               'all_seed_results': results,
               'seed_gate_pass_count': sum(x['gate_passed'] for x in results),
               'seed_mean': {metric: statistics.mean(x[metric] for x in results) if all(
                                 x[metric] is not None for x in results) else None
                             for metric in ('P', 'R', 'AP50')},
               'seed_min_max': {metric: [min(x[metric] for x in results),
                                         max(x[metric] for x in results)] if all(
                                             x[metric] is not None for x in results) else None
                                for metric in ('P', 'R', 'AP50')},
               'caveat': 'Seed-0 was predeclared for confirmation and deployment; seed results are reported in full.'}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'mode': mode, 'threshold': payload['threshold'],
                      'seed_mean': payload['seed_mean'],
                      'seed_min_max': payload['seed_min_max']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
