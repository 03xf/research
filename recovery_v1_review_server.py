"""Review recovery labels without editing the historical source dataset."""

import argparse
import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recovery_v1_prepare import check_label, digest


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DJI 标签复核</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#eef1f2;color:#20272a;font:14px system-ui,"Microsoft YaHei",sans-serif}header{display:flex;align-items:center;gap:10px;padding:10px 16px;background:#fff;border-bottom:1px solid #cbd3d6}h1{font-size:17px;margin:0 15px 0 0}button,select,input,textarea{font:inherit;border:1px solid #a9b8bf;border-radius:4px;background:#fff;color:#20272a;padding:7px}button{cursor:pointer}button:hover{background:#e3eef0}button.primary{background:#176b70;color:#fff;border-color:#176b70}button.primary:hover{background:#10585d}.spacer{flex:1}.layout{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:14px;max-width:1580px;margin:auto;padding:14px}.viewer,.details{min-width:0}.viewer{display:flex;flex-direction:column;gap:8px}.image-stage{position:relative;align-self:flex-start;width:100%;background:#111;min-height:300px}.image-stage img{display:block;width:100%;height:auto}.image-stage canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}.details{display:flex;flex-direction:column;gap:12px}.group{background:#fff;border:1px solid #cbd3d6;padding:12px;border-radius:5px}.group h2{font-size:14px;margin:0 0 9px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}.row input{min-width:0;flex:1}.muted{color:#59676b}.warn{color:#9c4d00}.ok{color:#126042}textarea{display:block;width:100%;height:128px;resize:vertical;font:13px Consolas,monospace;line-height:1.5}#meta{line-height:1.6;overflow-wrap:anywhere}#status{white-space:normal}#recordCounter{font-variant-numeric:tabular-nums}@media(max-width:950px){.layout{grid-template-columns:1fr}.details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){header{flex-wrap:wrap}.details{display:flex}.image-stage{min-height:160px}}
</style></head><body>
<header><h1>DJI 标签复核</h1><button id="prev" title="上一张">←</button><span id="recordCounter"></span><select id="filter"><option value="priority">优先复核</option><option value="all">全部</option><option value="train">训练</option><option value="validation">开发验证</option><option value="pending">待裁决</option></select><span class="spacer"></span><span id="status">加载中</span></header>
<main class="layout"><section class="viewer"><div class="image-stage"><img id="photo" alt="待复核原图"><canvas id="canvas"></canvas></div><div class="muted" id="imageInfo"></div></section><aside class="details"><section class="group"><h2>来源</h2><div id="meta"></div></section><section class="group"><h2>画框</h2><div class="row"><label>类别 <select id="category"></select></label><button id="removeLast" title="撤销最后一个框">↶</button></div><textarea id="labels" spellcheck="false"></textarea><div class="muted">选择类别后在图上拖拽画框。保存时，有框自动记为目标样本；空框自动记为无目标。</div><div id="patch" class="warn"></div></section><section class="group"><h2>保存</h2><div class="row"><button class="primary" id="save">保存当前标注</button><button class="primary" id="saveNext">保存并下一张</button></div><div class="muted">保存只写入新的复核文件，不修改历史标签。</div></section></aside></main>
<script>
const $=id=>document.getElementById(id);let keys=[],index=0,item=null,drag=null,dirty=false;const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,options){let r=await fetch(url,options);if(!r.ok)throw Error(await r.text());return r.json()}
function setStatus(message,good=false){$('status').textContent=message;$('status').className=good?'ok':'warn'}
function lines(){return $('labels').value.split('\n').map(s=>s.trim()).filter(Boolean)}
function draw(){const img=$('photo'),c=$('canvas');if(!img.naturalWidth)return;const w=img.clientWidth,h=img.clientHeight,d=devicePixelRatio||1;c.width=Math.round(w*d);c.height=Math.round(h*d);let g=c.getContext('2d');g.scale(d,d);g.clearRect(0,0,w,h);g.lineWidth=2;g.font='14px system-ui';lines().forEach((line,i)=>{let a=line.split(/\s+/).map(Number);if(a.length!==5||a.some(v=>!Number.isFinite(v)))return;let [cls,x,y,bw,bh]=a;let px=(x-bw/2)*w,py=(y-bh/2)*h;g.strokeStyle=cls===0?'#1df0d3':'#ffca35';g.fillStyle=g.strokeStyle;g.strokeRect(px,py,bw*w,bh*h);g.fillText(String(i+1),px+3,Math.max(16,py-3))})}
function framePoint(event){let rect=$('canvas').getBoundingClientRect();return {x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))}}
$('canvas').onpointerdown=e=>{drag=framePoint(e);$('canvas').setPointerCapture(e.pointerId)};
$('canvas').onpointerup=e=>{if(!drag)return;let b=framePoint(e),x1=Math.min(drag.x,b.x),y1=Math.min(drag.y,b.y),x2=Math.max(drag.x,b.x),y2=Math.max(drag.y,b.y);drag=null;if(x2-x1<.005||y2-y1<.005)return;let line=`${$('category').value} ${((x1+x2)/2).toFixed(8)} ${((y1+y2)/2).toFixed(8)} ${(x2-x1).toFixed(8)} ${(y2-y1).toFixed(8)}`;$('labels').value=[$('labels').value.trim(),line].filter(Boolean).join('\n');dirty=true;draw()};
async function reloadKeys(){let data=await api('/api/list?filter='+encodeURIComponent($('filter').value));keys=data.keys;if(index>=keys.length)index=0;await load(index)}
async function load(i){if(dirty&&!confirm('当前修改未保存，继续切换？'))return;if(!keys.length){setStatus('没有符合条件的样本');return}index=Math.max(0,Math.min(keys.length-1,i));let data=await api('/api/item?key='+encodeURIComponent(keys[index]));item=data.record;$('recordCounter').textContent=`${index+1} / ${keys.length}`;$('meta').innerHTML=`<b>${esc(item.observation_id)} / ${esc(item.sensor)} / ${esc(item.split)}</b><br>${esc(item.session_id)}<br>${esc(item.video_group)}<br>${esc(item.timestamp_s)} 秒<br>初筛：${esc(item.review_status)}<br>图像 SHA256：${esc(item.image_sha256)}`;$('imageInfo').textContent=`${item.image_size.join(' × ')} · ${item.observation_id} · ${item.sensor}`;$('patch').textContent=item.proposed_patch?'已有单框补丁（仅供参考，必须检查全图其他目标）：'+item.proposed_patch:'';$('category').innerHTML=(item.sensor==='V'?['smoke','flame']:['hotspot']).map((name,j)=>`<option value="${j}">${j} ${name}</option>`).join('');$('labels').value=data.decision?.label_text??data.original_label;$('photo').src='/api/image?key='+encodeURIComponent(keys[index]);$('photo').onload=draw;dirty=false;setStatus(data.decision?'已保存':'等待画框',!!data.decision)}
async function save(){if(!item)return;let labelText=$('labels').value.trim();let payload={key:keys[index],status:labelText?'approved_complete':'confirmed_negative',label_text:labelText};try{await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});dirty=false;setStatus('已保存到服务器',true)}catch(error){setStatus('保存失败：'+error.message)}}
async function saveNext(){await save();if(!dirty&&index<keys.length-1)await load(index+1)}
$('prev').onclick=()=>load(index-1);$('filter').onchange=()=>{index=0;reloadKeys().catch(e=>setStatus(e.message))};$('save').onclick=save;$('saveNext').onclick=saveNext;$('removeLast').onclick=()=>{$('labels').value=lines().slice(0,-1).join('\n');dirty=true;draw()};$('labels').oninput=()=>{dirty=true;draw()};window.onresize=draw;reloadKeys().catch(e=>setStatus(e.message));
</script></body></html>'''


class Review:
    def __init__(self, root):
        self.root = root.resolve()
        self.ledger = json.loads((root / "sample_ledger.json").read_text(encoding="utf-8"))["records"]
        self.by_key = {f"{row['sensor']}:{row['split']}:{row['observation_id']}": row for row in self.ledger}
        if len(self.by_key) != len(self.ledger):
            raise ValueError("duplicate sample key")
        self.decisions_path = root / "review_decisions.json"
        self.lock = threading.RLock()

    def decisions(self):
        data = json.loads(self.decisions_path.read_text(encoding="utf-8"))
        return {row["key"]: row for row in data["decisions"]}

    def keys(self, filter_name):
        decisions = self.decisions()
        if filter_name == "priority":
            selected = [k for k, r in self.by_key.items() if r["review_status"] != "legacy_positive_pending_full_image_review"]
        elif filter_name == "pending":
            selected = [k for k in self.by_key if k not in decisions or decisions[k]["status"] in ("pending", "needs_revision")]
        elif filter_name in ("train", "validation"):
            selected = [k for k, r in self.by_key.items() if r["split"] == filter_name]
        elif filter_name == "all":
            selected = list(self.by_key)
        else:
            raise ValueError("unknown filter")
        return sorted(selected, key=lambda k: (self.by_key[k]["split"] != "train", self.by_key[k]["review_status"] == "legacy_positive_pending_full_image_review", self.by_key[k]["session_id"] or "", k))

    def item(self, key):
        row = self.by_key[key]
        decisions = self.decisions()
        return {"record": row, "original_label": Path(row["label"]).read_text(encoding="utf-8"),
                "decision": decisions.get(key)}

    def save(self, value):
        key = value["key"]
        row = self.by_key[key]
        status = value["status"]
        if status not in ("pending", "approved_complete", "confirmed_negative", "needs_revision", "exclude"):
            raise ValueError("invalid status")
        if digest(Path(row["image"])) != row["image_sha256"] or digest(Path(row["label"])) != row["label_sha256"]:
            raise ValueError("source changed since ledger creation")
        label_text = value.get("label_text", "").strip()
        counts = check_label(label_text, 2 if row["sensor"] == "V" else 1)
        if status == "approved_complete" and not counts:
            raise ValueError("positive approval needs at least one box")
        if status == "confirmed_negative" and counts:
            raise ValueError("negative approval needs an empty label")
        decision = {"key": key, "status": status, "label_text": label_text,
                    "source_image_sha256": row["image_sha256"], "source_label_sha256": row["label_sha256"],
                    "reviewed_utc": datetime.now(timezone.utc).isoformat()}
        with self.lock:
            data = json.loads(self.decisions_path.read_text(encoding="utf-8"))
            existing = {entry["key"]: entry for entry in data["decisions"]}
            existing[key] = decision
            data["decisions"] = sorted(existing.values(), key=lambda entry: entry["key"])
            temp = self.decisions_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, self.decisions_path)
            with (self.root / "review_history.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(decision, ensure_ascii=False) + "\n")
        return decision


class Handler(BaseHTTPRequestHandler):
    review = None

    def send_bytes(self, payload, kind="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, value, status=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"), status=status)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            if url.path == "/":
                self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif url.path == "/api/list":
                self.send_json({"keys": self.review.keys(query.get("filter", ["priority"])[0])})
            elif url.path == "/api/item":
                self.send_json(self.review.item(query["key"][0]))
            elif url.path == "/api/image":
                self.send_bytes(Path(self.review.by_key[query["key"][0]]["image"]).read_bytes(), "image/jpeg")
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
            value = json.loads(self.rfile.read(size).decode("utf-8"))
            self.send_json(self.review.save(value))
        except (KeyError, ValueError, TypeError) as error:
            self.send_error(400, str(error))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()
    Handler.review = Review(args.root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Review UI: http://127.0.0.1:{args.port}/; samples={len(Handler.review.ledger)}", flush=True)
    server.serve_forever()
