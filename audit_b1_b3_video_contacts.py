"""Make midpoint contact sheets for visual triage, without changing source media."""

import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1/b1_b3_capacity_audit_20260926')


def frame(row):
    path = ROOT / 'mid_frames' / f"{row['batch']}_{row['category']}_{row['drone'].split('_')[0]}_{row['recording']}_{row['channel']}.jpg"
    path.parent.mkdir(exist_ok=True)
    duration = row.get('duration_s') or 0
    seek = max(0, min(duration * 0.5, max(duration - 0.15, 0)))
    p = subprocess.run([
        'ffmpeg', '-y', '-v', 'error', '-ss', f'{seek:.3f}', '-i', row['path'],
        '-frames:v', '1', '-q:v', '4', str(path),
    ], capture_output=True, timeout=40)
    return str(path) if p.returncode == 0 and path.is_file() else None


def main():
    rows = json.loads((ROOT / 'video_inventory.json').read_text(encoding='utf-8'))
    rows = [r for r in rows if r['batch'] in ('B1', 'B2', 'B3') and r['channel'] in ('V', 'T')]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(frame, r): r for r in rows}
        for future in as_completed(futures):
            futures[future]['mid_frame'] = future.result()
    (ROOT / 'midpoint_review.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    groups = defaultdict(list)
    for row in rows:
        groups[(row['batch'], row['channel'])].append(row)
    for (batch, channel), group in sorted(groups.items()):
        group.sort(key=lambda r: (r['category'], r['drone'], r['recording']))
        cols, cell_w, image_h, label_h = 4, 400, 260 if channel == 'T' else 230, 38
        cell_h = image_h + label_h
        canvas = Image.new('RGB', (cols * cell_w, ((len(group) + cols - 1) // cols) * cell_h), 'white')
        draw = ImageDraw.Draw(canvas)
        for idx, row in enumerate(group):
            x, y = (idx % cols) * cell_w, (idx // cols) * cell_h
            drone = row['drone'].split('_')[0].replace('无人机', 'D')
            desc = f"{row['category']} {drone} {row['recording']} {row.get('duration_s',0):.0f}s"
            draw.text((x + 4, y + 3), desc, fill='black')
            if row.get('mid_frame'):
                with Image.open(row['mid_frame']) as src:
                    picture = ImageOps.contain(src.convert('RGB'), (cell_w - 2, image_h - 2))
                    canvas.paste(picture, (x + (cell_w - picture.width) // 2, y + label_h + (image_h - picture.height) // 2))
            else:
                draw.text((x + 5, y + label_h + 20), 'DECODE FAILED', fill='red')
        canvas.save(ROOT / f'{batch}_{channel}_midpoint_contact.jpg', quality=88)
    print('decoded', sum(bool(r.get('mid_frame')) for r in rows), '/', len(rows))


if __name__ == '__main__':
    main()
