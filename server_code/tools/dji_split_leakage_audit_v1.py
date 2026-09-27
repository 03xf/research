#!/usr/bin/env python3
'''Audit DJI V/T train-validation separation without opening reserved test frames.'''
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
from PIL import Image


def dhash(path):
    image = Image.open(path).convert('L').resize((9, 8), Image.LANCZOS)
    values = list(image.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (values[y * 9 + x] > values[y * 9 + x + 1])
    return bits


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('refusing to overwrite output')
    root = args.root
    manifest = json.loads((root / 'manifest_round12.json').read_text(encoding='utf-8'))['observations']
    blind = json.loads((root / 'blind_test_manifest.json').read_text(encoding='utf-8'))['observations']
    sessions = collections.defaultdict(set)
    ids = collections.defaultdict(set)
    quality = collections.Counter()
    source_splits = collections.Counter()
    for item in manifest:
        split = item['split']
        sessions[split].add((item['session_id'], item['drone_id']))
        ids[split].add(item['observation_id'])
        quality[(split, item['annotation']['annotation_quality'])] += 1
        source_splits[(split, str(item.get('source_split')))] += 1
    blind_sessions = {(x['session_id'], x['drone_id']) for x in blind}
    result = {'schema_version': 'dji_split_leakage_audit_v1',
              'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'manifest': str(root / 'manifest_round12.json'),
              'test_frame_files_opened': False,
              'blind_test_labels_opened': False,
              'blind_manifest_metadata_read': True,
              'train_validation_session_overlap': sorted(list(sessions['train'] & sessions['validation'])),
              'train_blind_session_overlap': sorted(list(sessions['train'] & blind_sessions)),
              'validation_blind_session_overlap': sorted(list(sessions['validation'] & blind_sessions)),
              'train_validation_observation_id_overlap': sorted(list(ids['train'] & ids['validation'])),
              'quality_counts': {str(k): v for k, v in quality.items()},
              'source_split_counts': {str(k): v for k, v in source_splits.items()},
              'sensors': {}}
    for sensor in ('V', 'T'):
        data = root / 'datasets_round27_labels_fixed_v1' / sensor
        train = sorted((data / 'images/train').glob('*.jpg'))
        validation = sorted((data / 'images/validation').glob('*.jpg'))
        train_sha = {file_sha(p): p for p in train}
        val_sha = {file_sha(p): p for p in validation}
        exact = [{'train': str(train_sha[h]), 'validation': str(val_sha[h])}
                 for h in train_sha.keys() & val_sha.keys()]
        hashes_train = [(dhash(p), p) for p in train]
        hashes_val = [(dhash(p), p) for p in validation]
        near = []
        for vh, vp in hashes_val:
            distance, tp = min((bin(vh ^ th).count('1'), path) for th, path in hashes_train)
            if distance <= 5:
                near.append({'validation': str(vp), 'nearest_train': str(tp),
                             'hamming_distance_64bit_dhash': distance,
                             'warning': 'visual similarity candidate, not proven duplicate'})
        unfit_present = []
        for item in manifest:
            if item['split'] == 'train' and item['annotation']['annotation_quality'] in ('ambiguous', 'unusable'):
                image = data / 'images/train' / (item['observation_id'] + '.jpg')
                if image.exists():
                    unfit_present.append(item['observation_id'])
        result['sensors'][sensor] = {'train_image_count': len(train),
                                     'validation_image_count': len(validation),
                                     'exact_sha256_duplicate_count': len(exact),
                                     'exact_duplicates': exact,
                                     'near_dhash_candidate_count': len(near),
                                     'near_dhash_candidates': near,
                                     'ambiguous_or_unusable_train_images_present': unfit_present}
    result['interpretation'] = ('Zero session/ID/exact-hash overlap supports partition separation, '
                                'but perceptual similarity must be manually reviewed. Original source_split '
                                'labels reflect earlier dataset versions and do not define current membership.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'session_overlap': len(result['train_validation_session_overlap']),
                      'train_blind_overlap': len(result['train_blind_session_overlap']),
                      'sensors': {k: {'exact': v['exact_sha256_duplicate_count'],
                                      'near': v['near_dhash_candidate_count'],
                                      'unfit': len(v['ambiguous_or_unusable_train_images_present'])}
                                  for k, v in result['sensors'].items()}}))


if __name__ == '__main__':
    main()
