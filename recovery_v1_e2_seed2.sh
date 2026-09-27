#!/usr/bin/env bash
set -euo pipefail
root=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
entry=/home/member/xmy/xmy/code/tools/recovery_v1_train.py
base=/home/member/xmy/xmy/weights/pretrained/ultralytics/yolov8n.pt
python=/home/member/bin/python
for sensor in T V; do
  "$python" "$entry" \
    --weights "$base" \
    --data "$root/dataset_review_applied_v1/$sensor/data.yaml" \
    --project "$root/runs" \
    --name "E2_${sensor}_960_s2" \
    --epochs 100 --imgsz 960 --batch 8 --device 0 --workers 2 \
    --seed 2 --purpose controlled \
    > "$root/E2_${sensor}_960_s2.log" 2>&1
done
