#!/bin/sh
set -eu
R=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
/home/member/bin/python /home/member/xmy/xmy/code/tools/recovery_v1_evaluate.py \
  --weights "$R/detection_quality_v2/runs/C4_V_flame_960_s0/weights/best.pt" \
  --data "$R/detection_quality_v2/datasets/C4/V/data.yaml" \
  --ledger "$R/sample_ledger.json" \
  --output "$R/detection_quality_v2/C4_development" \
  --model-id C4_V_flame_960_s0 --imgsz 960 --device 0
