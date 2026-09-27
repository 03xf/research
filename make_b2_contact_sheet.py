from pathlib import Path
import json, cv2, math, numpy as np

root = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7')
out = root / 'recovery_v1/b2_review_v2'
out.mkdir(parents=True, exist_ok=True)
obs = [o for o in json.loads((root/'manifest_round12.json').read_text())['observations'] if o.get('batch_id') == 'B2']
for sensor in 'VT':
    tiles = []
    for o in sorted(obs, key=lambda x: (x['video_group'], x['timestamp_s'])):
        p = root / f"annotation_frames_round7/B2/{o['observation_id']}_{sensor}.jpg"
        im = cv2.imread(str(p))
        if im is None: continue
        h, w = im.shape[:2]
        im = cv2.resize(im, (300, round(h * 300 / w)))
        labels = o['annotation']['visible_labels'] if sensor == 'V' else o['annotation']['thermal_labels']
        for label in labels:
            if label['class'] not in (['flame'] if sensor == 'V' else ['hotspot']): continue
            x1, y1, x2, y2 = map(float, label['bbox_xyxy'])
            sx, sy = im.shape[1]/w, im.shape[0]/h
            cv2.rectangle(im, (round(x1*sx), round(y1*sy)), (round(x2*sx), round(y2*sy)), (0,255,0), 2)
        title = f"{o['observation_id']} g={o['video_group'][-4:]} t={o['timestamp_s']:.0f} {o['annotation']['annotation_quality']} {len(labels)}"
        cv2.rectangle(im, (0,0), (im.shape[1],28), (0,0,0), -1)
        cv2.putText(im, title, (4,20), cv2.FONT_HERSHEY_SIMPLEX, .38, (255,255,255), 1)
        tiles.append(im)
    cols = 4
    th = max(x.shape[0] for x in tiles)
    rows = math.ceil(len(tiles)/cols)
    sheet = np.full((rows*th, cols*300, 3), 255, np.uint8)
    for i, im in enumerate(tiles):
        sheet[(i//cols)*th:(i//cols)*th+im.shape[0], (i%cols)*300:(i%cols)*300+300] = im
    cv2.imwrite(str(out/f'B2_{sensor}_contact.jpg'), sheet)
