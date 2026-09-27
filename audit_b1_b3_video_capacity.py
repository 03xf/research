"""Read-only inventory of DJI video streams for B1-B3 capacity planning."""

import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path('/home/member/xmy/data/苏州放火_实验数据集')
MANIFEST = ROOT / '00_数据说明与清单' / 'dataset_manifest.csv'
OUT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1/b1_b3_capacity_audit_20260926')


def probe(path):
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'format=duration:stream=width,height,avg_frame_rate,nb_frames',
        '-of', 'json', str(path),
    ]
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=45)
        if p.returncode:
            return {'probe_error': p.stderr.strip()[-500:] or f'exit {p.returncode}'}
        obj = json.loads(p.stdout)
        fmt, stream = obj.get('format', {}), next(iter(obj.get('streams', [])), {})
        return {
            'duration_s': float(fmt['duration']) if fmt.get('duration') else None,
            'width': stream.get('width'),
            'height': stream.get('height'),
            'avg_frame_rate': stream.get('avg_frame_rate'),
            'nb_frames': stream.get('nb_frames'),
        }
    except Exception as exc:
        return {'probe_error': str(exc)}


def main():
    short_batch = {}
    with MANIFEST.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if row['category'] != 'short_or_supplement':
                continue
            match = re.search(r'=(0[1-4])$', row['notes'])
            if match:
                key = (row['drone_serial'], row['session'], row['recording_prefix'], row['channel'])
                short_batch[key] = f'B{int(match.group(1))}'

    jobs = []
    for path in ROOT.rglob('*.MP4'):
        match = re.search(r'_([VTS])\.MP4$', path.name, re.I)
        if not match:
            continue
        channel = match.group(1).upper()
        parts = path.relative_to(ROOT).parts
        category = 'supplement' if parts[0].startswith('90_') else 'formal' if len(parts) > 1 and parts[1].startswith('01_') else 'point_or_other'
        drone = next((p for p in parts if p.startswith('无人机')), '')
        serial = drone.split('_', 1)[-1]
        session = path.parent.name
        recording = path.stem[:-2]
        if category == 'formal':
            batch = f'B{int(parts[0][:2])}'
        elif category == 'supplement':
            batch = short_batch.get((serial, session, recording, channel), 'unmapped')
        else:
            batch = 'point_or_other'
        jobs.append({
            'batch': batch, 'category': category, 'channel': channel,
            'drone': drone, 'session': session, 'recording': recording,
            'bytes': path.stat().st_size, 'path': str(path),
        })

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(probe, Path(row['path'])): row for row in jobs if row['channel'] in ('V', 'T')}
        for future in as_completed(futures):
            futures[future].update(future.result())

    rows = sorted(jobs, key=lambda r: (r['batch'], r['category'], r['drone'], r['session'], r['recording'], r['channel']))
    counts = Counter((r['batch'], r['category'], r['channel']) for r in rows)
    durations = defaultdict(float)
    for r in rows:
        if r.get('duration_s') is not None:
            durations[(r['batch'], r['category'], r['channel'])] += r['duration_s']
    summary = {
        'source_root': str(ROOT),
        'video_stream_count': len(rows),
        'stream_counts': [{'batch': b, 'category': c, 'channel': ch, 'count': n, 'duration_h': round(durations[(b, c, ch)] / 3600, 3)} for (b, c, ch), n in sorted(counts.items())],
        'probe_errors': [{'path': r['path'], 'error': r['probe_error']} for r in rows if 'probe_error' in r],
        'unmapped_supplements': [r['path'] for r in rows if r['batch'] == 'unmapped'],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'video_inventory.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
