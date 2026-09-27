"""Create a B4-only, flame-only 40-image manual review queue."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from dji_flame_recall_dataset_v1 import remap


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def image_hash(path):
    with Image.open(path) as source:
        image = source.convert('L').resize((17, 16))
        values = list(image.getdata())
    return sum((values[y * 17 + x] > values[y * 17 + x + 1]) << (y * 16 + x)
               for y in range(16) for x in range(16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--grid', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    ledger = json.loads((args.root / 'sample_ledger.json').read_text(encoding='utf-8'))['records']
    training = [r for r in ledger if r.get('batch_id') == 'B4' and r.get('sensor') == 'V'
                and r.get('split') == 'train']
    existing = [r for r in training if r.get('class_counts', {}).get('flame', 0)]
    if len(existing) != 17:
        raise ValueError(f'expected 17 B4 flame training images, got {len(existing)}')
    videos = {r['source_video']['visible'] for r in training
              if r['session_id'] == 'DJI_202609081040_006'}
    if len(videos) != 1:
        raise ValueError('training source video is ambiguous')
    video = next(iter(videos))
    same_video = [r for r in ledger if r.get('sensor') == 'V'
                  and r.get('source_video', {}).get('visible') == video]
    if any(r['split'] != 'train' for r in same_video):
        raise ValueError('training video crosses data split')
    grid = json.loads((args.grid / 'candidates.json').read_text(encoding='utf-8'))
    old_times = [float(r['timestamp_s']) for r in same_video]
    selected = []
    for target in [390 + 6 * i for i in range(23)]:
        options = [c for c in grid
                   if c not in selected
                   and min(abs(c['pts_s'] - t) for t in old_times) >= 1.5
                   and all(abs(c['pts_s'] - s['pts_s']) >= 3.5 for s in selected)]
        if not options:
            raise ValueError(f'cannot source distinct candidate near {target}')
        selected.append(min(options, key=lambda c: (abs(c['pts_s'] - target), c['pts_s'])))
    selected.sort(key=lambda c: c['pts_s'])
    if len(selected) != 23:
        raise ValueError('wrong new frame count')
    args.output.mkdir(parents=True)
    images = args.output / 'images'
    labels = args.output / 'labels'
    images.mkdir()
    labels.mkdir()
    records, items = [], []
    c1 = args.root / 'flame_recall_v1' / 'datasets' / 'C1'
    for row in sorted(existing, key=lambda r: r['observation_id']):
        name = row['observation_id']
        source_image = c1 / 'V' / 'images' / 'train' / (name + '.jpg')
        source_label = c1 / 'V' / 'labels' / 'train' / (name + '.txt')
        if digest(source_image) != row['image_sha256']:
            raise ValueError('source image hash mismatch: ' + name)
        label_text = source_label.read_text(encoding='utf-8')
        if not label_text:
            raise ValueError('existing flame image remapped to empty: ' + name)
        shutil.copyfile(source_image, images / (name + '.jpg'))
        (labels / (name + '.txt')).write_text(label_text, encoding='utf-8')
        image, label = images / (name + '.jpg'), labels / (name + '.txt')
        record = {**row, 'image': str(image), 'label': str(label),
                  'image_sha256': digest(image), 'label_sha256': digest(label),
                  'class_counts': {'flame': len(label_text.splitlines())},
                  'review_status': '待复核火焰框', 'proposed_patch': None}
        records.append(record)
        items.append({'key': f'V:train:{name}', 'kind': 'existing',
                      'observation_id': name, 'image': str(image),
                      'image_sha256': record['image_sha256'], 'label_sha256': record['label_sha256'],
                      'timestamp_s': row['timestamp_s'], 'source_video': video})
    image_hashes = {r['image_sha256'] for r in ledger}
    old_perceptual = [(image_hash(Path(r['image'])), r['observation_id'])
                      for r in same_video if Path(r['image']).is_file()]
    perceptual_audit = []
    for i, candidate in enumerate(selected, 1):
        name = f'zflame_new_{i:02d}'
        original = Path(candidate['image'])
        image = images / (name + '.jpg')
        label = labels / (name + '.txt')
        shutil.copyfile(original, image)
        label.write_text('', encoding='utf-8')
        sha = digest(image)
        if sha in image_hashes:
            raise ValueError('new frame exactly duplicates existing data: ' + name)
        image_hashes.add(sha)
        ph = image_hash(image)
        minimum, closest = min((bin(ph ^ h).count('1'), key) for h, key in old_perceptual)
        perceptual_audit.append({'observation_id': name, 'nearest_existing_id': closest,
                                 'dhash_256_distance': minimum})
        with Image.open(image) as picture:
            size = list(picture.size)
        record = {'observation_id': name, 'sensor': 'V', 'split': 'train', 'batch_id': 'B4',
                  'session_id': 'DJI_202609081040_006',
                  'video_group': 'DJI_20260908105306_0001',
                  'source_video': {'visible': video}, 'timestamp_s': candidate['pts_s'],
                  'image': str(image), 'image_sha256': sha, 'image_size': size,
                  'label': str(label), 'label_sha256': digest(label),
                  'class_counts': {}, 'review_status': '待复核火焰框',
                  'proposed_patch': None}
        records.append(record)
        items.append({'key': f'V:train:{name}', 'kind': 'new', 'observation_id': name,
                      'image': str(image), 'image_sha256': sha, 'label_sha256': digest(label),
                      'timestamp_s': candidate['pts_s'], 'source_video': video})
    (args.output / 'sample_ledger.json').write_text(json.dumps({'records': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / 'queue.json').write_text(json.dumps({'schema_version': 'b4_flame_review_queue_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'existing_count': 17,
        'new_count': 23, 'items': items, 'perceptual_audit': perceptual_audit,
        'image_selection': 'B4 training-only V video; decoded PTS; >=1.5s from existing indexed frame and >=3.5s apart'},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / 'review_decisions.json').write_text('{"decisions": []}\n', encoding='utf-8')
    (args.output / 'review_history.jsonl').touch()
    print(json.dumps({'queue': str(args.output), 'count': len(items),
                      'new_pts': [round(x['pts_s'], 3) for x in selected],
                      'perceptual_min_distance': min(x['dhash_256_distance'] for x in perceptual_audit)}))


if __name__ == '__main__':
    main()
