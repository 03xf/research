"""Inspect candidate V frames from the B4 training-only source video."""
import argparse
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

PATTERN = re.compile(r"\bn:\s*(\d+).*?\bpts_time:\s*([-+0-9.eE]+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--start', type=float, default=390)
    ap.add_argument('--duration', type=float, default=135)
    ap.add_argument('--interval', type=float, default=2)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    ledger = json.loads((args.root / 'sample_ledger.json').read_text(encoding='utf-8'))['records']
    rows = [r for r in ledger if r.get('sensor') == 'V' and r.get('split') == 'train'
            and r.get('session_id') == 'DJI_202609081040_006']
    videos = {r['source_video']['visible'] for r in rows}
    if len(videos) != 1:
        raise ValueError('B4 training video ambiguous')
    video = Path(next(iter(videos)))
    args.output.mkdir(parents=True)
    frames = args.output / 'frames'
    frames.mkdir()
    cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'info', '-copyts',
           '-ss', str(args.start), '-i', str(video), '-t', str(args.start + args.duration),
           '-vf', f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{args.interval})',showinfo",
           '-vsync', '0', '-q:v', '4', str(frames / '%06d.jpg')]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding='utf-8', errors='replace')
    (args.output / 'ffmpeg.log').write_text(proc.stderr, encoding='utf-8')
    if proc.returncode:
        raise RuntimeError('ffmpeg failed; see log')
    pts = [float(m.group(2)) for line in proc.stderr.splitlines()
           if 'showinfo' in line and (m := PATTERN.search(line))]
    images = sorted(frames.glob('*.jpg'))
    if len(pts) == len(images) + 1 and pts[-1] >= args.start + args.duration - 0.2:
        pts.pop()
    if len(images) != len(pts):
        raise ValueError(f'PTS/image mismatch: {len(pts)} / {len(images)}')
    items = [{'image': str(image), 'pts_s': stamp} for image, stamp in zip(images, pts)]
    (args.output / 'candidates.json').write_text(json.dumps(items, indent=2) + '\n')
    tile_w, tile_h, cols = 320, 205, 5
    import math
    sheet = Image.new('RGB', (tile_w * cols, tile_h * math.ceil(len(items) / cols)), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, item in enumerate(items):
        with Image.open(item['image']) as source:
            small = source.convert('RGB')
            small.thumbnail((tile_w, tile_h - 25))
        x, y = i % cols * tile_w, i // cols * tile_h
        sheet.paste(small, (x, y))
        draw.text((x + 5, y + tile_h - 23), f"{i + 1:02d}  {item['pts_s']:.2f}s", fill='black')
    sheet.save(args.output / 'contact_sheet.jpg', quality=90)
    print(json.dumps({'count': len(items), 'first_pts': pts[0], 'last_pts': pts[-1],
                      'contact_sheet': str(args.output / 'contact_sheet.jpg')}))


if __name__ == '__main__':
    main()
