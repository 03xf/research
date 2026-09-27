import hashlib
import json
import shutil
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--round', type=int, default=3)
p.add_argument('--weights', type=Path)
p.add_argument('--model-id')
a = p.parse_args()
base = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1')
old = base / 'b2_auto_round2'
new = base / f'b2_auto_round{a.round}'
(new / 'replay_root').mkdir(parents=True, exist_ok=True)
(new / 'localization_v2').mkdir(parents=True, exist_ok=True)
src = old / 'replay_root/model_freeze_preconfirmation_v1.json'
cfg = json.loads(src.read_text())
v = a.weights or new / 'runs/B2R3_V_E2_curated_1280/weights/best.pt'
cfg['models']['V'].update(model_id=a.model_id or 'B2R3_V_E2_curated_1280', weights=str(v),
                          weights_sha256=hashlib.sha256(v.read_bytes()).hexdigest(),
                          class_index=0, imgsz=1280, development_passed=False)
cfg['models']['V']['note'] = 'Curated flame labels; fixed-video holdout only inspected after training.'
cfg['models']['T']['note'] = 'R2 T remains diagnostic; its validation split had prior holdout exposure.'
(new / 'replay_root/model_freeze_preconfirmation_v1.json').write_text(json.dumps(cfg, indent=2) + '\n')
shutil.copy2(old / 'localization_v2/fire_coordinate_inventory_v3.csv',
             new / 'localization_v2/fire_coordinate_inventory_v3.csv')
print(v)
