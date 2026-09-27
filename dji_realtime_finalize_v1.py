"""Record verified realtime prototype results without deleting historical status."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1')
STATUS = ROOT / 'status_current.json'
RUNS = ROOT / 'realtime_v1'
SOURCE_TRUTH = ROOT / 'source_truth_review_v1'
TOOLS = Path('/home/member/xmy/xmy/code/tools')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    status = read_json(STATUS)
    b3 = read_json(RUNS / 'B3_verified_final' / 'manifest.json')
    b4_primary = read_json(RUNS / 'B4_primary_final' / 'manifest.json')
    b4 = read_json(RUNS / 'B4_verified_ui_demo' / 'manifest.json')
    recorded = read_json(RUNS / 'B4_recorded_pair_demo' / 'manifest.json')
    stream = read_json(RUNS / 'B3_dualstream_demo' / 'manifest.json')
    evaluation = read_json(SOURCE_TRUTH / 'evaluation_v2.json')
    temporal = read_json(SOURCE_TRUTH / 'temporal_comparison_v2.json')
    assert b3['frames'] == {'V': 150, 'T': 150} and b3['paired_count'] == 150
    assert b4_primary['frames'] == {'V': 150, 'T': 150} and b4_primary['paired_count'] == 150
    assert not any(x['errors'] for x in (b3, b4_primary, b4, recorded, stream))
    assert evaluation['totals']['V_matched'] == 33 and evaluation['totals']['V_truth'] == 52
    assert evaluation['totals']['T_matched'] == 54 and evaluation['totals']['T_truth'] == 72
    assert temporal['totals']['stable']['T_matched'] == 41
    assert sha256(TOOLS / 'dji_realtime_replay_v1.py') == '8f2794bba53c72a0f8da2485482804cecb420e5a11dcff1f917e6690e71ce621'

    now = datetime.now(timezone.utc)
    history = ROOT / 'status_history'
    history.mkdir(exist_ok=True)
    snapshot = history / f"pre_realtime_v1_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    snapshot.write_bytes(STATUS.read_bytes())

    status['updated_utc'] = now.isoformat()
    status['stage'] = 'realtime_v1_prototype_complete_with_raw_detection_retained'
    status['next_action'] = (
        'Discuss whether to start a new detector data/training experiment, prioritizing V flame misses or T hot-background false detections; '
        'keep the current confirmation thresholds and model frozen until a new experiment is agreed.'
    )
    status['source_truth_tracking_evaluation_v2'] = {
        'status': 'complete',
        'file': str(SOURCE_TRUTH / 'evaluation_v2.json'),
        'V_matched': 33, 'V_truth': 52,
        'T_matched': 54, 'T_truth': 72,
        'T_negative_frames_with_detection': 9,
        'same_source_both_detected_pairs': 22,
        'exploratory_existing_truth': True,
    }
    status['realtime_v1'] = {
        'status': 'prototype_complete',
        'primary_batch': 'B4',
        'primary_run': str(RUNS / 'B4_primary_final'),
        'primary_web_url_local_tunnel': 'http://127.0.0.1:18794/',
        'B3_role': 'supplementary_comparison',
        'raw_detection_retained': True,
        'hard_temporal_filter': 'rejected_due_to_T_matching_loss_54_to_41',
        'temporal_comparison': str(SOURCE_TRUTH / 'temporal_comparison_v2.json'),
        'scripts': {
            name: {'path': str(TOOLS / name), 'sha256': sha256(TOOLS / name)}
            for name in ('dji_realtime_replay_v1.py', 'dji_temporal_rules_v1.py',
                         'dji_source_truth_eval_v2.py', 'dji_temporal_compare_v1.py',
                         'dji_realtime_diagnostics_v1.py')
        },
        'runs': {
            name: {'manifest': str(RUNS / name / 'manifest.json'),
                   'frames': data['frames'], 'paired_count': data['paired_count'],
                   'sustained_fps': data['sustained_fps'],
                   'server_latency_p95_ms': data['latency_p95_ms'],
                   'errors': data['errors']}
            for name, data in (('B4_primary_final', b4_primary), ('B3_verified_final', b3), ('B4_verified_ui_demo', b4),
                               ('B4_recorded_pair_demo', recorded), ('B3_dualstream_demo', stream))
        },
        'browser_display_latency_observations': {
            'B3_verified_final': {'p95_ms': 458, 'displayed_frames': 163, 'method': 'local browser image onload after exact sequence JPEG fetch over SSH tunnel'},
            'B4_primary_final': {'p95_ms': 1271, 'displayed_frames': 53, 'method': 'same; this session did not meet the 500 ms display target'},
            'B4_verified_ui_demo': {'p95_ms': 446, 'displayed_frames': 47, 'method': 'same; viewer joined after replay began'},
        },
        'continuity_diagnostics': str(RUNS / 'continuity_exploratory_v1.json'),
        'report': str(RUNS / 'REPORT_20260925.md'),
        'absolute_visual_localization': 'unavailable',
        'per_track_coordinate': 'unavailable_without_human_physical_source_association',
        'live_stream_sync': 'arrival_time_only_unverified',
    }
    temporary = STATUS.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(STATUS)
    print(json.dumps({'stage': status['stage'], 'backup': str(snapshot), 'status': str(STATUS)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
