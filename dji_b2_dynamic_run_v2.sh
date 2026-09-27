#!/usr/bin/env bash
set -euo pipefail
root=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
tools_dir=/home/member/xmy/xmy/code/tools
/home/member/bin/python "$tools_dir/dji_realtime_replay_v3.py" \
  --root "$root" \
  --clip "$root/realtime_b2_v1/B2_fixed_fire_20_60/decoded_input" \
  --scene-map "$tools_dir/b2_fixed_fire_scene_v1.json" \
  --telemetry-json "$root/realtime_b2_v1/B2_telemetry_20_60.json" \
  --dashboard "$tools_dir/dji_b2_dynamic_dashboard_v2.html" \
  --fixed-point-id B2_fixed_fire \
  --tracker "$tools_dir/bytetrack_recovery_v1.yaml" \
  --output "$root/realtime_b2_v1/B2_dynamic_20_60" \
  --port 8808 --v-gpu 0 --t-gpu 1 --serve-after
