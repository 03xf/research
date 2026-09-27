import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate-manifest', type=Path, required=True)
    ap.add_argument('--adjudication', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()

    src = json.loads(args.candidate_manifest.read_text(encoding='utf-8'))
    review = json.loads(args.adjudication.read_text(encoding='utf-8'))
    rows = {r['observation_id']: r for r in src['entries']}
    approved = review['approved']
    if len(approved) != 9 or set(approved) != {
        'obs_000706', 'obs_000730', 'obs_000738', 'obs_000746',
        'obs_000754', 'obs_000762', 'obs_000770', 'obs_000778', 'obs_000794'
    }:
        raise ValueError('unexpected approved set')
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)
    patches = []
    for obs_id in approved:
        row = rows[obs_id]
        image = Path(row['source_image'])
        label = Path(row['source_label'])
        if sha256(image) != row['source_image_sha256']:
            raise ValueError('source image hash changed: ' + obs_id)
        if sha256(label) != row['source_label_sha256'] or label.read_text().strip():
            raise ValueError('source label changed/non-empty: ' + obs_id)
        x1, y1, x2, y2 = row['bbox_xyxy']
        width, height = 1280.0, 1024.0
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError('invalid bbox: ' + obs_id)
        yolo = [(x1 + x2) / 2 / width, (y1 + y2) / 2 / height,
                (x2 - x1) / width, (y2 - y1) / height]
        patch = args.output_dir / (obs_id + '.txt')
        patch.write_text('0 ' + ' '.join(f'{v:.8f}' for v in yolo) + '\n', encoding='utf-8')
        patches.append({
            'observation_id': obs_id,
            'bbox_xyxy': [x1, y1, x2, y2],
            'yolo': [round(v, 8) for v in yolo],
            'interpretation': review['decisions'][obs_id]['interpretation'],
            'tv_relation': review['decisions'][obs_id]['tv_relation'],
            'source_image': str(image),
            'source_image_sha256': row['source_image_sha256'],
            'source_label': str(label),
            'source_label_sha256': row['source_label_sha256'],
            'patch_label': str(patch),
            'patch_label_sha256': sha256(patch),
        })
    provenance = {
        'schema_version': 'dji_round46_thermal_adjudication_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_candidate_manifest': str(args.candidate_manifest),
        'source_candidate_manifest_sha256': sha256(args.candidate_manifest),
        'adjudication': str(args.adjudication),
        'adjudication_sha256': sha256(args.adjudication),
        'approved_count': len(patches),
        'deferred': review['deferred'],
        'source_validation_dataset_modified': False,
        'training_authorized': False,
        'evaluation_authorized': False,
        'blind_test_accessed': False,
        'patches': patches,
    }
    (args.output_dir / 'provenance.json').write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'patch_count': len(patches), 'provenance': str(args.output_dir / 'provenance.json')}))


if __name__ == '__main__':
    main()
