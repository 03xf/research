"""Suggest flame extents using warm-color pixels inside reviewed fire-site ROIs."""
import json
from pathlib import Path

import cv2
import numpy as np

from build_b2_curated_v3 import POSITIVE

image_root = Path('D:/课题/b2_reports/review_images')
out_root = Path('D:/课题/b2_reports/flame_proposals')
out_root.mkdir(parents=True, exist_ok=True)
manifest = {}
tiles = []
for oid, (x1, y1, x2, y2) in POSITIVE.items():
    image_path = image_root / (oid + '.jpg')
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR) if image_path.exists() else None
    if image is None:
        continue
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Strong red/orange/yellow is a proposal cue; visual review is mandatory.
    warm = cv2.inRange(hsv, (0, 115, 100), (29, 255, 255))
    roi = np.zeros(warm.shape, np.uint8)
    roi[y1:y2, x1:x2] = 255
    warm = cv2.bitwise_and(warm, roi)
    warm = cv2.morphologyEx(warm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(warm, 8)
    candidates = []
    for j in range(1, count):
        xx, yy, ww, hh, area = map(int, stats[j])
        if area < 55 or ww < 9 or hh < 10:
            continue
        candidates.append([max(x1, xx-5), max(y1, yy-5), min(x2, xx+ww+5), min(y2, yy+hh+5), area])
    candidates.sort(key=lambda r: r[-1], reverse=True)
    manifest[oid] = candidates[:20]
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 3)
    for box in candidates[:12]:
        ax, ay, bx, by, area = box
        cv2.rectangle(overlay, (ax, ay), (bx, by), (0, 0, 255), 3)
        cv2.putText(overlay, str(area), (ax, max(15, ay-5)), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 255), 1)
    # Crop around the broader fire site for legible review.
    cx1, cy1, cx2, cy2 = max(0, x1-100), max(0, y1-100), min(image.shape[1], x2+100), min(image.shape[0], y2+100)
    crop = overlay[cy1:cy2, cx1:cx2]
    scale = min(800/crop.shape[1], 520/crop.shape[0])
    crop = cv2.resize(crop, None, fx=scale, fy=scale)
    tile = np.full((570, 840, 3), 255, np.uint8)
    tile[40:40+crop.shape[0], 20:20+crop.shape[1]] = crop
    cv2.putText(tile, oid, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 0, 0), 2)
    tiles.append(tile)
for page in range(0, len(tiles), 4):
    group = tiles[page:page+4]
    while len(group) < 4:
        group.append(np.full((570, 840, 3), 255, np.uint8))
    sheet = np.concatenate([np.concatenate(group[i:i+2], axis=1)
                            for i in (0, 2)], axis=0)
    cv2.imencode('.jpg', sheet)[1].tofile(out_root / f'proposals_{page//4+1:02d}.jpg')
(out_root / 'proposals.json').write_text(json.dumps(manifest, indent=2))
