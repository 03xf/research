#!/usr/bin/env python3
"""Small dependency-free browser annotator for the DJI T/V manifest.

The server edits only observation.annotation in the supplied manifest. It is
intended to be used through an SSH tunnel and binds to 127.0.0.1 by default.
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


VALID_V = {"smoke", "flame"}
VALID_T = {"hotspot"}
VALID_QUALITY = {"unlabeled", "clear", "weak", "ambiguous", "unusable"}
VALID_VISIBILITY = {"unlabeled", "visible", "thermal", "both", "none"}


HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DJI T/V 标注</title>
<style>
:root{color-scheme:dark;--bg:#111827;--panel:#1f2937;--muted:#9ca3af;--accent:#38bdf8;--border:#374151}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#f3f4f6;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}
header{height:58px;padding:10px 16px;background:#0b1220;display:flex;gap:12px;align-items:center;border-bottom:1px solid var(--border)}
header h1{font-size:17px;margin:0 14px 0 0}button,select,input{background:#111827;color:#f3f4f6;border:1px solid #4b5563;border-radius:5px;padding:7px 9px}button{cursor:pointer}button:hover{border-color:var(--accent)}button.primary{background:#0369a1;border-color:#0ea5e9}button.danger{border-color:#ef4444;color:#fecaca}
#status{margin-left:auto;color:#a7f3d0;white-space:nowrap}.layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:12px;padding:12px;height:calc(100vh - 58px)}
.viewer{display:grid;grid-template-columns:1fr 1fr;gap:12px;min-width:0}.card,.side{background:var(--panel);border:1px solid var(--border);border-radius:7px;padding:10px;min-width:0}.card h2{font-size:15px;margin:0 0 8px}.canvas-wrap{position:relative;background:#000;overflow:hidden;min-height:300px}.canvas-wrap img{display:block;max-width:100%;width:100%;height:auto}.canvas-wrap canvas{position:absolute;left:0;top:0;width:100%;height:100%;cursor:crosshair}.hint{color:var(--muted);font-size:12px;margin-top:6px}.side{overflow:auto}.row{display:flex;gap:7px;align-items:center;margin:8px 0;flex-wrap:wrap}.row label{color:#d1d5db}.stat{color:#cbd5e1;font-size:12px;line-height:1.5}.box-list{max-height:180px;overflow:auto;border:1px solid var(--border);padding:5px}.box-item{display:flex;justify-content:space-between;gap:5px;border-bottom:1px solid #374151;padding:4px 0;font-size:12px}.box-item:last-child{border:0}.box-item button{padding:2px 5px}.section{border-top:1px solid var(--border);margin-top:10px;padding-top:8px}.nav{display:flex;gap:7px;align-items:center}.nav input{width:82px}.warning{color:#fbbf24}.ok{color:#86efac}.small{font-size:12px;color:var(--muted)}
@media(max-width:1000px){.layout{grid-template-columns:1fr;height:auto}.viewer{grid-template-columns:1fr}.side{overflow:visible}}
</style></head><body>
<header><h1>DJI T/V 成对标注</h1><button id="prev">上一组</button><button id="next">下一组</button><div class="nav"><input id="jump" type="number" min="1"><button id="jumpBtn">跳转</button></div><button id="save" class="primary">保存 (Ctrl+S)</button><button id="clear">清空当前框</button><span id="status">加载中…</span></header>
<main class="layout"><section class="viewer"><div class="card"><h2>可见光 V <span class="small" id="vMeta"></span></h2><div class="canvas-wrap"><img id="vImg"><canvas id="vCanvas"></canvas></div><div class="hint">拖拽画框；类别使用右侧 V 类别。绿色为当前人工框，虚线为已有模型预测（仅供参考）。</div><div class="box-list" id="vBoxes"></div></div>
<div class="card"><h2>热成像 T <span class="small" id="tMeta"></span></h2><div class="canvas-wrap"><img id="tImg"><canvas id="tCanvas"></canvas></div><div class="hint">拖拽画框；类别使用右侧 T 类别。不要把模型框直接当人工框。</div><div class="box-list" id="tBoxes"></div></div></section>
<aside class="side"><div id="obsInfo" class="stat"></div><div class="section"><b>当前画框类别</b><div class="row"><label><input type="radio" name="sensor" value="V" checked> V</label><select id="vClass"><option value="smoke">smoke 烟雾</option><option value="flame">flame 明火</option></select><label><input type="radio" name="sensor" value="T"> T</label><select id="tClass"><option value="hotspot">hotspot 高温</option></select></div><div class="small">先选择 V/T 和类别，再在对应图像拖拽。点击框列表的删除可移除单个框。</div></div>
<div class="section"><b>标注状态</b><div class="row"><label>质量 <select id="quality"><option value="unlabeled">unlabeled</option><option value="clear">clear 清晰</option><option value="weak">weak 较弱</option><option value="ambiguous">ambiguous 不确定</option><option value="unusable">unusable 不可用</option></select></label></div><div class="row"><label>可见性 <select id="visibility"><option value="unlabeled">unlabeled</option><option value="visible">visible 仅V</option><option value="thermal">thermal 仅T</option><option value="both">both T/V都有</option><option value="none">none 确认无目标</option></select></label></div><div class="row"><label>fire_event_id <input id="eventId" placeholder="不确定则留空"></label></div></div>
<div class="section"><b>当前组信息</b><div id="prediction" class="stat"></div><div class="small">LRF 坐标仅作空间参考，不等于火焰中心真值。</div></div>
<div class="section"><b>进度</b><div id="progress" class="stat"></div><div class="row"><button id="unlabeled">跳到下一未标注</button><button id="review">跳到下一待复核</button></div></div>
<div class="section"><span class="warning">保存后才会写入服务器。不要创建 ANNOTATION_READY，直到人工标注和校验完成。</span></div></aside></main>
<script>
const S={items:[],idx:0,obs:null,frames:null,boxes:{V:[],T:[]},dirty:false,drag:null};
const $=id=>document.getElementById(id); const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,opt){const r=await fetch(url,opt);if(!r.ok)throw Error(await r.text());return r.json()}
function setStatus(x,good=false){$('status').textContent=x;$('status').className=good?'ok':''}
function selectedSensor(){return document.querySelector('input[name=sensor]:checked').value}
function setupCanvas(sensor){const c=$(sensor.toLowerCase()+'Canvas'),img=$(sensor.toLowerCase()+'Img'); const rect=()=>c.getBoundingClientRect();
 c.onpointerdown=e=>{const r=rect();S.drag={x:(e.clientX-r.left)/r.width,y:(e.clientY-r.top)/r.height};c.setPointerCapture(e.pointerId)};
 c.onpointerup=e=>{if(!S.drag)return;const r=rect(),x=(e.clientX-r.left)/r.width,y=(e.clientY-r.top)/r.height;let a=Math.max(0,Math.min(1,S.drag.x)),b=Math.max(0,Math.min(1,S.drag.y)),d=Math.max(0,Math.min(1,x)),f=Math.max(0,Math.min(1,y));let box={x1:Math.min(a,d),y1:Math.min(b,f),x2:Math.max(a,d),y2:Math.max(b,f)};S.drag=null;if((box.x2-box.x1)<.005||(box.y2-box.y1)<.005)return;S.boxes[sensor].push({class:sensor==='V'?$('vClass').value:$('tClass').value,box});S.dirty=true;draw(sensor);renderBoxes(sensor)};
 img.onload=()=>draw(sensor);}
function draw(sensor){const img=$(sensor.toLowerCase()+'Img'),c=$(sensor.toLowerCase()+'Canvas');if(!img.naturalWidth)return;const r=img.getBoundingClientRect(),d=window.devicePixelRatio||1;c.width=r.width*d;c.height=r.height*d;const x=c.getContext('2d');x.scale(c.width,c.height);x.clearRect(0,0,1,1);x.lineWidth=2/d/r.width;x.font='14px sans-serif';
 const pred=(S.obs||{})[sensor==='V'?'visible_detection':'thermal_detection']||{}; const fw=S.frames?.[sensor]?.width||1,fh=S.frames?.[sensor]?.height||1; (pred.boxes||[]).forEach((q,i)=>{x.setLineDash([.01,.008]);x.strokeStyle='rgba(250,204,21,.75)';x.strokeRect(q[0]/fw,q[1]/fh,(q[2]-q[0])/fw,(q[3]-q[1])/fh);x.setLineDash([])});
 S.boxes[sensor].forEach((q,i)=>{x.strokeStyle=sensor==='V'?'#34d399':'#f472b6';x.fillStyle=sensor==='V'?'#34d399':'#f472b6';x.strokeRect(q.box.x1,q.box.y1,q.box.x2-q.box.x1,q.box.y2-q.box.y1);x.fillText(q.class+' '+(i+1),q.box.x1+0.005,Math.max(.02,q.box.y1-.005))});}
function renderBoxes(sensor){const el=$(sensor.toLowerCase()+'Boxes');el.innerHTML=S.boxes[sensor].length?S.boxes[sensor].map((q,i)=>`<div class="box-item"><span>${i+1}. ${esc(q.class)} [${[q.box.x1,q.box.y1,q.box.x2,q.box.y2].map(v=>v.toFixed(3)).join(', ')}]</span><button data-s="${sensor}" data-i="${i}">删除</button></div>`).join(''):'<span class="small">暂无人工框</span>';el.querySelectorAll('button').forEach(b=>b.onclick=()=>{S.boxes[b.dataset.s].splice(+b.dataset.i,1);S.dirty=true;draw(b.dataset.s);renderBoxes(b.dataset.s)})}
function toPixels(sensor,q){const w=S.frames[sensor].width,h=S.frames[sensor].height;return [q.box.x1*w,q.box.y1*h,q.box.x2*w,q.box.y2*h].map(v=>Math.round(v*100)/100)}
function normalizedLabels(labels,sensor){const f=S.frames[sensor];return (labels||[]).filter(q=>q&&Array.isArray(q.bbox_xyxy)&&q.bbox_xyxy.length===4).map(q=>({class:q.class,box:{x1:q.bbox_xyxy[0]/f.width,y1:q.bbox_xyxy[1]/f.height,x2:q.bbox_xyxy[2]/f.width,y2:q.bbox_xyxy[3]/f.height}}))}
async function load(i){if(S.dirty&&!confirm('当前有未保存修改，确定切换吗？'))return;S.idx=Math.max(0,Math.min(S.items.length-1,i));const id=S.items[S.idx];const d=await api('/api/observation?id='+encodeURIComponent(id));S.obs=d.observation;S.frames=d.frames;S.boxes={V:normalizedLabels(S.obs.annotation.visible_labels,'V'),T:normalizedLabels(S.obs.annotation.thermal_labels,'T')};
 $('vImg').src='/frames/'+S.frames.V.relative;$('tImg').src='/frames/'+S.frames.T.relative;$('vMeta').textContent=`${S.frames.V.width}×${S.frames.V.height}`;$('tMeta').textContent=`${S.frames.T.width}×${S.frames.T.height}`;$('jump').value=S.idx+1;$('quality').value=S.obs.annotation.annotation_quality||'unlabeled';$('visibility').value=S.obs.annotation.visibility||'unlabeled';$('eventId').value=S.obs.annotation.fire_event_id||'';$('obsInfo').innerHTML=`<b>${esc(S.obs.observation_id)}</b><br>批次 ${esc(S.obs.batch_id)} · session ${esc(S.obs.session_id)} · ${esc(S.obs.video_group)}<br>时间 ${Number(S.obs.timestamp_s||0).toFixed(3)} s · 同步差 ${Number(S.obs.sync_delta_s||0).toFixed(4)} s · split ${esc(S.obs.split)}`;
 const vd=S.obs.visible_detection||{},td=S.obs.thermal_detection||{};$('prediction').innerHTML=`模型参考：V ${vd.boxes?.length||0} 框，T ${td.boxes?.length||0} 框；仅供参考，不会自动写入人工标注。`;S.dirty=false;renderBoxes('V');renderBoxes('T');setStatus(`第 ${S.idx+1}/${S.items.length} 组`,true);draw('V');draw('T');}
async function save(){if(!S.obs)return;const a={visible_labels:S.boxes.V.map(q=>({class:q.class,bbox_xyxy:toPixels('V',q)})),thermal_labels:S.boxes.T.map(q=>({class:q.class,bbox_xyxy:toPixels('T',q)})),fire_event_id:$('eventId').value.trim()||null,visibility:$('visibility').value,annotation_quality:$('quality').value};setStatus('保存中…');try{await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({observation_id:S.obs.observation_id,annotation:a})});S.obs.annotation=a;S.dirty=false;setStatus('已保存',true);await refreshProgress()}catch(e){setStatus('保存失败: '+e.message)}}
async function refreshProgress(){const d=await api('/api/progress');$('progress').innerHTML=`已明确标注 ${d.reviewed}/${d.total} · 未标注 ${d.unlabeled} · 待复核 ${d.review_queue} · clear ${d.clear} · weak ${d.weak}`}
async function findNext(pred){for(let k=1;k<=S.items.length;k++){let j=(S.idx+k)%S.items.length;const o=await api('/api/summary?id='+encodeURIComponent(S.items[j]));if(pred(o))return load(j)}alert('没有找到符合条件的观测')}
async function init(){setupCanvas('V');setupCanvas('T');const d=await api('/api/index');S.items=d.ids;await load(0);await refreshProgress()}
$('prev').onclick=()=>load(S.idx-1);$('next').onclick=()=>load(S.idx+1);$('jumpBtn').onclick=()=>load(+$('jump').value-1);$('save').onclick=save;$('clear').onclick=()=>{S.boxes={V:[],T:[]};S.dirty=true;renderBoxes('V');renderBoxes('T');draw('V');draw('T')};$('unlabeled').onclick=()=>findNext(o=>o.quality==='unlabeled');$('review').onclick=()=>findNext(o=>['weak','ambiguous','unusable'].includes(o.quality));document.onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();save()}if(e.key==='ArrowRight'&&!e.ctrlKey)load(S.idx+1);if(e.key==='ArrowLeft'&&!e.ctrlKey)load(S.idx-1)};window.onresize=()=>{draw('V');draw('T')};init().catch(e=>setStatus('加载失败: '+e.message));
</script></body></html>'''


class App:
    def __init__(self, manifest, frames_index, review_queue=None, batch=None, limit=None, candidates=None):
        self.manifest_path = Path(manifest).resolve()
        self.frames_path = Path(frames_index).resolve()
        self.frames_root = self.frames_path.parent.resolve()
        self.review_queue_path = Path(review_queue).resolve() if review_queue else None
        self.batch = batch
        self.limit = limit
        self.candidates_path = Path(candidates).resolve() if candidates else None
        self.lock = threading.RLock()
        self.load()

    def load(self):
        self.data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.frames = json.loads(self.frames_path.read_text(encoding="utf-8")).get("frames", {})
        all_rows = self.data.get("observations", [])
        if self.batch:
            all_rows = [x for x in all_rows if x.get("batch_id") == self.batch]
        self.by_id = {x["observation_id"]: x for x in all_rows}
        self.ids = list(self.by_id)
        if self.candidates_path and self.candidates_path.exists():
            candidate_ids = json.loads(self.candidates_path.read_text(encoding="utf-8")).get("observation_ids", [])
            self.ids = [oid for oid in candidate_ids if oid in self.by_id]
            self.by_id = {oid: self.by_id[oid] for oid in self.ids}
        if self.limit and len(self.ids) > self.limit:
            # Round-robin by video group so a small trial set covers every group.
            groups = {}
            for oid in self.ids:
                groups.setdefault(self.by_id[oid].get("video_group", ""), []).append(oid)
            selected = []
            while len(selected) < self.limit and groups:
                for key in list(groups):
                    if groups[key]:
                        selected.append(groups[key].pop(0))
                        if len(selected) >= self.limit:
                            break
                    if not groups[key]:
                        del groups[key]
            self.ids = selected
            self.by_id = {oid: self.by_id[oid] for oid in self.ids}
        self.queue = set()
        if self.review_queue_path and self.review_queue_path.exists():
            q = json.loads(self.review_queue_path.read_text(encoding="utf-8"))
            for item in q.get("items", q if isinstance(q, list) else []):
                if isinstance(item, dict) and item.get("observation_id"):
                    self.queue.add(item["observation_id"])

    def relative_frame(self, info):
        p = Path(info["path"]).resolve()
        p.relative_to(self.frames_root)
        out = dict(info)
        out["relative"] = p.relative_to(self.frames_root).as_posix()
        return out

    def observation(self, oid):
        with self.lock:
            o = self.by_id[oid]
            f = self.frames[oid]
            return {"observation": o, "frames": {k: self.relative_frame(v) for k, v in f.items()}}

    def summary(self, oid):
        o = self.by_id[oid]
        a = o.get("annotation", {})
        return {"observation_id": oid, "quality": a.get("annotation_quality", "unlabeled"), "has_labels": bool(a.get("visible_labels") or a.get("thermal_labels"))}

    def progress(self):
        counts = {x: 0 for x in VALID_QUALITY}
        for o in self.by_id.values():
            counts[o.get("annotation", {}).get("annotation_quality", "unlabeled")] = counts.get(o.get("annotation", {}).get("annotation_quality", "unlabeled"), 0) + 1
        return {"total": len(self.ids), "reviewed": len(self.ids)-counts.get("unlabeled", 0), "unlabeled": counts.get("unlabeled", 0), "review_queue": len(self.queue), **{k: counts.get(k, 0) for k in ("clear", "weak", "ambiguous", "unusable")}}

    def validate_annotation(self, a):
        if not isinstance(a, dict): raise ValueError("annotation must be an object")
        q, vis = a.get("annotation_quality"), a.get("visibility")
        if q not in VALID_QUALITY: raise ValueError("invalid annotation_quality")
        if vis not in VALID_VISIBILITY: raise ValueError("invalid visibility")
        for key, allowed in (("visible_labels", VALID_V), ("thermal_labels", VALID_T)):
            if not isinstance(a.get(key), list): raise ValueError(f"{key} must be a list")
            for item in a[key]:
                if not isinstance(item, dict) or item.get("class") not in allowed: raise ValueError(f"invalid class in {key}")
                b = item.get("bbox_xyxy")
                if not isinstance(b, list) or len(b) != 4 or any(float(x) < 0 for x in b) or float(b[2]) <= float(b[0]) or float(b[3]) <= float(b[1]): raise ValueError("invalid bbox")
        eid = a.get("fire_event_id")
        if eid is not None and not isinstance(eid, str): raise ValueError("fire_event_id must be string or null")

    def save(self, oid, annotation):
        self.validate_annotation(annotation)
        with self.lock:
            if not self.manifest_path.with_suffix(".json.bak").exists():
                self.manifest_path.with_suffix(".json.bak").write_text(self.manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
            self.by_id[oid]["annotation"] = annotation
            payload = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
            tmp = self.manifest_path.with_suffix(".json.tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self.manifest_path)


class Handler(BaseHTTPRequestHandler):
    app = None
    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args), flush=True)
    def send_json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                raw = HTML.encode("utf-8"); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/index": self.send_json({"ids": self.app.ids, "progress": self.app.progress()}); return
            if u.path == "/api/progress": self.send_json(self.app.progress()); return
            if u.path == "/api/observation":
                oid = parse_qs(u.query).get("id", [""])[0]; self.send_json(self.app.observation(oid)); return
            if u.path == "/api/summary":
                oid = parse_qs(u.query).get("id", [""])[0]; self.send_json(self.app.summary(oid)); return
            if u.path.startswith("/frames/"):
                rel = unquote(u.path[len("/frames/"):]); p = (self.app.frames_root / rel).resolve(); p.relative_to(self.app.frames_root)
                if not p.exists(): raise FileNotFoundError(rel)
                raw = p.read_bytes(); self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Cache-Control", "no-cache"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_error(404)
        except KeyError: self.send_error(404, "unknown observation")
        except Exception as e: self.send_error(400, str(e))
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(n).decode("utf-8"))
            if self.path == "/api/save": self.app.save(body["observation_id"], body["annotation"]); self.send_json({"ok": True}); return
            self.send_error(404)
        except Exception as e: self.send_error(400, str(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--frames-index", type=Path, required=True)
    ap.add_argument("--review-queue", type=Path)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--batch", choices=("B1", "B2", "B3", "B4"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--candidates", type=Path)
    args = ap.parse_args()
    app = App(args.manifest, args.frames_index, args.review_queue, args.batch, args.limit, args.candidates); Handler.app = app
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"url": f"http://{args.host}:{args.port}/", "observations": len(app.ids), "progress": app.progress()}, ensure_ascii=False), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
