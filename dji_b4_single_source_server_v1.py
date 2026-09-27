"""Serve one selected B4 video fire from the frozen multi-source replay.

This view filters associations only. Original model outputs and files stay intact.
"""
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path

import dji_realtime_replay_v3 as replay
from dji_realtime_replay_v3 import Handler, View, candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--focus-id', required=True)
    parser.add_argument('--port', type=int, default=8806)
    args = parser.parse_args()
    root, run = args.root, args.run
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    scene = json.loads(Path(manifest['scene_map']).read_text(encoding='utf-8')) if manifest.get('scene_map') else None
    if scene is None:
        raise ValueError('Run has no verified video source map')
    selected = [x for x in scene['sources'] if x['point_id'] == args.focus_id]
    if len(selected) != 1:
        raise ValueError(f'Focus point must be one video source: {args.focus_id}')
    scene = {**scene, 'sources': selected, 'source_count': 1,
             'single_source_view': True}
    batch = scene['batch_id'] if scene else 'unknown'
    inventory = root.parent / 'localization_v2' / 'fire_coordinate_inventory_v3.csv'
    points = [x for x in candidates(inventory, batch) if x['point_id'] == args.focus_id]
    if len(points) != 1:
        raise ValueError(f'Coordinate inventory lacks selected point: {args.focus_id}')
    view = View(points,
                '解码时间戳，50毫秒内配对' if manifest['mode'] == 'clip' else '到达时间候选，设备同步未验证', scene)
    latest = {}
    with (run / 'results.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            sensor = event['sensor']
            # Retain unassigned detections as context, but never show another
            # source's coordinates or marker in this single-point view.
            event = {**event, 'positions': [p for p in event['positions']
                     if p.get('point_id') in (None, args.focus_id)]}
            latest[sensor] = event
            view.replay.append({k: event[k] for k in ('sensor', 'frame_seq', 'pts_s', 'positions', 'fps', 'dropped', 'latency_ms')})
            view.timeline.append({
                'sensor': sensor, 'frame_seq': event['frame_seq'], 'pts_s': event['pts_s'],
                'raw_count': len(event['raw_detections']),
                'linked': any(p.get('point_id') == args.focus_id and
                              p['association_status'] == 'provisional_visual_lookup'
                              for p in event['positions']),
            })
    for sensor in ('V', 'T'):
        event = latest[sensor]
        view.state['sensors'][sensor] = {k: event[k] for k in ('frame_seq', 'pts_s', 'tracks', 'positions', 'latency_ms', 'fps', 'dropped', 'source_wall_ms')}
    view.state.update({
        'run_status_zh': '完成', 'paired_count': manifest['paired_count'],
        'unpaired_V': manifest['unpaired']['V'], 'unpaired_T': manifest['unpaired']['T'],
        'last_pair_delta_ms': None, 'latency_p95_ms': manifest['latency_p95_ms'],
    })
    Handler.view, Handler.output_dir = view, run
    replay.HTML = Path(__file__).with_name('dji_b4_dashboard_single_v1.html').read_text(encoding='utf-8')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(json.dumps({'url': f'http://127.0.0.1:{args.port}/', 'focus_id': args.focus_id, 'run': str(run),
                      'replay_rows': len(view.replay)}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
