#!/bin/sh
set -eu
R=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
/home/member/bin/python /home/member/xmy/xmy/code/tools/recovery_v1_evaluate.py \
  --weights "$R/runs/E2_V_960_s0/weights/best.pt" \
  --data "$R/dataset_review_applied_v1/V/data.yaml" \
  --ledger "$R/sample_ledger.json" \
  --output "$R/detection_quality_v2/V1536_development" \
  --model-id E2_V_input1536 --imgsz 1536 --device 0
