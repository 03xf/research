"""One-time confirmation evaluation of a development-frozen single-class V model."""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_confirm_evaluate import parse_labels
from recovery_v1_evaluate import average_precision, digest, totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--freeze', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--device', default='0')
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    root = args.root.resolve()
    manifest_path = root / 'confirmation_10s_v2' / 'manifest.json'
    decisions_path = root / 'confirmation_10s_v2' / 'decisions_frozen_v1.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    decisions = json.loads(decisions_path.read_text(encoding='utf-8'))['decisions']
    freeze = json.loads(args.freeze.read_text(encoding='utf-8'))
    if len(manifest['pairs']) != 194 or manifest['pair_count'] != 194 or manifest['unpaired_count']:
        raise ValueError('confirmation cohort differs from frozen 194 pairs')
    if {x['pair_id'] for x in manifest['pairs']} != set(decisions):
        raise ValueError('confirmation labels incomplete')
    weights = Path(freeze['weights'])
    development_path = Path(freeze['development_result'])
    development = json.loads(development_path.read_text(encoding='utf-8'))
    category = development['classes'][0]
    if (digest(weights) != freeze['weights_sha256']
            or digest(development_path) != freeze['development_result_sha256']
            or development['weights_sha256'] != freeze['weights_sha256']
            or category['class_name'] != 'flame'
            or category['work_threshold'] != freeze['threshold']
            or not category['gate_passed']):
        raise ValueError('candidate freeze does not match development result')
    os.environ['WANDB_MODE'] = 'disabled'
    os.environ['WANDB_DISABLED'] = 'true'
    os.environ['COMET_MODE'] = 'DISABLED'
    sys.path.insert(0, '/home/member/xmy/xmy/code/projects/ultralytics')
    from ultralytics import YOLO
    model = YOLO(str(weights))
    for module in model.model.modules():
        if type(module).__name__ == 'GELU' and not hasattr(module, 'approximate'):
            module.approximate = 'none'
    if set(model.names) != {0} or model.names[0] != 'flame':
        raise ValueError('single-class model mapping is not 0: flame')
    args.output.mkdir(parents=True)
    rows = []
    for pair in manifest['pairs']:
        pair_id = pair['pair_id']
        observation = pair['V']
        decision = decisions[pair_id]['V']
        image = Path(observation['file'])
        if (decision['status'] != 'complete' or decision['image_sha256'] != observation['sha256']
                or digest(image) != observation['sha256']):
            raise ValueError('confirmation image/label mismatch: ' + pair_id)
        original_truth = parse_labels(decision['label_text'], 'V', pair_id)
        truth = [{**box, 'class': 0} for box in original_truth if box['class'] == 1]
        result = model.predict(source=str(image), imgsz=960, conf=0.001, iou=0.7,
                               max_det=300, device=args.device, half=False,
                               augment=False, save=False, verbose=False)[0]
        height, width = result.orig_shape
        predictions = []
        for coords, confidence, category_id in zip(result.boxes.xyxy.cpu().tolist(),
                                                   result.boxes.conf.cpu().tolist(),
                                                   result.boxes.cls.cpu().tolist()):
            if int(category_id) != 0:
                raise ValueError('unexpected predicted class')
            predictions.append({'class': 0, 'confidence': float(confidence),
                                'xyxy': [coords[0] / width, coords[1] / height,
                                         coords[2] / width, coords[3] / height]})
        rows.append({'pair_id': pair_id, 'session_id': pair['session_id'],
                     'image_sha256': observation['sha256'], 'truth': truth,
                     'predictions': predictions})
    from recovery_v1_evaluate import write_json
    write_json(args.output / 'predictions_V.json', {'sensor': 'V', 'rows': rows})
    threshold = freeze['threshold']
    aps = [average_precision(rows, 0, round(.5 + i * .05, 2)) for i in range(10)]
    by_session = {}
    for session in sorted({row['session_id'] for row in rows}):
        subset = [row for row in rows if row['session_id'] == session]
        by_session[session] = {'images': len(subset),
                               'ground_truth': sum(len(row['truth']) for row in subset),
                               **totals(subset, 0, threshold)}
    work = totals(rows, 0, threshold)
    report = {'schema_version': 'dji_single_flame_confirmation_v1',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'historically_exposed_exploratory': True,
              'threshold_source': 'development freeze; no confirmation scan',
              'frozen_candidate_sha256': digest(args.freeze),
              'confirmation_manifest_sha256': digest(manifest_path),
              'confirmation_decisions_sha256': digest(decisions_path),
              'weights_sha256': freeze['weights_sha256'],
              'threshold': threshold, 'class_mapping': {'0': 'flame'},
              'image_count': len(rows), 'ground_truth': sum(len(row['truth']) for row in rows),
              'work_metrics': work, 'AP50': aps[0], 'AP50_95': sum(aps) / len(aps),
              'by_session': by_session,
              'gate_passed': work['precision'] >= .6 and work['recall'] >= .7 and aps[0] >= .5,
              'predictions_sha256': digest(args.output / 'predictions_V.json')}
    write_json(args.output / 'result.json', report)
    print(json.dumps({'work_metrics': work, 'AP50': aps[0],
                      'by_session': by_session, 'gate_passed': report['gate_passed']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
