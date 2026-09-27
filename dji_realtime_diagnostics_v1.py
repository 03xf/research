"""Summarize observed track gaps and V/T overlap in prototype JSONL.

These are diagnostics of tracker output, not identity accuracy against truth.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def analyze(run):
    frames = defaultdict(dict)
    track_frames = defaultdict(list)
    with (run / 'results.jsonl').open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            sensor, seq = row['sensor'], row['frame_seq']
            frames[sensor][seq] = row
            for detection in row['raw_detections']:
                if detection['track_id']:
                    track_frames[(sensor, detection['track_id'])].append(seq)
    gap_counts = {'V': 0, 'T': 0}
    for (sensor, _), seqs in track_frames.items():
        gap_counts[sensor] += sum(b - a > 1 for a, b in zip(seqs, seqs[1:]))
    with (run / 'pairs.csv').open(encoding='utf-8-sig', newline='') as source:
        pairs = list(csv.DictReader(source))
    overlap = {'raw_both': 0, 'stable_both': 0}
    for pair in pairs:
        v = frames['V'][int(pair['V_frame_seq'])]
        t = frames['T'][int(pair['T_frame_seq'])]
        overlap['raw_both'] += bool(v['raw_detections']) and bool(t['raw_detections'])
        overlap['stable_both'] += (
            any(x['state'] == 'stable_candidate' for x in v['tracks'])
            and any(x['state'] == 'stable_candidate' for x in t['tracks'])
        )
    return {
        'run': run.name,
        'frames': {s: len(frames[s]) for s in ('V', 'T')},
        'track_counts': {s: sum(key[0] == s for key in track_frames) for s in ('V', 'T')},
        'same_id_detection_gaps': gap_counts,
        'pairs': len(pairs),
        'raw_any_both_pairs': overlap['raw_both'],
        'stable_any_both_pairs': overlap['stable_both'],
        'limit': 'No per-frame identity truth; gaps and overlap do not establish ID accuracy or same physical source.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runs', nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = [analyze(args.root / name) for name in args.runs]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))
