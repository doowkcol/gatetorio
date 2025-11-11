# webui.py - Enhanced Web UI for Gate Controller
import json, pathlib, asyncio, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket
import uvicorn

from gate_controller_v2 import GateController
import os

app = FastAPI()
controller = GateController()  # uses same shared dict/logic

# Use environment variable or default paths
CONFIG_DIR = os.getenv('GATETORIO_CONFIG_DIR', '/home/doowkcol/Gatetorio_Code')
CFG = pathlib.Path(CONFIG_DIR) / "gate_config.json"
INPUT_CFG = pathlib.Path(CONFIG_DIR) / "input_config.json"

# Fallback to current directory if config files don't exist
if not CFG.exists():
    CFG = pathlib.Path("gate_config.json")
if not INPUT_CFG.exists():
    INPUT_CFG = pathlib.Path("input_config.json")

INDEX = """<!doctype html><meta charset="utf-8">
<title>Gate Controller</title>
<style>
  body{background:#000;color:#fff;font:16px system-ui;margin:0}
  header{padding:10px 14px;background:#111}
  main{padding:12px;max-width:1200px;margin:0 auto}
  .tabs{display:flex;gap:4px;margin-bottom:12px;overflow-x:auto}
  .tab{background:#222;padding:12px 20px;border-radius:8px 8px 0 0;cursor:pointer;border:2px solid transparent;white-space:nowrap}
  .tab.active{background:#333;border-color:#06c}
  .tab:hover{background:#2a2a2a}
  .page{display:none}
  .page.active{display:block}
  .row{display:flex;gap:8px;margin:8px 0}
  button{font-weight:700;border:0;border-radius:8px;padding:16px;flex:1;cursor:pointer}
  button:active{transform:scale(0.98)}
  .green{background:#0a0;color:#fff}
  .green.on{background:#063;box-shadow:inset 0 0 10px #0f0}
  .red{background:#a00;color:#fff}
  .red.on{background:#600;box-shadow:inset 0 0 10px #f00}
  .blue{background:#06c;color:#fff}
  .blue.on{background:#036;box-shadow:inset 0 0 10px #0cf}
  .yellow{background:#cc0;color:#000}
  .yellow.on{background:#880}
  .orange{background:#f80;color:#000}
  .orange.on{background:#a50}
  .purple{background:#808;color:#fff}
  .purple.on{background:#505}
  .violet{background:#b0b;color:#fff}
  .violet.on{background:#707}
  .blk{background:#333;color:#fff}
  .blk.on{background:#666}
  .cyan{background:#0cc;color:#000}
  .lightgreen{background:#8f8;color:#000}
  .lightblue{background:#8cf;color:#000}
  .tile{background:#222;padding:10px;border-radius:8px;margin:8px 0}
  .small button{padding:10px;font-size:14px}
  pre{white-space:pre-wrap;font:14px ui-monospace}
  label{display:block;margin:6px 0}
  input,select{font:16px;padding:6px;border-radius:6px;border:1px solid #555;background:#111;color:#fff;width:100%}
  .input-row{background:#2a2a2a;padding:10px;margin:8px 0;border-radius:6px;border-left:4px solid #06c}
  .input-row.active{background:#002200;border-color:#0f0}
  .input-label{font-weight:700;color:#0cf;margin-bottom:4px}
  .input-value{font-size:14px;color:#ccc}
  .learn-section{background:#332200;padding:12px;border-radius:6px;margin:10px 0;border:2px solid #f80}
  .learn-btn{background:#f80;color:#000;padding:8px 16px;border:0;border-radius:6px;cursor:pointer}
  .learn-status{background:#003311;padding:12px;border-radius:6px;margin:10px 0}
  .limit-indicator{display:inline-block;width:12px;height:12px;border-radius:50%;background:#444;margin:0 4px}
  .limit-indicator.active{background:#0f0;box-shadow:0 0 8px #0f0}
  .config-grid{display:grid;gap:12px}
  .config-item{background:#2a2a2a;padding:10px;border-radius:6px}
  .config-label{font-weight:700;margin-bottom:4px;color:#0cf}
  .config-desc{font-size:12px;color:#888;margin-top:4px}
  .status-big{font-size:24px;font-weight:700;text-align:center;padding:20px;background:#222;border-radius:8px}
</style>
<header><h2>Gate Controller - Enhanced Web UI</h2></header>
<main>
  <div class="tabs">
    <div class="tab active" onclick="showPage('control')">Control</div>
    <div class="tab" onclick="showPage('settings')">Settings</div>
    <div class="tab" onclick="showPage('inputs')">Input Status</div>
    <div class="tab" onclick="showPage('commands')">Command Editor</div>
    <div class="tab" onclick="showPage('learning')">Learning Mode</div>
  </div>

  <!-- CONTROL PAGE -->
  <div id="control" class="page active">
    <div class="tile">
      <div id="status" class="status-big">Loading…</div>
    </div>

    <div class="row">
      <button id="btnOpen" class="green" onclick="toggle('cmd_open_active')">OPEN</button>
      <button id="btnStop" class="red" onclick="toggle('cmd_stop_active')">STOP</button>
      <button id="btnClose" class="blue" onclick="toggle('cmd_close_active')">CLOSE</button>
    </div>

    <div class="row small">
      <button id="btnPClose" class="yellow" onclick="toggle('photocell_closing_active')">CLOSING PHOTO</button>
      <button id="btnPOpen" class="orange" onclick="toggle('photocell_opening_active')">OPENING PHOTO</button>
      <button id="btnPO1" class="purple" onclick="toggle('partial_1_active')">PO1</button>
      <button id="btnPO2" class="violet" onclick="toggle('partial_2_active')">PO2</button>
    </div>

    <div class="row small">
      <button id="btnSC" class="red" onclick="toggle('safety_stop_closing_active')">STOP CLOSING</button>
      <button id="btnSO" class="red" onclick="toggle('safety_stop_opening_active')">STOP OPENING</button>
      <button id="btnDMO" class="lightgreen" onclick="toggle('deadman_open_active')">DEADMAN OPEN</button>
      <button id="btnDMC" class="lightblue" onclick="toggle('deadman_close_active')">DEADMAN CLOSE</button>
    </div>

    <div class="row small">
      <button id="btnTimed" class="purple" onclick="toggle('timed_open_active')">TIMED OPEN</button>
      <button class="cyan" onclick="pulse()">STEP LOGIC</button>
    </div>

    <div class="tile">
      <h3>Live Log</h3>
      <pre id="log" style="height:180px;overflow:auto;background:#111;padding:8px;border-radius:8px"></pre>
    </div>
  </div>

  <!-- SETTINGS PAGE -->
  <div id="settings" class="page">
    <h2>Configuration Settings</h2>
    <form id="cfg" onsubmit="saveCfg(event)">
      <div class="config-grid">
        <div class="config-item">
          <div class="config-label">Motor 1 Travel Time (s)</div>
          <input name="motor1_run_time" type="number" step="0.1">
          <div class="config-desc">Time for M1 to fully open/close</div>
        </div>
        <div class="config-item">
          <div class="config-label">Motor 2 Travel Time (s)</div>
          <input name="motor2_run_time" type="number" step="0.1">
          <div class="config-desc">Time for M2 to fully open/close</div>
        </div>
        <div class="config-item">
          <div class="config-label">Motor 2 Enabled</div>
          <input name="motor2_enabled" type="checkbox">
          <div class="config-desc">Enable/disable motor 2 (for single-motor systems)</div>
        </div>
        <div class="config-item">
          <div class="config-label">Pause Time (s)</div>
          <input name="pause_time" type="number" step="0.1">
          <div class="config-desc">Pause between movements</div>
        </div>
        <div class="config-item">
          <div class="config-label">Motor 1 Open Delay (s)</div>
          <input name="motor1_open_delay" type="number" step="0.1">
          <div class="config-desc">Delay before M1 starts opening</div>
        </div>
        <div class="config-item">
          <div class="config-label">Motor 2 Close Delay (s)</div>
          <input name="motor2_close_delay" type="number" step="0.1">
          <div class="config-desc">Delay before M2 starts closing</div>
        </div>
        <div class="config-item">
          <div class="config-label">Auto-Close Time (s)</div>
          <input name="auto_close_time" type="number" step="0.1">
          <div class="config-desc">Seconds before auto-close from OPEN</div>
        </div>
        <div class="config-item">
          <div class="config-label">Safety Reverse Time (s)</div>
          <input name="safety_reverse_time" type="number" step="0.1">
          <div class="config-desc">Reverse duration on safety trigger</div>
        </div>
        <div class="config-item">
          <div class="config-label">Deadman Speed (0-1)</div>
          <input name="deadman_speed" type="number" step="0.01" min="0" max="1">
          <div class="config-desc">Speed multiplier for deadman control</div>
        </div>
        <div class="config-item">
          <div class="config-label">Step Logic Mode (1-4)</div>
          <input name="step_logic_mode" type="number" min="1" max="4">
          <div class="config-desc">Step logic behavior mode</div>
        </div>
        <div class="config-item">
          <div class="config-label">PO1 Position (%)</div>
          <input name="partial_1_percent" type="number" min="0" max="100">
          <div class="config-desc">Partial open 1 target percentage</div>
        </div>
        <div class="config-item">
          <div class="config-label">PO2 Position (%)</div>
          <input name="partial_2_percent" type="number" min="0" max="100">
          <div class="config-desc">Partial open 2 target percentage</div>
        </div>
        <div class="config-item">
          <div class="config-label">PO1 Auto-Close (s)</div>
          <input name="partial_1_auto_close_time" type="number" step="0.1">
          <div class="config-desc">Auto-close time for partial position 1</div>
        </div>
        <div class="config-item">
          <div class="config-label">PO2 Auto-Close (s)</div>
          <input name="partial_2_auto_close_time" type="number" step="0.1">
          <div class="config-desc">Auto-close time for partial position 2</div>
        </div>
        <div class="config-item">
          <div class="config-label">Partial Return Pause (s)</div>
          <input name="partial_return_pause" type="number" step="0.1">
          <div class="config-desc">Pause before returning from partial</div>
        </div>
        <div class="config-item">
          <div class="config-label">Auto-Close Enabled</div>
          <select name="auto_close_enabled">
            <option value="false">false</option>
            <option value="true">true</option>
          </select>
        </div>
        <div class="config-item">
          <div class="config-label">Opening Slowdown %</div>
          <input name="opening_slowdown_percent" type="number" step="0.5" min="0.5" max="20">
          <div class="config-desc">Slowdown percentage when opening</div>
        </div>
        <div class="config-item">
          <div class="config-label">Closing Slowdown %</div>
          <input name="closing_slowdown_percent" type="number" step="0.5" min="0.5" max="20">
          <div class="config-desc">Slowdown percentage when closing</div>
        </div>
        <div class="config-item">
          <div class="config-label">Slowdown Distance (s)</div>
          <input name="slowdown_distance" type="number" step="0.1">
          <div class="config-desc">Distance to apply slowdown</div>
        </div>
        <div class="config-item">
          <div class="config-label">Learning Speed (0-1)</div>
          <input name="learning_speed" type="number" step="0.05" min="0.1" max="1">
          <div class="config-desc">Speed during learning mode</div>
        </div>
        <div class="config-item">
          <div class="config-label">Open Speed (0-1)</div>
          <input name="open_speed" type="number" step="0.05" min="0.1" max="1">
          <div class="config-desc">Normal opening speed</div>
        </div>
        <div class="config-item">
          <div class="config-label">Close Speed (0-1)</div>
          <input name="close_speed" type="number" step="0.05" min="0.1" max="1">
          <div class="config-desc">Normal closing speed</div>
        </div>
        <div class="config-item">
          <div class="config-label">Limit Switch Creep Speed (0-1)</div>
          <input name="limit_switch_creep_speed" type="number" step="0.05" min="0.1" max="1">
          <div class="config-desc">Slow speed near limit switches</div>
        </div>
      </div>
      <div class="row" style="margin-top:16px">
        <button type="submit" class="green">SAVE CONFIG</button>
        <button type="button" class="blue" onclick="reload()">RELOAD CONTROLLER</button>
      </div>
    </form>
  </div>

  <!-- INPUT STATUS PAGE -->
  <div id="inputs" class="page">
    <h2>Input Status Monitor</h2>
    <div id="inputList"></div>
  </div>

  <!-- COMMAND EDITOR PAGE -->
  <div id="commands" class="page">
    <h2>Command Editor</h2>
    <p style="color:#888">Assign commands to physical input terminals</p>
    <div id="commandList"></div>
    <div class="row" style="margin-top:16px">
      <button class="green" onclick="saveCommands()">SAVE ASSIGNMENTS</button>
    </div>
  </div>

  <!-- LEARNING MODE PAGE -->
  <div id="learning" class="page">
    <h2 style="color:#ff0">Learning Mode</h2>

    <div class="learn-section" style="background:#440000">
      <label>
        <input type="checkbox" id="engineerMode" onchange="toggleEngineerMode()">
        <strong>🔧 ENGINEER MODE</strong> (Enable before learning - blocks normal commands)
      </label>
    </div>

    <div class="learn-section" style="background:#003300">
      <label>
        <input type="checkbox" id="learningMode" onchange="toggleLearningMode()" disabled>
        <strong>📚 Learning Mode</strong> (Record travel times)
      </label>
    </div>

    <div class="tile">
      <h3>Limit Switch Configuration</h3>
      <label><input type="checkbox" id="m1LimitSwitches"> Motor 1 use limit switches</label>
      <label><input type="checkbox" id="m2LimitSwitches"> Motor 2 use limit switches</label>
    </div>

    <div class="tile">
      <h3>Learned Travel Times</h3>
      <div id="learnedTimes">
        <div>M1 Open: <span id="m1OpenTime">Not learned</span></div>
        <div>M1 Close: <span id="m1CloseTime">Not learned</span></div>
        <div>M2 Open: <span id="m2OpenTime">Not learned</span></div>
        <div>M2 Close: <span id="m2CloseTime">Not learned</span></div>
      </div>
    </div>

    <div class="learn-status">
      <h3 style="color:#f0f">🤖 AUTOMATED LEARNING</h3>
      <p style="font-size:14px">Automatically learn gate travel times through progressive cycles</p>
      <div id="autoLearnStatus" style="font-weight:700;color:#ff0;margin:10px 0">Status: Ready</div>
      <div style="margin:10px 0">
        <strong>Limit Switches:</strong><br>
        <span>M1 Open <span class="limit-indicator" id="lsM1Open"></span></span>
        <span>M1 Close <span class="limit-indicator" id="lsM1Close"></span></span>
        <span>M2 Open <span class="limit-indicator" id="lsM2Open"></span></span>
        <span>M2 Close <span class="limit-indicator" id="lsM2Close"></span></span>
      </div>
      <div class="row">
        <button id="startAutoLearn" class="green" onclick="startAutoLearn()">▶ START AUTO-LEARN</button>
        <button id="stopAutoLearn" class="red" onclick="stopAutoLearn()" disabled>⬛ STOP</button>
      </div>
    </div>

    <div class="row" style="margin-top:16px">
      <button class="green" onclick="saveLearningConfig()">SAVE LEARNING CONFIG</button>
      <button class="orange" onclick="saveLearnedTimes()">SAVE LEARNED TIMES</button>
    </div>
  </div>
</main>

<script>
async function fetchJSON(u,opts){const r=await fetch(u,opts); if(!r.ok) throw new Error(await r.text()); return r.json();}
function setBtn(id,on){const el=document.getElementById(id); if(!el) return; on?el.classList.add('on'):el.classList.remove('on');}

// Page navigation
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(page).classList.add('active');
  event.target.classList.add('active');

  // Load page-specific data
  if (page === 'inputs') loadInputStatus();
  if (page === 'commands') loadCommandEditor();
  if (page === 'learning') loadLearningPage();
  if (page === 'settings') loadCfg();
}

// Control page
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

    // Update limit switch indicators on learning page
    updateLimitIndicators(s.flags);
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

// Settings page
async function loadCfg(){
  const c = await fetchJSON('/api/config');
  for (const k in c){
    const el = document.querySelector(`[name="${k}"]`);
    if(el){
      if(el.type === 'checkbox'){
        el.checked = Boolean(c[k]);
      } else if(el.tagName==='SELECT'){
        el.value = String(c[k]);
      } else {
        el.value = c[k];
      }
    }
  }
}
async function saveCfg(e){
  e.preventDefault();
  const form = document.getElementById('cfg');
  const fd = new FormData(form);
  const out = {};

  // Handle all form elements including checkboxes
  for (const el of form.elements) {
    if (el.name) {
      if (el.type === 'checkbox') {
        out[el.name] = el.checked;
      } else if (fd.has(el.name)) {
        const v = fd.get(el.name);
        out[el.name] = (v==='true'||v==='false')? (v==='true') : Number(v);
      }
    }
  }

  await fetchJSON('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(out)});
  alert('Configuration saved!');
}
async function reload(){ await fetchJSON('/api/reload',{method:'POST'}); }

// Input Status page
async function loadInputStatus(){
  const inputs = await fetchJSON('/api/inputs');
  const list = document.getElementById('inputList');
  list.innerHTML = '';
  for (const [name, data] of Object.entries(inputs)) {
    const div = document.createElement('div');
    div.className = 'input-row' + (data.state ? ' active' : '');
    div.innerHTML = `
      <div class="input-label">${name} (CH${data.channel})</div>
      <div class="input-value">
        Type: ${data.type} | Function: ${data.function || '[unassigned]'} |
        State: <strong>${data.state ? 'ACTIVE' : 'INACTIVE'}</strong> |
        Voltage: ${data.voltage.toFixed(2)}V |
        Resistance: ${data.resistance === null ? 'N/A' : data.resistance === Infinity ? 'OPEN' : data.resistance === 0 ? 'SHORT' : data.resistance >= 1000 ? (data.resistance/1000).toFixed(1) + 'kΩ' : data.resistance.toFixed(0) + 'Ω'}
      </div>
      ${data.description ? `<div style="font-size:12px;color:#888">${data.description}</div>` : ''}
    `;
    list.appendChild(div);
  }
}

// Command Editor page
async function loadCommandEditor(){
  const cfg = await fetchJSON('/api/input_config');
  const list = document.getElementById('commandList');
  list.innerHTML = '';

  const commands = [
    ['none', '[None - Disabled]'],
    ['cmd_open', 'Open Command'],
    ['cmd_close', 'Close Command'],
    ['cmd_stop', 'Stop Command'],
    ['photocell_closing', 'Photocell (Closing)'],
    ['photocell_opening', 'Photocell (Opening)'],
    ['safety_stop_closing', 'Safety Edge (Stop Closing)'],
    ['safety_stop_opening', 'Safety Edge (Stop Opening)'],
    ['deadman_open', 'Deadman Open'],
    ['deadman_close', 'Deadman Close'],
    ['timed_open', 'Timed Open'],
    ['partial_1', 'Partial Open 1'],
    ['partial_2', 'Partial Open 2'],
    ['step_logic', 'Step Logic'],
    ['open_limit_m1', 'Limit Switch - M1 OPEN'],
    ['close_limit_m1', 'Limit Switch - M1 CLOSE'],
    ['open_limit_m2', 'Limit Switch - M2 OPEN'],
    ['close_limit_m2', 'Limit Switch - M2 CLOSE']
  ];

  for (const [name, input] of Object.entries(cfg.inputs)) {
    const div = document.createElement('div');
    div.className = 'tile';
    div.innerHTML = `
      <div style="font-weight:700;color:#0cf;margin-bottom:8px">
        <label><input type="checkbox" data-input="${name}" data-field="enabled" ${input.enabled ? 'checked' : ''}> ${name} (CH${input.channel})</label>
      </div>
      <div class="row">
        <div style="flex:1">
          <label>Type:</label>
          <select data-input="${name}" data-field="type">
            <option value="NO" ${input.type === 'NO' ? 'selected' : ''}>NO</option>
            <option value="NC" ${input.type === 'NC' ? 'selected' : ''}>NC</option>
            <option value="8K2" ${input.type === '8K2' ? 'selected' : ''}>8K2</option>
          </select>
        </div>
        <div style="flex:2">
          <label>Command:</label>
          <select data-input="${name}" data-field="function">
            ${commands.map(([val, label]) => `<option value="${val}" ${(input.function || 'none') === val ? 'selected' : ''}>${label}</option>`).join('')}
          </select>
        </div>
      </div>
      ${input.description ? `<div style="font-size:12px;color:#888;margin-top:4px">${input.description}</div>` : ''}
    `;
    list.appendChild(div);
  }
}

async function saveCommands(){
  const cfg = await fetchJSON('/api/input_config');
  const inputs = cfg.inputs;

  document.querySelectorAll('[data-input]').forEach(el => {
    const inputName = el.dataset.input;
    const field = el.dataset.field;
    if (!inputs[inputName]) return;

    if (el.type === 'checkbox') {
      inputs[inputName][field] = el.checked;
    } else if (el.tagName === 'SELECT') {
      let val = el.value;
      if (field === 'function' && val === 'none') val = null;
      inputs[inputName][field] = val;
    }
  });

  await fetchJSON('/api/input_config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({inputs})
  });
  alert('Command assignments saved!');
}

// Learning Mode page
async function loadLearningPage(){
  const cfg = await fetchJSON('/api/config');
  document.getElementById('engineerMode').checked = cfg.engineer_mode_enabled || false;
  document.getElementById('learningMode').checked = cfg.learning_mode_enabled || false;
  document.getElementById('learningMode').disabled = !cfg.engineer_mode_enabled;
  document.getElementById('m1LimitSwitches').checked = cfg.motor1_use_limit_switches || false;
  document.getElementById('m2LimitSwitches').checked = cfg.motor2_use_limit_switches || false;

  // Load learned times
  const times = await fetchJSON('/api/learned_times');
  document.getElementById('m1OpenTime').textContent = times.m1_open ? times.m1_open.toFixed(2) + 's' : 'Not learned';
  document.getElementById('m1CloseTime').textContent = times.m1_close ? times.m1_close.toFixed(2) + 's' : 'Not learned';
  document.getElementById('m2OpenTime').textContent = times.m2_open ? times.m2_open.toFixed(2) + 's' : 'Not learned';
  document.getElementById('m2CloseTime').textContent = times.m2_close ? times.m2_close.toFixed(2) + 's' : 'Not learned';
}

async function toggleEngineerMode(){
  const enabled = document.getElementById('engineerMode').checked;
  await fetchJSON('/api/engineer_mode', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({enabled})
  });
  document.getElementById('learningMode').disabled = !enabled;
  if (!enabled) {
    document.getElementById('learningMode').checked = false;
    await toggleLearningMode();
  }
}

async function toggleLearningMode(){
  const enabled = document.getElementById('learningMode').checked;
  await fetchJSON('/api/learning_mode', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({enabled})
  });
}

async function startAutoLearn(){
  const res = await fetchJSON('/api/auto_learn/start', {method: 'POST'});
  if (res.ok) {
    document.getElementById('startAutoLearn').disabled = true;
    document.getElementById('stopAutoLearn').disabled = false;
  }
}

async function stopAutoLearn(){
  await fetchJSON('/api/auto_learn/stop', {method: 'POST'});
  document.getElementById('startAutoLearn').disabled = false;
  document.getElementById('stopAutoLearn').disabled = true;
}

async function saveLearningConfig(){
  const cfg = await fetchJSON('/api/config');
  cfg.motor1_use_limit_switches = document.getElementById('m1LimitSwitches').checked;
  cfg.motor2_use_limit_switches = document.getElementById('m2LimitSwitches').checked;
  cfg.limit_switches_enabled = cfg.motor1_use_limit_switches || cfg.motor2_use_limit_switches;

  await fetchJSON('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(cfg)
  });
  alert('Learning configuration saved!');
}

async function saveLearnedTimes(){
  await fetchJSON('/api/save_learned_times', {method: 'POST'});
  alert('Learned times saved!');
  loadLearningPage();
}

function updateLimitIndicators(flags){
  const indicators = {
    'lsM1Open': 'open_limit_m1_active',
    'lsM1Close': 'close_limit_m1_active',
    'lsM2Open': 'open_limit_m2_active',
    'lsM2Close': 'close_limit_m2_active'
  };
  for (const [id, key] of Object.entries(indicators)) {
    const el = document.getElementById(id);
    if (el) {
      if (flags[key]) el.classList.add('active');
      else el.classList.remove('active');
    }
  }
}

// WebSocket log
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
        'open_limit_m1_active': controller.shared.get('open_limit_m1_active', False),
        'close_limit_m1_active': controller.shared.get('close_limit_m1_active', False),
        'open_limit_m2_active': controller.shared.get('open_limit_m2_active', False),
        'close_limit_m2_active': controller.shared.get('close_limit_m2_active', False),
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
    # if STOP is toggled, make it "sustained" like Tk loop
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

@app.get("/api/inputs")
def get_inputs():
    """Get all input states with voltage/resistance data"""
    try:
        print(f"Reading input config from: {INPUT_CFG}")
        with open(INPUT_CFG, 'r') as f:
            input_config = json.load(f)

        inputs = {}
        for name, cfg in input_config.get('inputs', {}).items():
            state_key = f'{name}_state'
            voltage_key = f'{name}_voltage'
            resistance_key = f'{name}_resistance'

            # Debug: print what keys are in shared memory
            if len(inputs) == 0:  # Only print once
                print(f"Sample keys in controller.shared: {list(controller.shared.keys())[:10]}")

            # Get resistance and handle inf/nan values (not JSON compliant)
            resistance = controller.shared.get(resistance_key, None)
            if resistance is not None:
                import math
                if math.isinf(resistance) or math.isnan(resistance):
                    resistance = None  # Convert inf/nan to null for JSON

            inputs[name] = {
                'channel': cfg['channel'],
                'type': cfg.get('type', 'NO'),
                'function': cfg.get('function'),
                'description': cfg.get('description', ''),
                'state': controller.shared.get(state_key, False),
                'voltage': controller.shared.get(voltage_key, 0.0),
                'resistance': resistance,
            }
        print(f"Returning {len(inputs)} inputs")
        return JSONResponse(inputs)
    except Exception as e:
        import traceback
        print(f"ERROR in /api/inputs: {e}")
        print(traceback.format_exc())
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/input_config")
def get_input_config():
    """Get input configuration"""
    try:
        return JSONResponse(json.loads(INPUT_CFG.read_text()))
    except Exception:
        return JSONResponse({"inputs": {}}, status_code=200)

@app.post("/api/input_config")
async def set_input_config(req: Request):
    """Save input configuration"""
    try:
        cfg = await req.json()
        INPUT_CFG.write_text(json.dumps(cfg, indent=2))
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/learned_times")
def get_learned_times():
    """Get learned travel times"""
    status = controller.get_learning_status()
    return JSONResponse({
        'm1_open': status.get('m1_open_time'),
        'm1_close': status.get('m1_close_time'),
        'm2_open': status.get('m2_open_time'),
        'm2_close': status.get('m2_close_time'),
    })

@app.post("/api/save_learned_times")
def save_learned_times():
    """Save learned times to config"""
    success = controller.save_learned_times()
    return {"ok": success}

@app.post("/api/engineer_mode")
async def set_engineer_mode(req: Request):
    """Toggle engineer mode"""
    data = await req.json()
    enabled = data.get('enabled', False)
    controller.shared['engineer_mode_enabled'] = enabled
    return {"ok": True, "enabled": enabled}

@app.post("/api/learning_mode")
async def set_learning_mode(req: Request):
    """Toggle learning mode"""
    data = await req.json()
    enabled = data.get('enabled', False)
    if enabled:
        controller.enable_learning_mode()
    else:
        controller.disable_learning_mode()
    return {"ok": True, "enabled": enabled}

@app.post("/api/auto_learn/start")
def start_auto_learn():
    """Start automated learning sequence"""
    success = controller.start_auto_learn()
    return {"ok": success}

@app.post("/api/auto_learn/stop")
def stop_auto_learn():
    """Stop automated learning sequence"""
    controller.stop_auto_learn()
    return {"ok": True}

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
        # Connection closed by client - don't try to close again
        pass

if __name__ == "__main__":
    import threading
    from gate_ui import GateUI

    # Start web server in background thread
    def run_web_server():
        uvicorn.run(app, host="0.0.0.0", port=8000)

    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("Web server starting on http://0.0.0.0:8000")

    # Get local IP for LAN access info
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"Web UI accessible from LAN at: http://{local_ip}:8000")
    except:
        print("Web UI accessible at: http://localhost:8000")

    # Start Tkinter UI in main thread (required for GUI)
    # Pass the same controller instance so both UIs share the same data
    print("Starting Tkinter UI...")
    ui = GateUI(controller=controller)
    ui.run()
