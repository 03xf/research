"""Describe frozen E2 confirmation flame misses without tuning its threshold."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_evaluate import digest, image_matches, iou, totals


def classify(row, threshold):
    truth = [x for x in row['truth'] if x['class'] == 1]
    predictions = sorted((x for x in row['predictions']
                          if x['class'] == 1 and x['confidence'] >= threshold),
                         key=lambda x: x['confidence'], reverse=True)
    used = set()
    for prediction in predictions:
        choices = [(iou(prediction['xyxy'], target['xyxy']), j)
                   for j, target in enumerate(truth) if j not in used]
        best_iou, best_index = max(choices, default=(0, -1))
        if best_iou >= 0.5:
            used.add(best_index)
    results = []
    for j, target in enumerate(truth):
        area = ((target['xyxy'][2] - target['xyxy'][0])
                * (target['xyxy'][3] - target['xyxy'][1]))
        all_predictions = [x for x in row['predictions'] if x['class'] == 1]
        overlaps = [(iou(x['xyxy'], target['xyxy']), x['confidence'])
                    for x in all_predictions]
        best_iou = max((x[0] for x in overlaps), default=0)
        best_conf = max((x[1] for x in overlaps if x[0] >= 0.5), default=None)
        if j in used:
            cause = 'matched'
        elif any(overlap >= 0.5 and confidence < threshold
                 for overlap, confidence in overlaps):
            cause = 'below_work_threshold'
        elif any(overlap > 0 for overlap, confidence in overlaps):
            cause = 'box_truth_mismatch'
        else:
            cause = 'no_overlapping_flame_candidate'
        results.append({'pair_id': row['pair_id'], 'session_id': row['session_id'],
                        'truth_index': j, 'area_percent': round(100 * area, 6),
                        'area_bin': '<0.5%' if area < .005 else ('0.5–2%' if area < .02 else '>=2%'),
                        'cause': cause, 'max_candidate_iou': round(best_iou, 5),
                        'max_iou50_confidence': best_conf})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evaluation', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = json.loads((args.evaluation / 'result.json').read_text(encoding='utf-8'))
    predictions_path = args.evaluation / 'predictions_V.json'
    predictions = json.loads(predictions_path.read_text(encoding='utf-8'))['rows']
    threshold = next(x['threshold_from_development']
                     for x in report['sensors']['V']['classes'] if x['class_name'] == 'flame')
    details = [item for row in predictions for item in classify(row, threshold)]
    expected = totals(predictions, 1, threshold)
    observed = Counter(item['cause'] for item in details)
    if observed['matched'] != expected['tp'] or len(details) - observed['matched'] != expected['fn']:
        raise ValueError('one-to-one attribution disagrees with frozen evaluation')
    session = defaultdict(Counter)
    area = defaultdict(Counter)
    for item in details:
        session[item['session_id']][item['cause']] += 1
        area[item['area_bin']][item['cause']] += 1
    args.output.mkdir(parents=True)
    payload = {'schema_version': 'dji_flame_miss_attribution_v1',
               'created_utc': datetime.now(timezone.utc).isoformat(),
               'source_prediction_sha256': digest(predictions_path),
               'frozen_threshold': threshold, 'threshold_was_not_changed': True,
               'match_rule': 'same-class, one-to-one, IoU >= 0.5',
               'cause_rule': 'below threshold if any IoU>=0.5 low-confidence box; mismatch if any overlap; otherwise no overlapping candidate',
               'overall': dict(observed),
               'by_session': {k: dict(v) for k, v in session.items()},
               'by_area': {k: dict(v) for k, v in area.items()},
               'details': details}
    (args.output / 'attribution.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (args.output / 'attribution.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(details[0]))
        writer.writeheader()
        writer.writerows(details)
    print(json.dumps({'overall': payload['overall'], 'by_session': payload['by_session'],
                      'by_area': payload['by_area']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
