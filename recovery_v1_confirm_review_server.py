"""Serve paired V/T confirmation images and persist independent review labels."""

import argparse
import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recovery_v1_prepare import check_label, digest


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DJI 确认集成对复核</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#e9eef0;color:#20272a;font:14px system-ui,"Microsoft YaHei",sans-serif}header{display:flex;gap:10px;align-items:center;padding:9px 14px;background:#fff;border-bottom:1px solid #bbc8cd}h1{font-size:17px;margin:0 12px 0 0}button,select,textarea{font:inherit;border:1px solid #a9b8bf;border-radius:4px;background:white;padding:7px;color:#20272a}button{cursor:pointer}button:hover{background:#e3eef0}.primary{background:#176b70;color:white;border-color:#176b70}.spacer{flex:1}.info{font-size:12px;color:#53666c}.layout{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}.panel{background:white;border:1px solid #bbc8cd;border-radius:5px;padding:10px;min-width:0}.panel h2{margin:0 0 8px;font-size:16px}.stage{position:relative;width:100%;background:#111;min-height:200px}.stage img{display:block;width:100%;height:auto}.stage canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}.controls{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:8px 0}textarea{width:100%;height:70px;font:12px Consolas,monospace}.bottom{display:flex;gap:8px;align-items:center;padding:10px 12px;background:white;position:sticky;bottom:0;border-top:1px solid #bbc8cd}.warning{color:#a34f00}@media(max-width:900px){.layout{grid-template-columns:1fr}}
</style></head><body>
<header><h1>DJI 确认集成对复核</h1><button id="prev">← 上一对</button><span id="counter"></span><span class="spacer"></span><span id="meta" class="info"></span></header>
<main class="layout">
<section class="panel"><h2>V 可见光：烟雾 / 火焰</h2><div class="stage"><img id="Vimg" alt="V 原图"><canvas id="Vcanvas"></canvas></div><div class="controls"><select id="Vclass"><option value="0">smoke 烟雾</option><option value="1">flame 火焰</option></select><button id="Vundo">撤销最后框</button><label><input id="Vuncertain" type="checkbox"> 无法判断</label><span id="Vpts" class="info"></span></div><textarea id="Vlabels" spellcheck="false"></textarea></section>
<section class="panel"><h2>T 热成像：燃烧热点</h2><div class="stage"><img id="Timg" alt="T 原图"><canvas id="Tcanvas"></canvas></div><div class="controls"><button id="Tundo">撤销最后框</button><label><input id="Tuncertain" type="checkbox"> 无法判断</label><span id="Tpts" class="info"></span></div><textarea id="Tlabels" spellcheck="false"></textarea><div class="warning">高温地面、墙体、设备表面不等于燃烧热点。只标有可靠燃烧证据的局部热点；不确定时勾选“无法判断”。</div></section>
</main><div class="bottom"><button id="save">保存当前对</button><button class="primary" id="saveNext">保存并下一对 →</button><span id="status" class="info"></span><span class="spacer"></span><span class="info">有框表示确认目标；无框且未勾存疑表示确认无目标。</span></div>
<script>
const $=x=>document.getElementById(x);let pairs=[],i=0,current=null,dirty=false;
async function api(url,options){let r=await fetch(url,options);if(!r.ok)throw Error(await r.text());return r.json()}
function lines(s){return $(s+'labels').value.split('\n').map(x=>x.trim()).filter(Boolean)}
function draw(s){let img=$(s+'img'),c=$(s+'canvas');if(!img.naturalWidth)return;let w=img.clientWidth,h=img.clientHeight,d=devicePixelRatio||1;c.width=Math.round(w*d);c.height=Math.round(h*d);let g=c.getContext('2d');g.scale(d,d);g.clearRect(0,0,w,h);g.lineWidth=2;g.font='14px system-ui';for(let [j,line] of lines(s).entries()){let a=line.split(/\s+/).map(Number);if(a.length!==5||a.some(x=>!Number.isFinite(x)))continue;let [cls,x,y,bw,bh]=a;let px=(x-bw/2)*w,py=(y-bh/2)*h;g.strokeStyle=s==='T'?'#ff4757':cls===0?'#16e0da':'#ffc83d';g.fillStyle=g.strokeStyle;g.strokeRect(px,py,bw*w,bh*h);g.fillText(''+(j+1),px+3,Math.max(16,py-3))}}
function point(s,e){let r=$(s+'canvas').getBoundingClientRect();return {x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))}}
for(let s of ['V','T']){let start=null,c=$(s+'canvas');c.onpointerdown=e=>{start=point(s,e);c.setPointerCapture(e.pointerId)};c.onpointerup=e=>{if(!start)return;let b=point(s,e),x1=Math.min(start.x,b.x),x2=Math.max(start.x,b.x),y1=Math.min(start.y,b.y),y2=Math.max(start.y,b.y);start=null;if(x2-x1<.005||y2-y1<.005)return;let cls=s==='T'?0:Number($('Vclass').value);let line=[cls,(x1+x2)/2,(y1+y2)/2,x2-x1,y2-y1].map((v,k)=>k?Number(v).toFixed(8):v).join(' ');$(s+'labels').value=[...lines(s),line].join('\n');dirty=true;draw(s)};$(s+'labels').oninput=()=>{dirty=true;draw(s)};$(s+'uncertain').onchange=()=>{dirty=true};$(s+'undo').onclick=()=>{$(s+'labels').value=lines(s).slice(0,-1).join('\n');dirty=true;draw(s)}}
async function load(index){if(dirty&&!confirm('修改尚未保存，仍要切换？'))return;i=Math.max(0,Math.min(pairs.length-1,index));current=await api('/api/item?id='+encodeURIComponent(pairs[i]));$('counter').textContent=(i+1)+' / '+pairs.length;$('meta').textContent=current.session_id+' · '+current.pair_id+' · Δ '+(current.delta_s*1000).toFixed(1)+' ms';for(let s of ['V','T']){$(s+'labels').value=current.decision?.[s]?.label_text??'';$(s+'uncertain').checked=current.decision?.[s]?.status==='uncertain';$(s+'pts').textContent='PTS '+current[s].pts_s.toFixed(3)+' s';$(s+'img').src='/api/image?id='+encodeURIComponent(current.pair_id)+'&sensor='+s;$(s+'img').onload=()=>draw(s)}dirty=false;$('status').textContent=current.decision?'已保存':'待复核'}
async function save(){if(!current)return false;let payload={pair_id:current.pair_id,V:{status:$('Vuncertain').checked?'uncertain':'complete',label_text:$('Vlabels').value.trim()},T:{status:$('Tuncertain').checked?'uncertain':'complete',label_text:$('Tlabels').value.trim()}};try{await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});dirty=false;$('status').textContent='已保存到服务器';return true}catch(e){$('status').textContent='保存失败：'+e.message;return false}}
$('save').onclick=save;$('saveNext').onclick=async()=>{if(await save()&&i<pairs.length-1)await load(i+1)};$('prev').onclick=()=>load(i-1);window.onresize=()=>{draw('V');draw('T')};api('/api/list').then(x=>{pairs=x.pairs;i=x.first_pending_index;return load(i)}).catch(e=>$('status').textContent=e.message);
</script></body></html>'''


class Review:
    def __init__(self, root):
        self.root = root.resolve()
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.pairs = self.manifest["pairs"]
        self.by_id = {p["pair_id"]: p for p in self.pairs}
        if len(self.by_id) != len(self.pairs):
            raise ValueError("duplicate pair id")
        self.decisions_path = root / "decisions.json"
        self.lock = threading.RLock()

    def decisions(self):
        return json.loads(self.decisions_path.read_text(encoding="utf-8"))["decisions"]

    def listing(self):
        decisions = self.decisions()
        pending = next((i for i, p in enumerate(self.pairs) if p["pair_id"] not in decisions), 0)
        return {"pairs": [p["pair_id"] for p in self.pairs], "first_pending_index": pending,
                "complete": len(decisions), "total": len(self.pairs)}

    def item(self, pair_id):
        pair = self.by_id[pair_id]
        return {**pair, "decision": self.decisions().get(pair_id)}

    def image(self, pair_id, sensor):
        if sensor not in ("V", "T"):
            raise ValueError("invalid sensor")
        row = self.by_id[pair_id][sensor]
        image = Path(row["file"])
        if digest(image) != row["sha256"]:
            raise ValueError("image hash changed")
        return image.read_bytes()

    def save(self, payload):
        pair_id = payload["pair_id"]
        pair = self.by_id[pair_id]
        result = {"pair_id": pair_id, "saved_utc": datetime.now(timezone.utc).isoformat()}
        for sensor, count in (("V", 2), ("T", 1)):
            value = payload[sensor]
            status = value["status"]
            if status not in ("complete", "uncertain"):
                raise ValueError("invalid status")
            label = value["label_text"].strip()
            check_label(label, count)
            if status == "uncertain" and label:
                raise ValueError("uncertain images cannot contain committed boxes")
            if digest(Path(pair[sensor]["file"])) != pair[sensor]["sha256"]:
                raise ValueError("image hash changed")
            result[sensor] = {"status": status, "label_text": label, "image_sha256": pair[sensor]["sha256"]}
        with self.lock:
            data = json.loads(self.decisions_path.read_text(encoding="utf-8"))
            data["decisions"][pair_id] = result
            temp = self.decisions_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, self.decisions_path)
            with (self.root / "review_history.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
        return result


class Handler(BaseHTTPRequestHandler):
    review = None

    def send_bytes(self, value, content_type="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(value)

    def send_json(self, value):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            if url.path == "/":
                self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif url.path == "/api/list":
                self.send_json(self.review.listing())
            elif url.path == "/api/item":
                self.send_json(self.review.item(query["id"][0]))
            elif url.path == "/api/image":
                self.send_bytes(self.review.image(query["id"][0], query["sensor"][0]), "image/jpeg")
            else:
                self.send_error(404)
        except (KeyError, ValueError, FileNotFoundError) as error:
            self.send_error(400, str(error))

    def do_POST(self):
        try:
            if self.path != "/api/save":
                self.send_error(404)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 100000:
                raise ValueError("invalid request size")
            self.send_json(self.review.save(json.loads(self.rfile.read(size).decode("utf-8"))))
        except (KeyError, ValueError, TypeError) as error:
            self.send_error(400, str(error))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8781)
    args = parser.parse_args()
    Handler.review = Review(args.root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Confirmation pair review: http://127.0.0.1:{args.port}/; pairs={len(Handler.review.pairs)}", flush=True)
    server.serve_forever()
