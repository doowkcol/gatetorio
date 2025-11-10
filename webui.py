# webui.py
import json, pathlib, asyncio, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket
import uvicorn

from gate_controller_v2 import GateController

app = FastAPI()
controller = GateController()  # uses same shared dict/logic
CFG = pathlib.Path("/home/doowkcol/Gatetorio_Code/gate_config.json")
INPUT_CFG = pathlib.Path("/home/doowkcol/Gatetorio_Code/input_config.json")

INDEX = """<!doctype html><meta charset="utf-8">
<title>Gate Controller</title>
<style>
  body{background:#000;color:#fff;font:16px system-ui;margin:0}
  header,footer{padding:10px 14px;background:#111}
  main{padding:12px}
  .row{display:flex;gap:8px;margin:8px 0}
  button{font-weight:700;border:0;border-radius:8px;padding:16px;flex:1}
  .green{background:#0a0}
  .green.on{background:#063}
  .red{background:#a00}
  .red.on{background:#600}
  .blue{background:#06c}
  .blue.on{background:#036}
  .blk{background:#333}
  .tile{background:#222;padding:10px;border-radius:8px}
  .small button{padding:10px}
  pre{white-space:pre-wrap;font:14px ui-monospace}
  label{display:block;margin:6px 0}
  input,select{font:16px;padding:6px;border-radius:6px;border:1px solid #555;background:#111;color:#fff}
</style>
<header><h2>Gate Controller</h2></header>
<main>
  <div class="tile">
    <div id="status" style="font-weight:700;font-size:18px">Loading…</div>
  </div>

  <div class="row">
    <button id="btnOpen"  class="green" onclick="toggle('cmd_open_active')">OPEN</button>
    <button id="btnStop"  class="red"   onclick="toggle('cmd_stop_active')">STOP</button>
    <button id="btnClose" class="blue"  onclick="toggle('cmd_close_active')">CLOSE</button>
  </div>

  <div class="row small">
    <button id="btnPClose"  class="blk" onclick="toggle('photocell_closing_active')">CLOSING PHOTO</button>
    <button id="btnPOpen"   class="blk" onclick="toggle('photocell_opening_active')">OPENING PHOTO</button>
    <button id="btnPO1"     class="blk" onclick="toggle('partial_1_active')">PO1</button>
    <button id="btnPO2"     class="blk" onclick="toggle('partial_2_active')">PO2</button>
  </div>

  <div class="row small">
    <button id="btnSC" class="red" onclick="toggle('safety_stop_closing_active')">STOP CLOSING</button>
    <button id="btnSO" class="red" onclick="toggle('safety_stop_opening_active')">STOP OPENING</button>
    <button id="btnDMO" class="blk" onclick="toggle('deadman_open_active')">DEADMAN OPEN</button>
    <button id="btnDMC" class="blk" onclick="toggle('deadman_close_active')">DEADMAN CLOSE</button>
    <button id="btnTimed" class="blk" onclick="toggle('timed_open_active')">TIMED OPEN</button>
    <button class="blk" onclick="pulse()">STEP LOGIC</button>
  </div>

  <div class="tile">
    <h3>Settings</h3>
    <form id="cfg" onsubmit="saveCfg(event)">
      <div class="row">
        <label style="flex:1">Run Time (s)
          <input name="run_time" type="number" step="0.1">
        </label>
        <label style="flex:1">Pause Time (s)
          <input name="pause_time" type="number" step="0.1">
        </label>
        <label style="flex:1">Auto-close (s)
          <input name="auto_close_time" type="number" step="0.1">
        </label>
        <label style="flex:1">Auto-close Enabled
          <select name="auto_close_enabled">
            <option value="false">false</option>
            <option value="true">true</option>
          </select>
        </label>
      </div>
      <div class="row">
        <button type="submit" class="green">SAVE CONFIG</button>
        <button type="button" class="blue" onclick="reload()">RELOAD CONTROLLER</button>
      </div>
    </form>
  </div>

  <div class="tile">
    <h3>Live log</h3>
    <pre id="log" style="height:180px;overflow:auto;background:#111;padding:8px;border-radius:8px"></pre>
  </div>
</main>
<footer>Web UI served locally. Use a tunnel to publish.</footer>

<script>
async function fetchJSON(u,opts){const r=await fetch(u,opts); if(!r.ok) throw new Error(await r.text()); return r.json();}
function setBtn(id,on){const el=document.getElementById(id); if(!el) return; on?el.classList.add('on'):el.classList.remove('on');}

async function refresh(){
  try{
    const s = await fetchJSON('/api/status');
    document.getElementById('status').textContent =
      `${s.state} | M1 ${s.m1_percent}% (spd ${s.m1_speed}%)  M2 ${s.m2_percent}% (spd ${s.m2_speed}%)`+
      (s.auto_close_active?` | Auto-close ${s.auto_close_countdown}s`:
        s.partial_1_auto_close_active?` | PO1 ${s.partial_1_auto_close_countdown}s`:
        s.partial_2_auto_close_active?` | PO2 ${s.partial_2_auto_close_countdown}s`:'');
    setBtn('btnOpen',  s.flags.cmd_open_active);
    setBtn('btnStop',  s.flags.cmd_stop_active);
    setBtn('btnClose', s.flags.cmd_close_active);
    setBtn('btnPClose', s.flags.photocell_closing_active);
    setBtn('btnPOpen',  s.flags.photocell_opening_active);
    setBtn('btnPO1',    s.flags.partial_1_active);
    setBtn('btnPO2',    s.flags.partial_2_active);
    setBtn('btnSC', s.flags.safety_stop_closing_active);
    setBtn('btnSO', s.flags.safety_stop_opening_active);
    setBtn('btnDMO', s.flags.deadman_open_active);
    setBtn('btnDMC', s.flags.deadman_close_active);
    setBtn('btnTimed', s.flags.timed_open_active);
  }catch(e){/* no-op */}
}

async function toggle(key){
  await fetchJSON('/api/toggle',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({key})});
  refresh();
}
async function pulse(){
  await fetchJSON('/api/pulse',{method:'POST'});
}
async function loadCfg(){
  const c = await fetchJSON('/api/config');
  for (const k in c){ const el = document.querySelector(`[name="${k}"]`); if(el){
    if(el.tagName==='SELECT'){ el.value = String(c[k]); } else { el.value = c[k]; }
  }}
}
async function saveCfg(e){
  e.preventDefault();
  const fd = new FormData(document.getElementById('cfg'));
  const out = {};
  fd.forEach((v,k)=>{ out[k]= (v==='true'||v==='false')? (v==='true') : Number(v); });
  await fetchJSON('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(out)});
}
async function reload(){ await fetchJSON('/api/reload',{method:'POST'}); }

const logEl = document.getElementById('log');
let ws;
function openWS(){
  const proto = location.protocol==='https:'?'wss':'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = e => { logEl.textContent = e.data + "\\n" + logEl.textContent; };
  ws.onclose = ()=>{ setTimeout(openWS, 1500); };
}
openWS();
loadCfg();
setInterval(refresh, 500);
</script>
"""

@app.get("/", response_class=HTMLResponse)
def index(): return HTMLResponse(INDEX)

@app.get("/api/status")
def status():
    s = controller.get_status()
    flags = {
        'cmd_open_active': controller.shared.get('cmd_open_active', False),
        'cmd_stop_active': controller.shared.get('cmd_stop_active', False),
        'cmd_close_active': controller.shared.get('cmd_close_active', False),
        'photocell_closing_active': controller.shared.get('photocell_closing_active', False),
        'photocell_opening_active': controller.shared.get('photocell_opening_active', False),
        'partial_1_active': controller.shared.get('partial_1_active', False),
        'partial_2_active': controller.shared.get('partial_2_active', False),
        'safety_stop_closing_active': controller.shared.get('safety_stop_closing_active', False),
        'safety_stop_opening_active': controller.shared.get('safety_stop_opening_active', False),
        'deadman_open_active': controller.shared.get('deadman_open_active', False),
        'deadman_close_active': controller.shared.get('deadman_close_active', False),
        'timed_open_active': controller.shared.get('timed_open_active', False),
    }
    s['flags'] = flags
    # coerce numbers to simple ints for display
    for k in ['m1_percent','m2_percent','m1_speed','m2_speed','auto_close_countdown',
              'partial_1_auto_close_countdown','partial_2_auto_close_countdown']:
        if k in s and s[k] is not None:
            s[k] = int(s[k])
    return JSONResponse(s)

@app.post("/api/toggle")
async def toggle(req: Request):
    data = await req.json()
    key = data.get("key")
    # if STOP is toggled, make it “sustained” like Tk loop
    if key == 'cmd_stop_active':
        controller.shared['cmd_stop_active'] = not controller.shared.get('cmd_stop_active', False)
    else:
        controller.shared[key] = not controller.shared.get(key, False)
    return JSONResponse({"ok": True, "key": key, "value": controller.shared[key]})

@app.post("/api/pulse")
def pulse():
    controller.shared['step_logic_pulse'] = True
    return {"ok": True}

@app.get("/api/config")
def get_config():
    try:
        return JSONResponse(json.loads(CFG.read_text()))
    except Exception:
        return JSONResponse({}, status_code=200)

@app.post("/api/config")
async def set_config(req: Request):
    try:
        # stop before writing, match Tk behaviour
        controller.shared['cmd_stop_active'] = True
        controller.shared['cmd_open_active'] = False
        controller.shared['cmd_close_active'] = False
        cfg = await req.json()
        CFG.write_text(json.dumps(cfg, indent=2))
        controller.reload_config()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/reload")
def reload_cfg():
    ok = controller.reload_config()
    return {"ok": bool(ok)}

@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            s = controller.get_status()
            msg = f"{time.strftime('%H:%M:%S')} | {s['state']} | M1 {s['m1_percent']:.0f}% spd {s['m1_speed']:.0f}% | M2 {s['m2_percent']:.0f}% spd {s['m2_speed']:.0f}%"
            await ws.send_text(msg)
            await asyncio.sleep(1.0)
    except Exception:
        await ws.close()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
