"""Serve the completed B2 V/T replay from local files, without an SSH tunnel."""
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path

import dji_realtime_replay_v3 as replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18809)
    args = parser.parse_args()
    manifest = json.loads((args.run / 'manifest.json').read_text(encoding='utf-8'))
    events = [json.loads(line) for line in (args.run / 'results.jsonl').open(encoding='utf-8')]
    view = replay.View([], '原视频解码时间戳', None)
    latest = {}
    for event in events:
        sensor = event['sensor']
        latest[sensor] = event
        view.replay.append({key: event[key] for key in
                            ('sensor', 'frame_seq', 'pts_s', 'positions', 'fps', 'dropped', 'latency_ms')})
    for sensor in ('V', 'T'):
        event = latest[sensor]
        view.state['sensors'][sensor] = {key: event[key] for key in
            ('frame_seq', 'pts_s', 'tracks', 'positions', 'latency_ms', 'fps', 'dropped', 'source_wall_ms')}
    view.state.update({'run_status_zh': '完成', 'paired_count': manifest['paired_count'],
                       'unpaired_V': manifest['unpaired']['V'], 'unpaired_T': manifest['unpaired']['T'],
                       'latency_p95_ms': manifest['latency_p95_ms']})
    replay.HTML = Path(__file__).with_name('dji_b2_dynamic_dashboard_v2.html').read_text(encoding='utf-8')
    replay.Handler.view = view
    replay.Handler.output_dir = args.run
    server = ThreadingHTTPServer(('127.0.0.1', args.port), replay.Handler)
    print(f'http://127.0.0.1:{args.port}/', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
