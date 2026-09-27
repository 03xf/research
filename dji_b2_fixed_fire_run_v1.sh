#!/usr/bin/env bash
set -euo pipefail
root=/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1
video=/home/member/xmy/data/苏州放火_实验数据集/02_第二批_20260908_0924_单火点/01_正式视频/无人机01_1581F7K3C251800CYBVP/DJI_202609080913_003
tools_dir=/home/member/xmy/xmy/code/tools
/home/member/bin/python "$tools_dir/dji_realtime_replay_v3.py" \
  --root "$root" \
  --visible "$video/DJI_20260908092431_0003_V.MP4" \
  --thermal "$video/DJI_20260908092431_0003_T.MP4" \
  --batch B2 --session DJI_202609080913_003 --video-group DJI_20260908092431_0003 \
  --start-s 20 --duration-s 40 \
  --scene-map "$tools_dir/b2_fixed_fire_scene_v1.json" \
  --dashboard "$tools_dir/dji_b2_fixed_fire_dashboard_v1.html" \
  --fixed-point-id B2_fixed_fire \
  --tracker "$tools_dir/bytetrack_recovery_v1.yaml" \
  --output "$root/realtime_b2_v1/B2_fixed_fire_20_60" \
  --port 8807 --v-gpu 0 --t-gpu 1 --serve-after
