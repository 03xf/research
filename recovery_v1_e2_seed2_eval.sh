#!/usr/bin/env bash
set -euo pipefail
root=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
entry=/home/member/xmy/xmy/code/tools/recovery_v1_evaluate.py
python=/home/member/bin/python
for sensor in T V; do
  "$python" "$entry" \
    --weights "$root/runs/E2_${sensor}_960_s2/weights/best.pt" \
    --data "$root/dataset_review_applied_v1/$sensor/data.yaml" \
    --ledger "$root/sample_ledger.json" \
    --output "$root/evaluations/E2_${sensor}_960_s2" \
    --model-id "E2_${sensor}_960_s2" \
    --imgsz 960 --device 0 \
    > "$root/E2_${sensor}_960_s2_eval.log" 2>&1
done
