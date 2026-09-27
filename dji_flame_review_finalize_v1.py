"""Freeze all 40 flame decisions, record differences, and build C2/C3 datasets."""
import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dji_flame_recall_dataset_v1 import build, digest, reviewed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    work = root / 'flame_recall_v1'
    queue = work / 'review_queue_v1'
    if (work / 'review_frozen_v1.json').exists():
        raise FileExistsError('review is already frozen; preserve its original version')
    items = json.loads((queue / 'queue.json').read_text(encoding='utf-8'))['items']
    mapped, decision_hash = reviewed(queue, require_all=True)
    if set(mapped) != {item['key'] for item in items} or len(items) != 40:
        raise ValueError('review keys incomplete or unexpected')
    rows = []
    for item in items:
        decision_item, final_text = mapped[item['key']]
        original = Path(item['image']).with_name(item['observation_id'] + '.jpg')
        if digest(original) != item['image_sha256']:
            raise ValueError('review image changed')
        old_text = (queue / 'labels' / (item['observation_id'] + '.txt')).read_text(encoding='utf-8')
        old_lines = [line for line in old_text.splitlines() if line.strip()]
        new_lines = [line for line in final_text.splitlines() if line.strip()]
        rows.append({'key': item['key'], 'kind': item['kind'],
                     'observation_id': item['observation_id'],
                     'timestamp_s': item['timestamp_s'],
                     'old_flame_boxes': len(old_lines), 'new_flame_boxes': len(new_lines),
                     'label_changed': old_text.strip() != final_text.strip(),
                     'source_image_sha256': item['image_sha256']})
    changed_existing = sum(row['label_changed'] for row in rows if row['kind'] == 'existing')
    output = work / 'review_frozen_v1.json'
    frozen_queue = work / 'review_queue_frozen_v1'
    if frozen_queue.exists():
        raise FileExistsError(frozen_queue)
    frozen_queue.mkdir()
    shutil.copyfile(queue / 'queue.json', frozen_queue / 'queue.json')
    shutil.copyfile(queue / 'review_decisions.json', frozen_queue / 'review_decisions.json')
    payload = {'schema_version': 'b4_flame_review_frozen_v1',
               'created_utc': datetime.now(timezone.utc).isoformat(),
               'review_decisions_sha256': decision_hash,
               'review_queue_sha256': digest(queue / 'queue.json'),
               'frozen_queue_path': str(frozen_queue),
               'existing_count': 17, 'existing_changed_count': changed_existing,
               'new_count': 23,
               'new_positive_count': sum(row['new_flame_boxes'] > 0 for row in rows if row['kind'] == 'new'),
               'rows': rows}
    (work / 'label_diff_v1.csv').write_text('', encoding='utf-8')
    with (work / 'label_diff_v1.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if changed_existing:
        build(root, 'C2', work / 'datasets' / 'C2', frozen_queue)
    build(root, 'C3', work / 'datasets' / 'C3', frozen_queue)
    payload['C2_status'] = 'built' if changed_existing else 'skipped_no_existing_label_change'
    payload['C3_dataset_manifest_sha256'] = digest(work / 'datasets' / 'C3' / 'manifest.json')
    if changed_existing:
        payload['C2_dataset_manifest_sha256'] = digest(work / 'datasets' / 'C2' / 'manifest.json')
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('existing_changed_count', 'new_positive_count', 'C2_status', 'C3_dataset_manifest_sha256')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
