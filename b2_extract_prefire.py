import json
import subprocess
from pathlib import Path

base = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1')
original = base/'b2_candidate_v1/replay_B2_20_60_v3/decoded_input/manifest.json'
src = json.loads(original.read_text())['source']
out = base/'b2_auto_round4/prefire_0_20_decoded'
cmd = ['/home/member/bin/python', '/home/member/xmy/xmy/code/tools/recovery_v1_extract_custom_clip.py',
       '--visible', src['visible_video'], '--thermal', src['thermal_video'],
       '--start', '0', '--duration', '20', '--output', str(out),
       '--batch', 'B2', '--session', src['session_id'], '--video-group', src['video_group']]
print(subprocess.run(cmd, check=True).returncode)
