"""Freeze the B4 real-time preview check without replacing prior runs."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--browser-p95-ms', type=float, required=True)
    parser.add_argument('--browser-displayed-frames', type=int, required=True)
    parser.add_argument('--web-url', required=True)
    args = parser.parse_args()
    root = args.root
    new_run = root / 'realtime_v2' / 'B4_primary_browser_check'
    old_run = root / 'realtime_v1' / 'B4_primary_final'
    new_path = new_run / 'manifest.json'
    old_path = old_run / 'manifest.json'
    new = json.loads(new_path.read_text(encoding='utf-8'))
    old = json.loads(old_path.read_text(encoding='utf-8'))
    assert new['frames'] == {'V': 150, 'T': 150}
    assert new['paired_count'] == 150 and new['unpaired'] == {'V': 0, 'T': 0}
    assert new['errors'] == []
    assert new['web_preview'] == {'max_width_px': 640, 'jpeg_quality': 40, 'scope': 'web live preview only'}
    assert old['source_manifest_sha256'] == new['source_manifest_sha256']
    assert old['model_freeze_sha256'] == new['model_freeze_sha256']
    assert old['tracker_sha256'] == new['tracker_sha256']
    assert all(new['sustained_fps'][s] >= 4.9 for s in ('V', 'T'))
    records = sum(1 for _ in (new_run / 'results.jsonl').open(encoding='utf-8'))
    assert records == 300
    for sensor in ('V', 'T'):
        assert (new_run / sensor / 'tracked_browser.mp4').stat().st_size > 100000
    summary = {
        'schema_version': 'dji_b4_realtime_closeout_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'default_models': 'frozen E2 V and E2 T',
        'run': str(new_run),
        'manifest_sha256': digest(new_path),
        'previous_run': str(old_run),
        'previous_manifest_sha256': digest(old_path),
        'frames': new['frames'],
        'paired_count': new['paired_count'],
        'records_jsonl': records,
        'sustained_fps': new['sustained_fps'],
        'server_p95_ms': new['latency_p95_ms'],
        'browser_display_p95_ms': args.browser_p95_ms,
        'browser_displayed_frames': args.browser_displayed_frames,
        'browser_measurement': 'local in-app browser image load over SSH forwarding; viewer joined after playback began',
        'previous_browser_display_p95_ms': 1271,
        'web_url_local_tunnel': args.web_url,
        'web_preview': new['web_preview'],
        'per_track_coordinate': 'unavailable without confirmed physical source identity',
        'coordinate_table': 'batch LRF references and approximate visual candidates only',
        'absolute_visual_WGS84': 'unavailable',
    }
    out = root / 'realtime_v2' / 'B4_closeout_v1.json'
    write_new(out, summary)
    status_path = root / 'status_current.json'
    status_bytes = status_path.read_bytes()
    history = root / 'status_history' / (hashlib.sha256(status_bytes).hexdigest() + '.json')
    if not history.exists():
        history.write_bytes(status_bytes)
    status = json.loads(status_bytes)
    status['updated_utc'] = summary['created_utc']
    status['stage'] = 'b4_realtime_and_location_capability_report_complete'
    status['status_history_archived'] = str(history)
    status['realtime_v2'] = {
        'status': 'B4_primary_preview_complete',
        'default_models': summary['default_models'],
        'run': str(new_run),
        'manifest_sha256': summary['manifest_sha256'],
        'report': str(out),
        'browser_display_p95_ms': args.browser_p95_ms,
        'browser_displayed_frames': args.browser_displayed_frames,
        'server_p95_ms': new['latency_p95_ms'],
        'absolute_visual_WGS84': 'unavailable',
    }
    temp = root / 'status_current.json.tmp_b4_closeout'
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(status_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
