#!/bin/sh
set -eu
R=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
/home/member/bin/python /home/member/xmy/xmy/code/tools/recovery_v1_train.py \
  --weights /home/member/xmy/xmy/weights/pretrained/ultralytics/yolov8n.pt \
  --data "$R/detection_quality_v2/datasets/C4/V/data.yaml" \
  --project "$R/detection_quality_v2/runs" \
  --name C4_V_flame_960_s0 \
  --epochs 100 --imgsz 960 --batch 8 --device 0 --workers 2 --seed 0 --purpose controlled
