"""Build immutable single-class V flame datasets C1/C2/C3 for recovery_v1."""
import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from recovery_v1_prepare import check_label


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def remap(text):
    lines = []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == '1':
            lines.append('0 ' + ' '.join(fields[1:]))
        elif fields[0] != '0':
            raise ValueError('unexpected source V class: ' + line)
    result = '\n'.join(lines) + ('\n' if lines else '')
    check_label(result, 1)
    return result


def reviewed(queue, require_all):
    if not queue:
        return {}, None
    source = json.loads((queue / 'queue.json').read_text(encoding='utf-8'))['items']
    values = json.loads((queue / 'review_decisions.json').read_text(encoding='utf-8'))['decisions']
    decisions = {row['key']: row for row in values}
    if require_all and len(decisions) != len(source):
        raise ValueError(f'review incomplete: {len(decisions)}/{len(source)}')
    mapped = {}
    for item in source:
        decision = decisions.get(item['key'])
        if not decision:
            continue
        if decision['source_image_sha256'] != item['image_sha256']:
            raise ValueError('review image hash mismatch: ' + item['key'])
        text = decision['label_text'].strip()
        check_label(text, 1)
        if decision['status'] != ('approved_complete' if text else 'confirmed_negative'):
            raise ValueError('review status disagrees with label: ' + item['key'])
        mapped[item['key']] = (item, text + ('\n' if text else ''))
    return mapped, digest(queue / 'review_decisions.json')


def build(root, mode, output, queue):
    if output.exists():
        raise FileExistsError(output)
    source = root / 'dataset_review_applied_v1'
    if not source.is_dir():
        raise FileNotFoundError(source)
    source_manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if Path(source_manifest['derived_dataset']).resolve() != source.resolve():
        raise ValueError('source dataset provenance mismatch')
    decisions, decision_hash = reviewed(queue, require_all=mode in ('C2', 'C3')) if mode != 'C1' else ({}, None)
    if mode in ('C2', 'C3') and not queue:
        raise ValueError('C2/C3 require reviewed queue')
    existing = {item['observation_id']: (item, label) for item, label in decisions.values()
                if item['kind'] == 'existing'}
    added = [(item, label) for item, label in decisions.values() if item['kind'] == 'new']
    if mode in ('C2', 'C3') and len(existing) != 17:
        raise ValueError('expected 17 existing reviewed B4 flame images')
    if mode == 'C3' and len(added) != 23:
        raise ValueError('expected 23 new reviewed frames')
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix=mode + '.building.', dir=output.parent) as temp:
        temp_path = Path(temp)
        for split in ('train', 'validation'):
            image_source = source / 'V' / 'images' / split
            label_source = source / 'V' / 'labels' / split
            image_dest = temp_path / 'V' / 'images' / split
            label_dest = temp_path / 'V' / 'labels' / split
            image_dest.mkdir(parents=True)
            label_dest.mkdir(parents=True)
            for image in sorted(image_source.glob('*.jpg')):
                label = label_source / (image.stem + '.txt')
                if not label.is_file():
                    raise FileNotFoundError(label)
                new_text = remap(label.read_text(encoding='utf-8'))
                if split == 'train' and image.stem in existing and mode in ('C2', 'C3'):
                    item, new_text = existing[image.stem]
                    if digest(image) != item['image_sha256']:
                        raise ValueError('existing review image changed: ' + image.stem)
                shutil.copyfile(image, image_dest / image.name)
                (label_dest / label.name).write_text(new_text, encoding='utf-8')
                records.append({'split': split, 'image': image.name,
                                'source_image_sha256': digest(image),
                                'source_label_sha256': digest(label),
                                'new_label_sha256': digest(label_dest / label.name),
                                'review_override': split == 'train' and image.stem in existing and mode in ('C2', 'C3')})
        if mode == 'C3':
            for item, new_text in added:
                image = Path(item['image'])
                if digest(image) != item['image_sha256']:
                    raise ValueError('new review image changed: ' + item['key'])
                name = item['observation_id'] + '.jpg'
                dest_image = temp_path / 'V' / 'images' / 'train' / name
                dest_label = temp_path / 'V' / 'labels' / 'train' / (item['observation_id'] + '.txt')
                if dest_image.exists():
                    raise ValueError('new image ID collides with existing: ' + name)
                shutil.copyfile(image, dest_image)
                dest_label.write_text(new_text, encoding='utf-8')
                records.append({'split': 'train', 'image': name,
                                'source_image_sha256': item['image_sha256'],
                                'source_label_sha256': item['label_sha256'],
                                'new_label_sha256': digest(dest_label), 'review_override': True,
                                'new_frame': True, 'source_pts_s': item['timestamp_s']})
        hashes = {'train': set(), 'validation': set()}
        for record in records:
            value = record['source_image_sha256']
            if value in hashes[record['split']]:
                raise ValueError('exact duplicate in ' + record['split'])
            hashes[record['split']].add(value)
        if hashes['train'] & hashes['validation']:
            raise ValueError('train/validation exact duplicate')
        (temp_path / 'review_decisions_snapshot.json').write_bytes((source / 'review_decisions_snapshot.json').read_bytes())
        yaml = ('path: ' + str(output / 'V') + '\ntrain: images/train\nval: images/validation\n'
                'names:\n  0: flame\nnc: 1\n')
        (temp_path / 'V' / 'data.yaml').write_text(yaml, encoding='utf-8')
        manifest = {'schema_version': 'dji_flame_recall_dataset_v1',
                    'created_utc': datetime.now(timezone.utc).isoformat(),
                    'mode': mode, 'derived_dataset': str(output.resolve()),
                    'source_dataset': str(source.resolve()),
                    'source_dataset_manifest_sha256': digest(source / 'manifest.json'),
                    'review_decisions_sha256': digest(temp_path / 'review_decisions_snapshot.json'),
                    'flame_review_decisions_sha256': decision_hash,
                    'legacy_positive_unreviewed': source_manifest['legacy_positive_unreviewed'],
                    'class_mapping': {'source': {'0': 'smoke', '1': 'flame'}, 'derived': {'0': 'flame'}},
                    'counts': {split: sum(r['split'] == split for r in records) for split in ('train', 'validation')},
                    'reviewed_existing_count': len(existing) if mode in ('C2', 'C3') else 0,
                    'new_frame_count': len(added) if mode == 'C3' else 0,
                    'records': records,
                    'development_historically_exposed': True,
                    'confirmation_training_excluded': True}
        (temp_path / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp_path.rename(output)
    print(json.dumps({'dataset': str(output), 'mode': mode, 'counts': manifest['counts'],
                      'manifest_sha256': digest(output / 'manifest.json')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mode', choices=('C1', 'C2', 'C3'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--queue', type=Path)
    args = parser.parse_args()
    build(args.root, args.mode, args.output, args.queue)
