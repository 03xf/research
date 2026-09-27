"""Dual-GPU V/T replay and local live-view prototype for frozen DJI E2 models.

Inputs are decoded PTS clip directories made by recovery_v1_extract_custom_clip.py.
The worker API also accepts live V/T capture URLs. Live stream pairing is based
on arrival time and is explicitly marked as such.
"""
import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import os
import queue
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dji_temporal_rules_v1 import TemporalFilter


HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DJI 火源实时跟踪</title>
<style>body{margin:0;background:#edf1f2;color:#17262a;font:15px system-ui,"Microsoft YaHei",sans-serif}header{padding:12px 18px;background:#fff;border-bottom:1px solid #bccbd0;display:flex;gap:24px;align-items:center}h1{font-size:20px;margin:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}.card{background:#fff;border:1px solid #bccbd0;border-radius:6px;padding:10px;min-width:0}.card h2{margin:0 0 8px;font-size:17px}.card img{display:block;width:100%;min-height:200px;background:#111}.stat{padding:8px 12px;background:#fff;margin:0 12px 12px;border-radius:6px}.pill{display:inline-block;padding:2px 7px;margin-right:4px;border-radius:4px;background:#dce9eb}.warn{background:#ffe9cb}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:5px;border-bottom:1px solid #ddd;text-align:left}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style></head><body>
<header><h1>DJI 火源实时跟踪</h1><span id="run">等待数据</span><span id="pair"></span></header>
<div class="grid"><section class="card"><h2>可见光 V</h2><img id="V" alt="可见光视频"><video id="Vvideo" controls style="display:none;width:100%"></video><div id="Vstat"></div><div id="Vtracks"></div></section><section class="card"><h2>热成像 T</h2><img id="T" alt="热成像视频"><video id="Tvideo" controls style="display:none;width:100%"></video><div id="Tstat"></div><div id="Ttracks"></div></section></div>
<section class="stat"><h2>位置与性能</h2><div id="location"></div><div id="perf"></div><p>位置表是批次候选集合。未确认轨迹与物理火源对应时，单条轨迹的位置为“未确定”。“预测保持”使用上次检测框，最多持续 0.6 秒。</p></section>
<script>
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function table(xs){if(!xs?.length)return '当前无火源候选';return '<table><tr><th>轨迹</th><th>类别</th><th>状态</th><th>置信度</th><th>位置</th></tr>'+xs.map(x=>'<tr><td>'+esc(x.track_id||'未分配')+'</td><td>'+esc(({flame:'火焰',hotspot:'热点'})[x.class_name]||x.class_name)+'</td><td>'+esc(x.state_zh)+'</td><td>'+esc(x.confidence?.toFixed?.(2)||'')+'</td><td>'+esc(x.coordinate_status_zh||'未确定')+'</td></tr>').join('')+'</table>'}
const displayedSeq={V:0,T:0},loading={V:false,T:false},currentUrl={V:null,T:null},clientLatencies=[];
function p95(xs){if(!xs.length)return null;let s=[...xs].sort((a,b)=>a-b);return s[Math.floor(.95*(s.length-1))]}
function renderSensor(sensor,x){document.getElementById(sensor+'stat').textContent='时间 '+(x.pts_s?.toFixed?.(3)??'—')+' 秒 · 帧率 '+(x.fps?.toFixed?.(2)??'—')+' · 服务器延迟 '+(x.latency_ms?.toFixed?.(0)??'—')+' 毫秒 · 丢帧 '+(x.dropped||0);document.getElementById(sensor+'tracks').innerHTML=table(x.tracks)}
async function loadFrame(sensor,x,offset){
  if(loading[sensor]||x.frame_seq<=displayedSeq[sensor])return;
  loading[sensor]=true;
  let url=null;
  try{
    let r=await fetch('/api/frame/'+sensor+'?n='+x.frame_seq,{cache:'no-store'});
    if(!r.ok)throw new Error('frame HTTP '+r.status);
    url=URL.createObjectURL(await r.blob());
    let im=document.getElementById(sensor);
    await new Promise((resolve,reject)=>{im.onload=resolve;im.onerror=reject;im.src=url});
    if(currentUrl[sensor])URL.revokeObjectURL(currentUrl[sensor]);
    currentUrl[sensor]=url;url=null;
    displayedSeq[sensor]=x.frame_seq;
    renderSensor(sensor,x);
    let ms=Date.now()-x.source_wall_ms-offset;
    if(ms>=0&&ms<5000)clientLatencies.push(ms);
  }catch(e){document.getElementById(sensor+'stat').textContent='画面加载失败：'+e.message}
  finally{if(url)URL.revokeObjectURL(url);loading[sensor]=false}
}
async function tick(){
  try{
    let t0=Date.now(),r=await fetch('/api/state',{cache:'no-store'}),s=await r.json(),t1=Date.now();
    let clockOffset=(t0+t1)/2-s.server_wall_ms;
    document.getElementById('run').textContent='运行状态：'+s.run_status_zh;
    document.getElementById('pair').textContent='已配对 '+s.paired_count+' 对；未配对 V '+s.unpaired_V+' / T '+s.unpaired_T;
    for(let sensor of ['V','T']){
      let x=s.sensors[sensor]||{};
      if(s.run_status_zh==='完成'){
        let v=document.getElementById(sensor+'video');
        if(!v.src){v.src='/api/video/'+sensor;v.style.display='block';document.getElementById(sensor).style.display='none'}
      }else if(x.frame_seq&&x.source_wall_ms)loadFrame(sensor,x,clockOffset);
    }
    document.getElementById('location').innerHTML='<b>批次候选坐标：</b> '+((s.coordinate_candidates||[]).map(x=>esc(x.point_id)+' ('+esc(x.latitude)+', '+esc(x.longitude)+') ['+esc(({reference_confirmed:'激光参考',prefire_reference:'放火前参考',provisional_visual:'影像近似候选',candidate_only:'未定候选'})[x.status]||x.status)+']').join('；')||'无');
    document.getElementById('perf').textContent='时间配对方式：'+s.pairing_method_zh+'；最近时间差 '+(s.last_pair_delta_ms?.toFixed?.(1)??'—')+' 毫秒；服务器第95百分位延迟 '+(s.latency_p95_ms?.toFixed?.(0)??'—')+' 毫秒；本浏览器显示第95百分位 '+(p95(clientLatencies)?.toFixed?.(0)??'—')+' 毫秒（'+clientLatencies.length+' 帧）。网页每100毫秒刷新。'
  }catch(e){document.getElementById('run').textContent='连接中断：'+e.message}
  setTimeout(tick,100)
}
tick();
</script></body></html>'''


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def percentile(values,p):
    if not values:return None
    s=sorted(values);return s[max(0,min(len(s)-1,int((len(s)-1)*p)))]


def annotate(image,detections,tracks,sensor,pts):
    import cv2
    colors={'V':(0,160,255),'T':(40,70,235)}
    color=colors[sensor]
    stable_ids={t['track_id']:t for t in tracks}
    for d in detections:
        x1,y1,x2,y2=map(round,d['bbox_xyxy_px']);tid=d.get('track_id')
        state=stable_ids.get(tid,{}).get('state','unconfirmed')
        cv2.rectangle(image,(x1,y1),(x2,y2),color,2)
        cv2.putText(image,f"{tid or '-'} {state} {d['confidence']:.2f}",(x1,max(18,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.48,color,2)
        point=d.get('source_point_image_normalized')
        if point:
            h,w=image.shape[:2];cv2.circle(image,(round(point[0]*w),round(point[1]*h)),5,(0,255,255),-1)
    for t in tracks:
        if t['state']!='predicted_hold':continue
        x1,y1,x2,y2=map(round,t['bbox_xyxy_px']);cv2.rectangle(image,(x1,y1),(x2,y2),(120,120,120),1)
        cv2.putText(image,f"{t['track_id']} HOLD",(x1,max(18,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1)
    cv2.putText(image,f"{sensor} PTS {pts:.3f}s",(15,image.shape[0]-18),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
    return image


def worker(sensor,source,mode,weights,weight_hash,threshold,tracker,imgsz,device,output,base_pts,start_clock,start_event,result_queue,stop_event):
    os.environ['WANDB_MODE']='disabled';os.environ['WANDB_DISABLED']='true';os.environ['COMET_MODE']='DISABLED'
    os.environ['CUDA_VISIBLE_DEVICES']=str(device)
    sys.path.insert(0,'/home/member/xmy/xmy/code/projects/ultralytics')
    import cv2
    from ultralytics import YOLO
    try:
        if sha(Path(weights))!=weight_hash:raise ValueError('frozen weight hash mismatch '+sensor)
        model=YOLO(str(weights))
        for module in model.model.modules():
            if type(module).__name__=='GELU' and not hasattr(module,'approximate'):module.approximate='none'
        if mode=='clip':
            warm_rows=json.loads((Path(source)/'frames.json').read_text(encoding='utf-8'))
            warm=cv2.imread(str(Path(source)/warm_rows[0]['frame_file']))
            if warm is None:raise RuntimeError('warmup frame unreadable '+sensor)
            model.predict(source=warm,conf=threshold,imgsz=imgsz,device='0',classes=[1 if sensor=='V' else 0],verbose=False,save=False)
        filt=TemporalFilter(sensor)
        cls=1 if sensor=='V' else 0
        class_name='flame' if sensor=='V' else 'hotspot'
        writer=None;processed=0;dropped=0;last_emit=None
        if mode=='clip':
            frames=json.loads((Path(source)/'frames.json').read_text(encoding='utf-8'))
            iterator=((x['decoded_pts_s'],cv2.imread(str(Path(source)/x['frame_file']))) for x in frames)
        else:
            cap=cv2.VideoCapture(source)
            if not cap.isOpened():raise RuntimeError('cannot open live stream '+sensor)
            def stream_frames():
                last=0
                while not stop_event.is_set():
                    ok,frame=cap.read()
                    if not ok:break
                    now=time.monotonic()
                    if now-last<0.19:
                        continue
                    last=now
                    yield now,frame
            iterator=stream_frames()
        result_queue.put({'type':'ready','sensor':sensor})
        start_event.wait()
        for pts,image in iterator:
            if stop_event.is_set():break
            if image is None:raise RuntimeError('unreadable frame '+sensor)
            if mode=='clip':
                target=start_clock.value+(pts-base_pts)
                remain=target-time.monotonic()
                if remain>0:time.sleep(remain)
                elif remain<-0.50:
                    dropped+=1
                    continue
            else:
                target=pts
                pts=pts-start_clock.value
            started=time.monotonic()
            result=model.track(source=image,persist=True,tracker=str(tracker),conf=threshold,iou=.7,
                               imgsz=imgsz,device='0',classes=[cls],max_det=300,verbose=False,save=False)[0]
            boxes=result.boxes;xy=boxes.xyxy.cpu().tolist();confs=boxes.conf.cpu().tolist()
            ids=boxes.id.cpu().tolist() if boxes.id is not None else [None]*len(xy)
            h,w=image.shape[:2];detections=[]
            for box,conf,track_id in zip(xy,confs,ids):
                x1,y1,x2,y2=box
                detections.append({'class_name':class_name,'confidence':conf,
                    'track_id':f'{sensor}_{class_name}_{int(track_id)}' if track_id is not None else None,
                    'bbox_xyxy_px':box,
                    'source_point_image_normalized':[((x1+x2)/2)/w,y2/h] if sensor=='V' else None})
            tracks=filt.update(pts,detections)
            for t in tracks:
                labels=({'stable_candidate':'稳定候选','unconfirmed':'待确认候选','predicted_hold':'预测保持'} if sensor=='V' else
                        {'stable_candidate':'热像候选（稳定）','unconfirmed':'热像候选（待确认）','predicted_hold':'热像候选（预测保持）'})
                t['state_zh']=labels[t['state']]
                t['coordinate_status_zh']='未确定'
            frame=annotate(image,detections,tracks,sensor,pts)
            if writer is None:
                writer=cv2.VideoWriter(str(output/sensor/'tracked.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),5.0,(w,h))
                if not writer.isOpened():raise RuntimeError('video writer failed '+sensor)
            writer.write(frame)
            preview=cv2.resize(frame,(960,round(frame.shape[0]*960/frame.shape[1]))) if frame.shape[1]>960 else frame
            ok,jpeg=cv2.imencode('.jpg',preview,[cv2.IMWRITE_JPEG_QUALITY,60])
            if not ok:raise RuntimeError('jpeg encoding failed')
            ended=time.monotonic();processed+=1
            fps=1/(ended-last_emit) if last_emit is not None and ended>last_emit else None;last_emit=ended
            event={'type':'frame','sensor':sensor,'frame_seq':processed,'pts_s':pts,'raw_detections':detections,
                   'tracks':tracks,'jpeg':jpeg.tobytes(),'inference_latency_ms':(ended-started)*1000,
                   'source_monotonic':target,
                   'source_wall_ms':time.time()*1000-(time.monotonic()-target)*1000,
                   'fps':fps,'dropped':dropped,'timestamp_utc':datetime.now(timezone.utc).isoformat()}
            result_queue.put(event)
        if writer:writer.release()
        result_queue.put({'type':'done','sensor':sensor,'processed':processed,'dropped':dropped})
    except BaseException as exc:
        result_queue.put({'type':'error','sensor':sensor,'error':repr(exc)})


class View:
    def __init__(self,candidates,pairing):
        self.lock=threading.Lock();self.jpeg={'V':None,'T':None}
        self.frame_cache={'V':OrderedDict(),'T':OrderedDict()}
        self.state={'run_status_zh':'启动中','sensors':{'V':{},'T':{}},'paired_count':0,'unpaired_V':0,'unpaired_T':0,
                    'pairing_method_zh':pairing,'last_pair_delta_ms':None,'latency_p95_ms':None,
                    'coordinate_candidates':candidates}


class Handler(BaseHTTPRequestHandler):
    view=None
    output_dir=None
    def send(self,data,ctype):
        self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        parsed=urlparse(self.path);path=parsed.path
        if path=='/':self.send(HTML.encode(),'text/html; charset=utf-8');return
        if path.startswith('/api/video/'):
            sensor=path.rsplit('/',1)[-1]
            if sensor not in ('V','T'):self.send_error(404);return
            file=self.output_dir/sensor/'tracked_browser.mp4'
            if not file.is_file():self.send_error(404);return
            size=file.stat().st_size;range_header=self.headers.get('Range')
            start=0;end=size-1;partial=False
            if range_header and range_header.startswith('bytes='):
                try:
                    a,b=range_header[6:].split('-',1);start=int(a) if a else 0;end=int(b) if b else end
                    if start<0 or end>=size or end<start:raise ValueError()
                    partial=True
                except ValueError:self.send_error(416);return
            self.send_response(206 if partial else 200)
            self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
            self.send_header('Content-Length',str(end-start+1))
            if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            with file.open('rb') as f:
                f.seek(start);remaining=end-start+1
                while remaining:
                    block=f.read(min(1024*1024,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)
            return
        with self.view.lock:
            if path=='/api/state':
                state=dict(self.view.state);state['server_wall_ms']=time.time()*1000
                self.send(json.dumps(state,ensure_ascii=False).encode(),'application/json; charset=utf-8');return
            if path.startswith('/api/frame/'):
                sensor=path.rsplit('/',1)[-1]
                seq=parse_qs(parsed.query).get('n',[None])[0]
                data=(self.view.frame_cache.get(sensor,{}).get(int(seq)) if seq is not None and seq.isdecimal()
                      else self.view.jpeg.get(sensor))
                if data:self.send(data,'image/jpeg');return
        self.send_error(404)
    def log_message(self,*args):pass


def candidates(inventory,batch):
    with inventory.open(encoding='utf-8-sig',newline='') as f:
        return [{k:r[k] for k in ('point_id','latitude','longitude','status')} for r in csv.DictReader(f) if r['batch_id']==batch]


def run(args):
    root=args.root;clip=args.clip
    out=args.output
    if out.exists():raise FileExistsError(out)
    if clip is None and args.visible and args.thermal and Path(args.visible).is_file() and Path(args.thermal).is_file():
        out.mkdir(parents=True)
        clip=out/'decoded_input'
        command=[sys.executable,'/home/member/xmy/xmy/code/tools/recovery_v1_extract_custom_clip.py',
                 '--visible',args.visible,'--thermal',args.thermal,'--start',str(args.start_s),
                 '--duration',str(args.duration_s),'--output',str(clip),
                 '--batch',args.batch or 'unknown','--session',args.session or 'unknown',
                 '--video-group',args.video_group or 'recorded_pair']
        subprocess.run(command,check=True)
    manifest=json.loads((clip/'manifest.json').read_text(encoding='utf-8')) if clip else None
    mode='clip' if clip else 'stream'
    if clip:
        if not manifest['paired_frames']:raise ValueError('clip has no pairs')
        batch=manifest['source']['batch_id']
        base_pts=min(json.loads((clip/s/'frames.json').read_text(encoding='utf-8'))[0]['decoded_pts_s'] for s in ('V','T'))
        sources={s:str(clip/s) for s in ('V','T')}
    else:
        if not args.visible or not args.thermal:raise ValueError('streams require --visible and --thermal')
        batch=args.batch or 'unknown';base_pts=0;sources={'V':args.visible,'T':args.thermal}
    for s in ('V','T'):(out/s).mkdir(parents=True)
    freeze=json.loads((root/'model_freeze_preconfirmation_v1.json').read_text(encoding='utf-8'))['models']
    inv=root.parent/'localization_v2'/'fire_coordinate_inventory_v3.csv'
    view=View(candidates(inv,batch) if batch!='unknown' else [],
              '解码时间戳，50毫秒内配对' if mode=='clip' else '到达时间候选，设备同步未验证')
    Handler.view=view
    Handler.output_dir=out
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    print(json.dumps({'web':f'http://127.0.0.1:{args.port}/','output':str(out)},ensure_ascii=False),flush=True)
    ctx=mp.get_context('spawn');q=ctx.Queue(maxsize=16);start_event=ctx.Event();stop_event=ctx.Event();start_clock=ctx.Value('d',0.0)
    procs=[]
    for sensor,device in (('V',args.v_gpu),('T',args.t_gpu)):
        model=freeze[sensor];p=ctx.Process(target=worker,args=(sensor,sources[sensor],mode,model['weights'],model['weights_sha256'],
                model['thresholds']['flame' if sensor=='V' else 'hotspot'],args.tracker,model['imgsz'],device,out,
                base_pts,start_clock,start_event,q,stop_event),daemon=True);p.start();procs.append(p)
    ready=set();done=set();pending={'V':[],'T':[]};latencies=[];pair_deltas=[];events=0;errors=[]
    pair_rows=[];sensor_rows=[];started=time.monotonic();last_progress=time.monotonic();first_published={};last_published={}
    with (out/'results.jsonl').open('w',encoding='utf-8') as log:
        try:
            while len(done)<2 and not errors:
                if args.run_seconds is not None and start_event.is_set() and time.monotonic()-start_clock.value>=args.run_seconds:
                    stop_event.set()
                try:event=q.get(timeout=1)
                except queue.Empty:
                    if time.monotonic()-last_progress>90:errors.append('worker timeout')
                    if any(not p.is_alive() for p in procs) and len(ready)<2:errors.append('worker exited before ready')
                    continue
                last_progress=time.monotonic();kind=event['type'];sensor=event['sensor']
                if kind=='ready':
                    ready.add(sensor)
                    if len(ready)==2:
                        start_clock.value=time.monotonic()+0.2;start_event.set()
                        with view.lock:view.state['run_status_zh']='运行中'
                elif kind=='error':errors.append(sensor+': '+event['error'])
                elif kind=='done':done.add(sensor)
                elif kind=='frame':
                    jpeg=event.pop('jpeg')
                    event['latency_ms']=max(0,(time.monotonic()-event.pop('source_monotonic'))*1000)
                    published=time.monotonic()
                    first_published.setdefault(sensor,published);last_published[sensor]=published
                    log.write(json.dumps(event,ensure_ascii=False)+'\n');log.flush()
                    events+=1;latencies.append(event['latency_ms'])
                    sensor_rows.append({'sensor':sensor,'frame_seq':event['frame_seq'],'pts_s':event['pts_s'],
                        'latency_ms':event['latency_ms'],'fps':event['fps'],'raw_count':len(event['raw_detections']),
                        'stable_count':sum(t['state']=='stable_candidate' for t in event['tracks']),
                        'held_count':sum(t['state']=='predicted_hold' for t in event['tracks']),'dropped':event['dropped']})
                    pending[sensor].append({'pts':event['pts_s'],'seq':event['frame_seq']})
                    other='T' if sensor=='V' else 'V'
                    if pending[other]:
                        nearest=min(pending[other],key=lambda x:abs(x['pts']-event['pts_s']))
                        delta=abs(nearest['pts']-event['pts_s'])
                        if delta<=.05:
                            pending[other].remove(nearest);pending[sensor].pop()
                            pair_rows.append({'V_frame_seq':event['frame_seq'] if sensor=='V' else nearest['seq'],
                                'T_frame_seq':event['frame_seq'] if sensor=='T' else nearest['seq'],
                                'time_delta_s':delta,'physical_same_source':'unverified'})
                            pair_deltas.append(delta)
                    with view.lock:
                        view.jpeg[sensor]=jpeg
                        cache=view.frame_cache[sensor];cache[event['frame_seq']]=jpeg
                        if len(cache)>30:cache.popitem(last=False)
                        view.state['sensors'][sensor]={k:event[k] for k in ('frame_seq','pts_s','tracks','latency_ms','fps','dropped','source_wall_ms')}
                        view.state['paired_count']=len(pair_rows)
                        view.state['unpaired_V']=len(pending['V']);view.state['unpaired_T']=len(pending['T'])
                        view.state['last_pair_delta_ms']=pair_deltas[-1]*1000 if pair_deltas else None
                        view.state['latency_p95_ms']=percentile(latencies,.95)
        except KeyboardInterrupt:
            errors.append('interrupted')
        finally:
            stop_event.set();start_event.set()
            for p in procs:p.join(timeout=5)
            for p in procs:
                if p.is_alive():p.terminate();p.join(timeout=2)
            browser_videos={}
            if not errors:
                for sensor in ('V','T'):
                    source=out/sensor/'tracked.mp4'
                    target=out/sensor/'tracked_browser.mp4'
                    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),
                             '-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p',
                             '-movflags','+faststart','-an',str(target)]
                    result=subprocess.run(command,capture_output=True,text=True)
                    if result.returncode or not target.is_file():
                        errors.append('browser video encoding failed '+sensor+': '+result.stderr[-500:])
                    else:
                        browser_videos[sensor]=str(target)
            fields=['sensor','frame_seq','pts_s','latency_ms','fps','raw_count','stable_count','held_count','dropped']
            with (out/'performance.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(sensor_rows)
            with (out/'pairs.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['V_frame_seq','T_frame_seq','time_delta_s','physical_same_source']);w.writeheader();w.writerows(pair_rows)
            elapsed=time.monotonic()-started
            sustained_fps={s:((sum(x['sensor']==s for x in sensor_rows)-1)/(last_published[s]-first_published[s])
                          if s in last_published and last_published[s]>first_published[s] else None) for s in ('V','T')}
            summary={'schema_version':'dji_dual_gpu_realtime_v1','mode':mode,'source':str(clip) if clip else sources,
                     'source_manifest_sha256':sha(clip/'manifest.json') if clip else None,
                     'model_freeze':str(root/'model_freeze_preconfirmation_v1.json'),'model_freeze_sha256':sha(root/'model_freeze_preconfirmation_v1.json'),
                     'tracker':str(args.tracker),'tracker_sha256':sha(args.tracker),'gpu':{'V':args.v_gpu,'T':args.t_gpu},
                     'frames':{'V':sum(x['sensor']=='V' for x in sensor_rows),'T':sum(x['sensor']=='T' for x in sensor_rows)},
                     'paired_count':len(pair_rows),'unpaired':{s:len(pending[s]) for s in ('V','T')},
                     'latency_p95_ms':percentile(latencies,.95),'latency_max_ms':max(latencies) if latencies else None,
                     'pair_delta_p95_ms':percentile([x*1000 for x in pair_deltas],.95),'elapsed_wall_s':elapsed,
                     'startup_wall_s':min(first_published.values())-started if first_published else None,
                     'sustained_fps':sustained_fps,
                     'effective_fps':{s:sum(x['sensor']==s for x in sensor_rows)/elapsed for s in ('V','T')},
                     'browser_videos':browser_videos,
                     'errors':errors,'coordinate_policy':'batch candidates only; no per-track WGS84 unless independently confirmed',
                     'same_target_policy':'time pairing is not physical identity','absolute_visual_localization':'unavailable'}
            (out/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            with view.lock:view.state['run_status_zh']='完成' if not errors else '失败'
            print(json.dumps(summary,ensure_ascii=False),flush=True)
            # Keep the web result inspectable until the process is stopped.
            if args.serve_after:
                try:
                    while True:time.sleep(1)
                except KeyboardInterrupt:pass
            server.shutdown()
    if errors:raise RuntimeError('; '.join(errors))


if __name__=='__main__':
    mp.freeze_support()
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--clip',type=Path)
    p.add_argument('--visible');p.add_argument('--thermal');p.add_argument('--batch')
    p.add_argument('--start-s',type=float,default=0.0);p.add_argument('--duration-s',type=float,default=30.0)
    p.add_argument('--session');p.add_argument('--video-group')
    p.add_argument('--tracker',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--port',type=int,default=8783);p.add_argument('--v-gpu',default='0');p.add_argument('--t-gpu',default='1')
    p.add_argument('--run-seconds',type=float)
    p.add_argument('--serve-after',action='store_true');run(p.parse_args())
