import argparse, hashlib, json
from pathlib import Path
from ultralytics import YOLO

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_boxes(path):
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            _, x, y, w, h = map(float, line.split())
            out.append((x-w/2, y-h/2, x+w/2, y+h/2))
    return out

def iou(a, b):
    x = max(0, min(a[2], b[2])-max(a[0], b[0]))
    y = max(0, min(a[3], b[3])-max(a[1], b[1]))
    z = x*y
    aa = (a[2]-a[0])*(a[3]-a[1]); bb = (b[2]-b[0])*(b[3]-b[1])
    return z/(aa+bb-z) if aa+bb-z else 0

ap = argparse.ArgumentParser()
ap.add_argument('--weights', required=True); ap.add_argument('--images', required=True)
ap.add_argument('--labels', required=True); ap.add_argument('--output', required=True)
ap.add_argument('--imgsz', type=int, default=1280); ap.add_argument('--device', default='1')
ap.add_argument('--model_id', required=True)
a = ap.parse_args()
model = YOLO(a.weights); rows = []
for image in sorted(Path(a.images).glob('*.jpg')):
    truth = load_boxes(Path(a.labels)/(image.stem+'.txt'))
    result = model.predict(str(image), imgsz=a.imgsz, conf=0.001, iou=0.7, device=a.device, verbose=False)[0]
    height, width = result.orig_shape
    pred = [([c[0]/width, c[1]/height, c[2]/width, c[3]/height], float(conf))
            for c, conf in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist())]
    used = set(); tp = fp = 0
    for box, conf in sorted(pred, key=lambda x: x[1], reverse=True):
        candidates = [(iou(box, target), index) for index, target in enumerate(truth) if index not in used]
        best = max(candidates, default=(0, -1))
        if best[0] >= 0.5:
            tp += 1; used.add(best[1])
        else:
            fp += 1
    rows.append({'image': image.stem, 'gt': len(truth), 'pred': len(pred), 'tp': tp, 'fp': fp, 'fn': len(truth)-tp})
tp = sum(x['tp'] for x in rows); fp = sum(x['fp'] for x in rows); fn = sum(x['fn'] for x in rows)
report = {'model_id': a.model_id, 'weights': a.weights, 'weights_sha256': sha(a.weights), 'images': len(rows),
          'tp': tp, 'fp': fp, 'fn': fn, 'precision': tp/(tp+fp) if tp+fp else 0,
          'recall': tp/(tp+fn) if tp+fn else 0, 'rows': rows}
Path(a.output).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False))
