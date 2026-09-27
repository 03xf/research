"""Small web UI for V/T ground-source truth review."""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DJI 火源真值标注</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#edf1f2;color:#20272a;font:14px system-ui,"Microsoft YaHei",sans-serif}header{display:flex;gap:8px;align-items:center;padding:10px 14px;background:#fff;border-bottom:1px solid #bac6ca}h1{font-size:17px;margin:0 12px 0 0}button,select,input{font:inherit;border:1px solid #a8b7bc;border-radius:4px;background:#fff;padding:7px;color:#20272a}button{cursor:pointer}button:hover{background:#e2eef0}.primary{background:#176b70;color:#fff;border-color:#176b70}.spacer{flex:1}.info{font-size:12px;color:#53666c}.layout{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}.panel{background:#fff;border:1px solid #bac6ca;border-radius:5px;padding:10px;min-width:0}.panel h2{margin:0 0 8px;font-size:16px}.stage{position:relative;width:100%;background:#111;min-height:220px}.stage img{display:block;width:100%;height:auto}.stage canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}.controls{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:8px 0}.pointlist{font:12px Consolas,monospace;background:#f5f7f7;border:1px solid #d0d9dc;min-height:32px;padding:6px;white-space:pre-wrap}.bottom{display:flex;gap:8px;align-items:center;padding:10px 12px;background:#fff;position:sticky;bottom:0;border-top:1px solid #bac6ca}.help{padding:0 12px 12px;color:#53666c}.warning{color:#a34f00}@media(max-width:900px){.layout{grid-template-columns:1fr}}
</style></head><body>
<header><h1>DJI 火源真值标注</h1><button id="prev">← 上一对</button><span id="counter"></span><span class="spacer"></span><span id="meta" class="info"></span></header>
<div class="help">点击图像添加地面火源点或热点候选。先填写片段内稳定的火源编号（例如 F1、F2），每个点可以单独撤销。烟雾不需要标注；热像高温地面、墙体和设备请选择高温背景。V/T关系指是否对应同一个物理火源，不是判断两张图是否已经成对。</div>
<main class="layout">
<section class="panel"><h2>V 可见光</h2><div class="stage"><img id="Vimg" alt="可见光原图"><canvas id="Vcanvas"></canvas></div><div class="controls"><label>火源编号 <input id="fireId" value="F1" size="6"></label><button id="Vundo">撤销 V 点</button><span id="Vpts" class="info"></span></div><div id="Vlist" class="pointlist"></div></section>
<section class="panel"><h2>T 热成像</h2><div class="stage"><img id="Timg" alt="T 原图"><canvas id="Tcanvas"></canvas></div><div class="controls"><button id="Tundo">撤销 T 点</button><span id="Tpts" class="info"></span></div><div id="Tlist" class="pointlist"></div><div class="warning">亮度高不等于燃烧。无法确认时选 unknown。</div></section>
</main>
<div class="bottom"><label>火源状态 <select id="sourceState"><option value="unknown">无法判断</option><option value="active_fire">明火</option><option value="residual_heat">余热</option><option value="hot_background">高温背景</option><option value="no_source">无火源</option></select></label><label>V/T火源关系 <select id="relation"><option value="unknown">未确认同一火源</option><option value="same_source">确认同一火源</option><option value="different_source">确认不同火源</option></select></label><label>热像背景 <select id="background"><option value="unknown">无法判断</option><option value="none">无</option><option value="hot_background">高温背景</option></select></label><label>帧状态 <select id="frameStatus"><option value="usable">可用</option><option value="unknown">无法判断</option></select></label><button id="save">保存</button><button class="primary" id="saveNext">保存并下一对 →</button><span id="status" class="info"></span></div>
<script>
const $=x=>document.getElementById(x);let tasks=[],i=0,item=null,points={V:[],T:[]},dirty=false;
async function api(url,options){let r=await fetch(url,options);if(!r.ok)throw Error(await r.text());return r.json()}
function canvasPoint(sensor,event){const c=$(sensor+'canvas'),r=c.getBoundingClientRect();return [Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))]}
function render(sensor){const img=$(sensor+'img'),c=$(sensor+'canvas');if(!img.naturalWidth)return;const w=img.clientWidth,h=img.clientHeight,d=devicePixelRatio||1;c.width=Math.round(w*d);c.height=Math.round(h*d);const g=c.getContext('2d');g.scale(d,d);g.clearRect(0,0,w,h);g.font='bold 14px system-ui';points[sensor].forEach((p,n)=>{const x=p[0]*w,y=p[1]*h;g.fillStyle=sensor==='V'?'#18d6ff':'#ff455c';g.beginPath();g.arc(x,y,7,0,Math.PI*2);g.fill();g.fillStyle='#fff';g.fillText(p[2]+' '+(n+1),x+9,y-9)});$(sensor+'pts').textContent=points[sensor].length+' 个点';$(sensor+'list').textContent=points[sensor].map((p,n)=>`${n+1}. ${p[2]} (${p[0].toFixed(3)}, ${p[1].toFixed(3)})`).join('\n')}
function add(sensor,e){if(!item)return;const p=canvasPoint(sensor,e);points[sensor].push([p[0],p[1],$('fireId').value.trim()||'F1']);dirty=true;render(sensor)}
async function load(n){if(dirty&&!confirm('当前修改未保存，继续切换？'))return;i=Math.max(0,Math.min(tasks.length-1,n));item=await api('/api/item?id='+encodeURIComponent(tasks[i].task_id));points={V:item.decision?.V?.points||[],T:item.decision?.T?.points||[]};$('sourceState').value=item.decision?.source_state||'unknown';$('relation').value=item.decision?.tv_relation||'unknown';$('background').value=item.decision?.thermal_background||'unknown';$('frameStatus').value=item.decision?.frame_status||'usable';$('counter').textContent=`第 ${i+1} / 共 ${tasks.length} 对`;$('meta').textContent=`${item.clip_id} · V时间 ${item.visible_pts_s?.toFixed?.(3)??item.visible_pts_s}秒 / T时间 ${item.thermal_pts_s?.toFixed?.(3)??item.thermal_pts_s}秒 · 时间差 ${item.delta_s?.toFixed?.(3)??item.delta_s}秒`;$('Vimg').src='/api/image?id='+encodeURIComponent(item.task_id)+'&sensor=V';$('Timg').src='/api/image?id='+encodeURIComponent(item.task_id)+'&sensor=T';dirty=false;$('status').textContent=item.decision?'已保存':'待标注';}
async function save(){if(!item)return;const payload={task_id:item.task_id,source_state:$('sourceState').value,frame_status:$('frameStatus').value,tv_relation:$('relation').value,thermal_background:$('background').value,V:{points:points.V},T:{points:points.T}};await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});dirty=false;$('status').textContent='已保存'}
$('Vcanvas').onclick=e=>add('V',e);$('Tcanvas').onclick=e=>add('T',e);$('Vundo').onclick=()=>{points.V.pop();dirty=true;render('V')};$('Tundo').onclick=()=>{points.T.pop();dirty=true;render('T')};$('prev').onclick=()=>load(i-1);$('save').onclick=save;$('saveNext').onclick=async()=>{await save();if(i<tasks.length-1)await load(i+1)};window.onresize=()=>{render('V');render('T')};$('Vimg').onload=()=>render('V');$('Timg').onload=()=>render('T');api('/api/list').then(x=>{tasks=x.tasks;return load(x.first_pending_index)}).catch(e=>$('status').textContent=e.message);
</script></body></html>'''


class Review:
    def __init__(self, root: Path):
        self.root = root
        self.queue_path = root / "queue.json"
        self.decisions_path = root / "decisions.json"
        self.lock = threading.Lock()
        data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.tasks = data["tasks"]
        self.by_id = {x["task_id"]: x for x in self.tasks}

    def list(self):
        data = json.loads(self.decisions_path.read_text(encoding="utf-8"))
        decisions = data.get("decisions", {})
        pending = next((n for n, task in enumerate(self.tasks) if task["task_id"] not in decisions), len(self.tasks) - 1)
        return {"tasks": self.tasks, "decided": len(decisions), "first_pending_index": pending}

    def item(self, task_id):
        if task_id not in self.by_id:
            raise ValueError("unknown task")
        task = self.by_id[task_id].copy()
        data = json.loads(self.decisions_path.read_text(encoding="utf-8"))
        task["decision"] = data.get("decisions", {}).get(task_id)
        return task

    def image(self, task_id, sensor):
        task = self.by_id[task_id]
        if sensor not in ("V", "T"):
            raise ValueError("invalid sensor")
        path = Path(task["visible_frame"] if sensor == "V" else task["thermal_frame"])
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_bytes()

    def save(self, payload):
        task_id = payload["task_id"]
        if task_id not in self.by_id:
            raise ValueError("unknown task")
        if payload.get("frame_status") not in ("usable", "unknown"):
            raise ValueError("invalid frame status")
        if payload.get("tv_relation") not in ("same_source", "different_source", "unknown"):
            raise ValueError("invalid relation")
        if payload.get("source_state") not in ("active_fire", "residual_heat", "hot_background", "no_source", "unknown"):
            raise ValueError("invalid source state")
        if payload.get("thermal_background") not in ("none", "hot_background", "unknown"):
            raise ValueError("invalid background")
        for sensor in ("V", "T"):
            for point in payload.get(sensor, {}).get("points", []):
                if len(point) != 3 or not isinstance(point[2], str) or not point[2].strip():
                    raise ValueError("point must be [x_norm, y_norm, fire_id]")
                if not (0 <= float(point[0]) <= 1 and 0 <= float(point[1]) <= 1):
                    raise ValueError("point coordinates must be normalized")
        result = {"task_id": task_id, "saved_utc": datetime.now(timezone.utc).isoformat(),
                  "source_state": payload["source_state"],
                  "frame_status": payload["frame_status"], "tv_relation": payload["tv_relation"],
                  "thermal_background": payload["thermal_background"],
                  "V": {"points": payload.get("V", {}).get("points", [])},
                  "T": {"points": payload.get("T", {}).get("points", [])}}
        with self.lock:
            data = json.loads(self.decisions_path.read_text(encoding="utf-8"))
            data.setdefault("decisions", {})[task_id] = result
            temp = self.decisions_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(self.decisions_path)
            with (self.root / "review_history.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        return result


class Handler(BaseHTTPRequestHandler):
    review = None

    def send_bytes(self, value, content_type="application/json", status=200):
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(value))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(value)

    def send_json(self, value): self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        url = urlparse(self.path); q = parse_qs(url.query)
        try:
            if url.path == "/": self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif url.path == "/api/list": self.send_json(Handler.review.list())
            elif url.path == "/api/item": self.send_json(Handler.review.item(q["id"][0]))
            elif url.path == "/api/image": self.send_bytes(Handler.review.image(q["id"][0], q["sensor"][0]), "image/jpeg")
            else: self.send_error(404)
        except (KeyError, ValueError, FileNotFoundError) as e: self.send_error(400, str(e))

    def do_POST(self):
        try:
            if self.path != "/api/save": self.send_error(404); return
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 100000: raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            self.send_json(Handler.review.save(payload))
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e: self.send_error(400, str(e))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True); ap.add_argument("--port", type=int, default=8782); args = ap.parse_args()
    Handler.review = Review(args.root)
    print(f"DJI source truth review: http://127.0.0.1:{args.port}/; tasks={len(Handler.review.tasks)}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
