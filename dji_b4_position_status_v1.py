"""Archive the prior recovery status and register the audited B4 display."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/home/member/xmy/xmy/results/dji_adaptation/b4_trial_v7/recovery_v1')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    status_path = ROOT / 'status_current.json'
    run = ROOT / 'realtime_v3' / 'B4_primary_location_dashboard_replay'
    validation_path = ROOT / 'realtime_v3' / 'B4_location_validation_v2.json'
    scene_path = ROOT / 'realtime_v3' / 'scene_map_b4_1039_006_v1.json'
    report_path = ROOT / 'realtime_v3' / 'REPORT_20260926.md'
    manifest_path = run / 'manifest.json'
    for path in (status_path, validation_path, scene_path, report_path, manifest_path,
                 run / 'results.jsonl', run / 'positions.csv', run / 'pairs.csv'):
        if not path.is_file():
            raise FileNotFoundError(path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    validation = json.loads(validation_path.read_text(encoding='utf-8'))
    totals = validation['totals']
    assert manifest['errors'] == []
    assert manifest['frames'] == {'V': 150, 'T': 150}
    assert manifest['paired_count'] == 150
    assert manifest['scene_map_sha256'] == digest(scene_path)
    assert validation['scene_map_sha256'] == digest(scene_path)
    assert validation['reviewed_pair_count'] == 30
    assert (totals['V_truth_sources'], totals['V_located_sources']) == (32, 18)
    assert (totals['T_truth_sources'], totals['T_located_sources']) == (32, 17)
    assert totals['V_wrong_coordinates_on_reviewed_frames'] == 0
    assert totals['T_wrong_coordinates_on_reviewed_frames'] == 0
    assert totals['prelight_candidates_with_coordinate'] == 0
    previous_bytes = status_path.read_bytes()
    status = json.loads(previous_bytes)
    if 'realtime_v3' in status:
        raise ValueError('realtime_v3 already registered; refusing to overwrite')
    history = ROOT / 'status_history' / (hashlib.sha256(previous_bytes).hexdigest() + '.json')
    if history.exists() and history.read_bytes() != previous_bytes:
        raise ValueError('status archive collision')
    if not history.exists():
        history.write_bytes(previous_bytes)
    now = datetime.now(timezone.utc).isoformat()
    status['updated_utc'] = now
    status['stage'] = 'b4_visual_source_lookup_and_dashboard_complete'
    status['status_history_archived'] = str(history)
    status['realtime_v3'] = {
        'status': 'complete_exploratory',
        'primary_batch': 'B4',
        'default_models': 'frozen E2 V and E2 T',
        'scene_map': str(scene_path),
        'scene_map_sha256': digest(scene_path),
        'primary_run': str(run),
        'primary_manifest_sha256': digest(manifest_path),
        'validation': str(validation_path),
        'validation_sha256': digest(validation_path),
        'report': str(report_path),
        'report_sha256': digest(report_path),
        'reviewed_pairs': 30,
        'source_coverage': {'V': '18/32', 'T': '17/32'},
        'coordinate_mismatches_on_reviewed_frames': 0,
        'prelight_candidates_with_coordinate': 0,
        'browser_display_p95_ms_observed': 517,
        'browser_displayed_frames_observed': 180,
        'coordinate_method': 'lookup of existing approximate visual candidates',
        'independent_absolute_visual_WGS84': 'unavailable',
        'local_web_url_through_ssh_tunnel': 'http://127.0.0.1:18805/',
    }
    temp = ROOT / 'status_current.json.tmp_b4_position_v1'
    if temp.exists():
        raise FileExistsError(temp)
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(status_path)
    print(json.dumps({'stage': status['stage'], 'archive': str(history),
                      'validation_sha256': digest(validation_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
