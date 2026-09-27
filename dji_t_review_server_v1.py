"""Minimal paired V/T review UI for B4 thermal fire-source/background boxes."""
import argparse
import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


LEGACY_HTML = r'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>B4 热像复核</title><style>
body{margin:0;background:#101923;color:#eef3f7;font:16px system-ui,"Microsoft YaHei",sans-serif}header{padding:12px 18px;background:#203044;display:flex;gap:16px;align-items:center;flex-wrap:wrap}h1{font-size:20px;margin:0}button,select{font:inherit;cursor:pointer;border:0;border-radius:6px;padding:9px 14px}button{background:#386ba0;color:white}button:disabled{opacity:.45;cursor:default}.primary{background:#088a69}.warn{background:#926327}.active{outline:3px solid #fff}main{padding:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.panel{background:#192736;border-radius:8px;padding:10px;min-width:0}.panel h2{font-size:17px;margin:0 0 8px}.imagebox{position:relative;display:inline-block;max-width:100%}.imagebox img{display:block;max-width:100%;max-height:calc(100vh - 260px);object-fit:contain}.imagebox canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}#visible{max-width:100%}.tools{display:flex;gap:9px;align-items:center;flex-wrap:wrap;padding:10px 0}.note{color:#b6c5d4;line-height:1.45}footer{position:sticky;bottom:0;background:#203044;padding:10px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}#msg{margin-left:auto}input[type=checkbox]{width:18px;height:18px}.count{font-weight:bold}.legend{font-size:14px;color:#cbd7e2}@media(max-width:1000px){.grid{grid-template-columns:1fr}.imagebox img{max-height:44vh}}
</style></head><body><header><h1>B4 热像复核</h1><span class="count" id="count">加载中</span><select id="pick"></select><span id="meta"></span></header>
<main><p class="note">左侧可见光仅辅助判断；右侧热像上框出所有与燃烧有关的亮区（明火或原地余热）。高温地面、墙体等非燃烧亮区可用“非火高温”框标出。原有黄框是待检查建议。拿不准就点“无法判断”，该图不进训练。</p>
<div class="tools"><button id="source" class="active">画火源／余热框</button><button id="background" class="warn">画非火高温框</button><button id="undo">撤销上一框</button><button id="clear">清空框</button><span class="legend">黄色＝火源或余热；青色＝非火高温。拖拽画框，点击已有框可删除。</span></div>
<div class="grid"><section class="panel"><h2>可见光 V（判断现场状态）</h2><img id="visible"></section><section class="panel"><h2>热像 T（在此画框）</h2><div class="imagebox"><img id="thermal"><canvas id="canvas"></canvas></div></section></div></main>
<footer><label><input id="checked" type="checkbox"> 已看完整张图；若无火源／余热，允许保持空框</label><button id="prev">上一对</button><button id="save" class="primary">保存并下一对</button><button id="uncertain" class="warn">无法判断并下一对</button><span id="msg"></span></footer>
<script>
let items=[],index=0,boxes=[],mode='source',drag=null,dirty=false,record=null;
const $=id=>document.getElementById(id),canvas=$('canvas'),ctx=canvas.getContext('2d');
function api(path,init){return fetch(path,init).then(async r=>{let d=await r.json();if(!r.ok)throw Error(d.error||r.status);return d})}
function status(msg,ok=true){$('msg').textContent=msg;$('msg').style.color=ok?'#9be9bf':'#ff9c9c'}
function syncCanvas(){canvas.width=$('thermal').naturalWidth;canvas.height=$('thermal').naturalHeight;draw()}
function point(e){let r=canvas.getBoundingClientRect();return [(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height].map(x=>Math.min(1,Math.max(0,x)))}
function draw(){if(!canvas.width)return;ctx.clearRect(0,0,canvas.width,canvas.height);let all=drag?[...boxes,{kind:mode,xyxy:[...drag[0],...drag[1]]}]:boxes;all.forEach((b,i)=>{let [x1,y1,x2,y2]=b.xyxy;ctx.strokeStyle=b.kind==='source'?'#ffcf35':'#19f3d3';ctx.lineWidth=Math.max(2,canvas.width/500);ctx.strokeRect(x1*canvas.width,y1*canvas.height,(x2-x1)*canvas.width,(y2-y1)*canvas.height);ctx.fillStyle=ctx.strokeStyle;ctx.font='bold 20px sans-serif';ctx.fillText((i+1)+' '+(b.kind==='source'?'火源/余热':'非火高温'),x1*canvas.width+2,Math.max(22,y1*canvas.height-3))})}
function choose(m){mode=m;$('source').classList.toggle('active',m==='source');$('background').classList.toggle('active',m==='background')}
async function load(n){if(dirty&&!confirm('本张未保存，确定离开吗？'))return;index=n;record=await api('/api/item?key='+encodeURIComponent(items[index].key));boxes=structuredClone(record.boxes);drag=null;dirty=false;$('checked').checked=false;$('visible').src='/image?key='+encodeURIComponent(record.key)+'&sensor=V';$('thermal').src='/image?key='+encodeURIComponent(record.key)+'&sensor=T';$('thermal').onload=syncCanvas;$('count').textContent=`第 ${index+1} / ${items.length} 对 · 已保存 ${items.filter(x=>x.reviewed).length} 对`;$('meta').textContent=`${record.session_id} · ${record.target_s} 秒 · ${record.kind==='existing'?'已有训练图':'新抽帧'}`;$('pick').value=record.key;status(record.saved?'已保存，可修改并重新保存':'待复核')}
async function save(uncertain){if(!uncertain&&!$('checked').checked){status('请先勾选“已看完整张图”',false);return}try{await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:record.key,outcome:uncertain?'uncertain':'usable',boxes:uncertain?[]:boxes,T_sha256:record.T_sha256,V_sha256:record.V_sha256})});items[index].reviewed=true;dirty=false;status('已保存');if(index<items.length-1)await load(index+1);else $('count').textContent=`32 / 32 · 已保存 ${items.filter(x=>x.reviewed).length} 对`}catch(e){status('保存失败：'+e.message,false)}}
canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);drag=[point(e),point(e)];draw()});canvas.addEventListener('pointermove',e=>{if(drag){drag[1]=point(e);draw()}});canvas.addEventListener('pointerup',e=>{if(!drag)return;let [a,b]=drag;drag=null;let xyxy=[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0]),Math.max(a[1],b[1])];if((xyxy[2]-xyxy[0])*(xyxy[3]-xyxy[1])<0.00005){let hit=boxes.findLastIndex(x=>x.xyxy[0]<=a[0]&&x.xyxy[2]>=a[0]&&x.xyxy[1]<=a[1]&&x.xyxy[3]>=a[1]);if(hit>=0){boxes.splice(hit,1);dirty=true}}else{boxes.push({kind:mode,xyxy});dirty=true}draw()});
$('source').onclick=()=>choose('source');$('background').onclick=()=>choose('background');$('undo').onclick=()=>{boxes.pop();dirty=true;draw()};$('clear').onclick=()=>{boxes=[];dirty=true;draw()};$('prev').onclick=()=>{if(index>0)load(index-1)};$('save').onclick=()=>save(false);$('uncertain').onclick=()=>save(true);$('pick').onchange=e=>load(items.findIndex(x=>x.key===e.target.value));
api('/api/queue').then(d=>{items=d.items;$('pick').innerHTML=items.map(x=>`<option value="${x.key}">${x.reviewed?'✓':'○'} ${x.session_id.slice(-7)} ${x.target_s}s</option>`).join('');load(Math.max(0,items.findIndex(x=>!x.reviewed)))}).catch(e=>status(e.message,false));
</script></body></html>'''

# The reviewer's requested workflow: draw source boxes, or save an empty image.
# Older saved decisions remain readable; initial legacy labels are not prefilled.
HTML = r'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>B4 热像火源复核</title>
<style>body{margin:0;background:#111923;color:#f1f5f9;font:17px system-ui,"Microsoft YaHei",sans-serif}header{background:#203043;padding:12px 18px;display:flex;align-items:center;gap:20px}h1{font-size:21px;margin:0}a{color:#aed2ff;cursor:pointer}main{padding:12px}.hint{margin:0 0 12px;color:#c9d5e2}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.panel{background:#1a2938;padding:10px;border-radius:8px;min-width:0}.panel h2{font-size:17px;margin:0 0 8px}.panel img{display:block;max-width:100%;max-height:calc(100vh - 225px)}.frame{display:inline-block;position:relative;max-width:100%}.frame canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}footer{position:sticky;bottom:0;background:#203043;padding:10px 18px;display:flex;align-items:center;gap:14px}button{border:0;border-radius:7px;background:#078a68;color:white;padding:12px 24px;font:inherit;cursor:pointer}#message{color:#bcdecf}@media(max-width:950px){.grid{grid-template-columns:1fr}.panel img{max-height:42vh}}</style></head>
<body><header><h1>B4 热像火源复核</h1><strong id="progress">加载中</strong><a id="previous">上一对</a><span id="meta"></span></header><main><p class="hint">有火源或原地余热：直接在右侧热像画框，框出全部目标。没有：不画框，直接保存并下一对。画错的框点一下即可删除。左侧可见光供判断。</p><div class="grid"><section class="panel"><h2>可见光 V</h2><img id="visible"></section><section class="panel"><h2>热像 T（在此画框）</h2><div class="frame"><img id="thermal"><canvas id="canvas"></canvas></div></section></div></main><footer><button id="save">保存并下一对</button><span id="message"></span></footer>
<script>
const $=id=>document.getElementById(id);let items=[],index=0,item=null,boxes=[],drag=null,dirty=false;const canvas=$('canvas'),ctx=canvas.getContext('2d');
async function api(path,init){let r=await fetch(path,init),d=await r.json();if(!r.ok)throw Error(d.error||r.status);return d}
function tell(value,error=false){$('message').textContent=value;$('message').style.color=error?'#ff9c9c':'#bcdecf'}
function xy(e){let r=canvas.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]}
function paint(){if(!canvas.width)return;ctx.clearRect(0,0,canvas.width,canvas.height);let all=drag?[...boxes,{kind:'source',xyxy:[Math.min(drag[0][0],drag[1][0]),Math.min(drag[0][1],drag[1][1]),Math.max(drag[0][0],drag[1][0]),Math.max(drag[0][1],drag[1][1])]}]:boxes;for(let i=0;i<all.length;i++){let [x1,y1,x2,y2]=all[i].xyxy;ctx.strokeStyle='#ffcf35';ctx.lineWidth=Math.max(2,canvas.width/500);ctx.strokeRect(x1*canvas.width,y1*canvas.height,(x2-x1)*canvas.width,(y2-y1)*canvas.height);ctx.font='bold 19px sans-serif';ctx.fillStyle='#ffcf35';ctx.fillText('火源 '+(i+1),x1*canvas.width+2,Math.max(21,y1*canvas.height-3))}}
async function load(n){if(n<0||n>=items.length)return;if(dirty&&!confirm('本张未保存，确定返回吗？'))return;index=n;item=await api('/api/item?key='+encodeURIComponent(items[n].key));boxes=(item.boxes||[]).filter(x=>x.kind==='source');drag=null;dirty=false;$('visible').src='/image?key='+encodeURIComponent(item.key)+'&sensor=V';$('thermal').src='/image?key='+encodeURIComponent(item.key)+'&sensor=T';$('thermal').onload=()=>{canvas.width=$('thermal').naturalWidth;canvas.height=$('thermal').naturalHeight;paint()};$('progress').textContent=`第 ${n+1}/${items.length} 对 · 已保存 ${items.filter(x=>x.reviewed).length} 对`;$('meta').textContent=`${item.session_id} · ${item.target_s} 秒`;tell(item.saved?'已保存，可修改':'待复核')}
canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);drag=[xy(e),xy(e)];paint()};canvas.onpointermove=e=>{if(drag){drag[1]=xy(e);paint()}};canvas.onpointerup=e=>{if(!drag)return;let [a,b]=drag;drag=null;let box=[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0]),Math.max(a[1],b[1])];if((box[2]-box[0])*(box[3]-box[1])<0.00005){let hit=boxes.findLastIndex(x=>x.xyxy[0]<=a[0]&&a[0]<=x.xyxy[2]&&x.xyxy[1]<=a[1]&&a[1]<=x.xyxy[3]);if(hit>=0){boxes.splice(hit,1);dirty=true}}else{boxes.push({kind:'source',xyxy:box});dirty=true}paint()};
$('previous').onclick=()=>load(index-1);$('save').onclick=async()=>{try{await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:item.key,outcome:'usable',boxes,T_sha256:item.T_sha256,V_sha256:item.V_sha256})});items[index].reviewed=true;dirty=false;if(index+1<items.length)await load(index+1);else{$('progress').textContent=`已完成 ${items.filter(x=>x.reviewed).length}/${items.length} 对`;tell('全部保存完成')}}catch(e){tell('保存失败：'+e.message,true)}};
api('/api/queue').then(d=>{items=d.items;load(Math.max(0,items.findIndex(x=>!x.reviewed)))}).catch(e=>tell(e.message,true));
</script></body></html>'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_boxes(path):
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 5 or fields[0] != "0":
            raise ValueError("unexpected T label: " + line)
        x, y, w, h = map(float, fields[1:])
        boxes.append({"kind": "source", "xyxy": [x-w/2, y-h/2, x+w/2, y+h/2]})
    return boxes


class Store:
    def __init__(self, root):
        self.root = root.resolve()
        queue = json.loads((self.root / "queue.json").read_text(encoding="utf-8"))
        self.records = {row["key"]: row for row in queue["records"]}
        if len(self.records) != 32:
            raise ValueError("expected 32 unique pairs")
        self.decisions_path = self.root / "decisions.json"
        self.history_path = self.root / "history.jsonl"
        self.lock = threading.Lock()

    def decisions(self):
        return json.loads(self.decisions_path.read_text(encoding="utf-8"))["decisions"]

    def save(self, value):
        if (self.root.parent / "review_frozen_v1.json").exists():
            raise ValueError("复核已冻结，无法再修改")
        key = value.get("key")
        row = self.records.get(key)
        if row is None:
            raise ValueError("unknown image")
        if value.get("T_sha256") != row["T_sha256"] or value.get("V_sha256") != row["V_sha256"]:
            raise ValueError("image hash mismatch")
        outcome = value.get("outcome")
        if outcome not in ("usable", "uncertain"):
            raise ValueError("invalid decision")
        boxes = value.get("boxes")
        if not isinstance(boxes, list) or len(boxes) > 50 or (outcome == "uncertain" and boxes):
            raise ValueError("invalid boxes")
        clean = []
        for box in boxes:
            if box.get("kind") not in ("source", "background"):
                raise ValueError("invalid box kind")
            coords = box.get("xyxy")
            if not isinstance(coords, list) or len(coords) != 4 or not all(
                    isinstance(x, (int, float)) and math.isfinite(x) for x in coords):
                raise ValueError("invalid coordinates")
            x1, y1, x2, y2 = map(float, coords)
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                raise ValueError("out-of-bounds box")
            clean.append({"kind": box["kind"], "xyxy": [x1, y1, x2, y2]})
        decision = {"key": key, "outcome": outcome, "boxes": clean,
                    "T_sha256": row["T_sha256"], "V_sha256": row["V_sha256"],
                    "saved_utc": datetime.now(timezone.utc).isoformat()}
        with self.lock:
            current = self.decisions()
            current[key] = decision
            temp = self.decisions_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps({"decisions": current}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, self.decisions_path)
            with self.history_path.open("a", encoding="utf-8") as history:
                history.write(json.dumps(decision, ensure_ascii=False) + "\n")
        return decision


class Handler(BaseHTTPRequestHandler):
    store = None

    def send_json(self, data, code=200):
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/":
            content = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == "/api/queue":
            saved = self.store.decisions()
            return self.send_json({"items": [{"key": x["key"], "session_id": x["session_id"],
                                                "target_s": x["target_s"], "reviewed": x["key"] in saved}
                                               for x in self.store.records.values()]})
        key = query.get("key", [None])[0]
        row = self.store.records.get(key)
        if row is None:
            return self.send_json({"error": "unknown image"}, 404)
        if parsed.path == "/api/item":
            decision = self.store.decisions().get(key)
            return self.send_json({"key": key, "session_id": row["session_id"],
                                   "target_s": row["target_s"], "kind": row["kind"],
                                   "T_sha256": row["T_sha256"], "V_sha256": row["V_sha256"],
                                   "boxes": decision["boxes"] if decision else [],
                                   "saved": decision is not None, "outcome": decision["outcome"] if decision else None})
        if parsed.path == "/image":
            sensor = query.get("sensor", [None])[0]
            if sensor not in ("V", "T"):
                return self.send_json({"error": "invalid sensor"}, 400)
            image = Path(row[f"{sensor}_image"])
            content = image.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            self.wfile.write(content)
            return
        return self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/save":
            return self.send_json({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 30000:
                raise ValueError("invalid request size")
            value = json.loads(self.rfile.read(length))
            decision = self.store.save(value)
            return self.send_json({"saved": decision["key"]})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            return self.send_json({"error": str(error)}, 400)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--port", type=int, default=8797)
    args = ap.parse_args()
    Handler.store = Store(args.root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"B4 thermal review: http://127.0.0.1:{args.port}/; pairs=32", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
