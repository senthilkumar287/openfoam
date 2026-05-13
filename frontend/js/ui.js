/* ============================================================
   OpenFOAM Clone — Main UI Controller
   Handles: mesh, solver, BC, simulation, visualization
   ============================================================ */
const API = 'http://localhost:5000';
let currentMesh = null, currentSolver = null;
let monTimer = null, startTime = null;
let residualHistory = {};
let activeBCs = [];
let activeField = 'T';
let viz3d = null, rightViz3d = null;
let lastHeatmap = null;

// ── Tab switching ──
function switchLeftTab(id, el) {
  document.querySelectorAll('.ppanel').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.ptab').forEach(t => t.classList.remove('on'));
  document.getElementById('ltab-' + id).classList.add('on');
  el.classList.add('on');
}
function switchView(id, el) {
  document.querySelectorAll('.vpanel').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.vtab').forEach(t => t.classList.remove('on'));
  document.getElementById('vpanel-' + id).classList.add('on');
  el.classList.add('on');
}
function switchRight(id, el) {
  document.querySelectorAll('.rpanel').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.rnav-item').forEach(t => t.classList.remove('on'));
  document.getElementById('rpanel-' + id).classList.add('on');
  el.classList.add('on');
}
function switchLog(id, el) {
  document.querySelectorAll('.ltab').forEach(t => t.classList.remove('on'));
  el.classList.add('on');
  document.getElementById('log-out').style.display = id === 'log' ? 'block' : 'none';
  const mp = document.getElementById('mon-panel');
  mp.style.display = id === 'mon' ? 'block' : 'none';
  if (id === 'mon') mp.classList.add('show');
}

// ── Logging ──
function log(msg, type = 'info') {
  const el = document.getElementById('log-out');
  const t = new Date().toLocaleTimeString();
  const prefix = type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warn' ? '⚠' : '›';
  el.value += `[${t}] ${prefix} ${msg}\n`;
  el.scrollTop = el.scrollHeight;
}
function clearLog() { document.getElementById('log-out').value = ''; }
function setStatus(txt, cls = '') {
  const el = document.getElementById('tb-status-text');
  el.textContent = txt;
  el.style.color = cls === 'ok' ? 'var(--green)' : cls === 'er' ? 'var(--red)' : 'var(--txt3)';
}

// ── Toast ──
function toast(msg, type = 'in') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + type;
  setTimeout(() => { t.className = ''; }, 3000);
}

// ── Mesh dimension toggle ──
function onDimChange() {
  const is3d = document.getElementById('mesh-dim').value === '3d';
  document.getElementById('nz-row').style.display = is3d ? 'flex' : 'none';
  document.getElementById('lz-row').style.display = is3d ? 'flex' : 'none';
  updateMeshPreview();
}

// ── LIVE MESH PREVIEW (canvas) ──
function updateMeshPreview() {
  const canvas = document.getElementById('mesh-preview');
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.offsetWidth || 240;
  const H = canvas.height = 170;

  const nx = parseInt(document.getElementById('mesh-nx').value) || 30;
  const ny = parseInt(document.getElementById('mesh-ny').value) || 30;
  const lx = parseFloat(document.getElementById('dom-x').value) || 1;
  const ly = parseFloat(document.getElementById('dom-y').value) || 1;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#060a0d';
  ctx.fillRect(0, 0, W, H);

  const pad = 20, drawW = W - 2*pad, drawH = H - 2*pad;
  const scaleX = drawW / lx, scaleY = drawH / ly;

  // Grid lines
  const stepX = nx <= 40 ? 1 : Math.ceil(nx / 40);
  const stepY = ny <= 40 ? 1 : Math.ceil(ny / 40);
  const dx = lx / nx, dy = ly / ny;

  ctx.strokeStyle = 'rgba(10,132,255,0.2)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= nx; i += stepX) {
    const x = pad + i * dx * scaleX;
    ctx.beginPath(); ctx.moveTo(x, pad); ctx.lineTo(x, pad + drawH); ctx.stroke();
  }
  for (let j = 0; j <= ny; j += stepY) {
    const y = pad + j * dy * scaleY;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(pad + drawW, y); ctx.stroke();
  }

  // Border
  ctx.strokeStyle = 'rgba(10,132,255,0.8)';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(pad, pad, drawW, drawH);

  // BC patches (colored walls)
  const patchColors = { left:'rgba(255,70,70,.7)', right:'rgba(70,130,255,.7)',
    top:'rgba(255,200,50,.5)', bottom:'rgba(50,200,80,.5)' };
  const patchLocs = { left:[pad,pad,3,drawH], right:[pad+drawW-3,pad,3,drawH],
    top:[pad,pad,drawW,3], bottom:[pad,pad+drawH-3,drawW,3] };
  for (const bc of activeBCs) {
    if (patchColors[bc.patch]) {
      ctx.fillStyle = patchColors[bc.patch];
      ctx.fillRect(...patchLocs[bc.patch]);
    }
  }

  // Dimension labels
  ctx.fillStyle = 'rgba(100,210,255,.7)';
  ctx.font = '9px JetBrains Mono, monospace';
  ctx.textAlign = 'center';
  ctx.fillText(`Lx=${lx}m  nx=${nx}`, W/2, H-4);
  ctx.textAlign = 'left';
  ctx.save(); ctx.translate(8, H/2); ctx.rotate(-Math.PI/2);
  ctx.fillText(`Ly=${ly}m  ny=${ny}`, 0, 0);
  ctx.restore();

  // Cell count
  const cells = nx * ny * (document.getElementById('mesh-dim').value === '3d' ?
    (parseInt(document.getElementById('mesh-nz').value)||10) : 1);
  ctx.fillStyle = 'rgba(10,132,255,.9)';
  ctx.font = 'bold 10px JetBrains Mono, monospace';
  ctx.textAlign = 'right';
  ctx.fillText(`${cells.toLocaleString()} cells`, W-4, 14);
}

// ── BC PREVIEW CANVAS ──
function updateBCPreview() {
  const canvas = document.getElementById('bc-preview');
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.offsetWidth || 240;
  const H = canvas.height = 170;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#060a0d';
  ctx.fillRect(0, 0, W, H);

  const pad = 20, drawW = W - 2*pad, drawH = H - 2*pad;

  // Background domain
  ctx.fillStyle = '#0a1520';
  ctx.fillRect(pad, pad, drawW, drawH);
  ctx.strokeStyle = 'rgba(10,132,255,.4)';
  ctx.lineWidth = 1;
  ctx.strokeRect(pad, pad, drawW, drawH);

  // Interior gradient hint
  const gradient = ctx.createLinearGradient(pad, 0, pad+drawW, 0);
  gradient.addColorStop(0, 'rgba(255,100,50,.35)');
  gradient.addColorStop(1, 'rgba(50,100,255,.35)');
  ctx.fillStyle = gradient;
  ctx.fillRect(pad+3, pad+3, drawW-6, drawH-6);

  const colorMap = {
    dirichlet: '#ff4646', neumann: '#32d74b',
    wall: '#8888aa', inlet: '#ff9f0a', outlet: '#64d2ff'
  };
  const legend = {};

  for (const bc of activeBCs) {
    const col = colorMap[bc.type] || '#ffffff';
    ctx.fillStyle = col;
    ctx.lineWidth = 4;
    ctx.strokeStyle = col;
    legend[bc.type] = col;
    if (bc.patch === 'left')   { ctx.fillRect(pad-2, pad, 6, drawH); }
    if (bc.patch === 'right')  { ctx.fillRect(pad+drawW-4, pad, 6, drawH); }
    if (bc.patch === 'top')    { ctx.fillRect(pad, pad-2, drawW, 6); }
    if (bc.patch === 'bottom') { ctx.fillRect(pad, pad+drawH-4, drawW, 6); }
    // Label value
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 9px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    const val = bc.type === 'dirichlet' ? `${bc.value}°` : bc.type;
    if (bc.patch === 'left')   ctx.fillText(val, pad+12, H/2);
    if (bc.patch === 'right')  ctx.fillText(val, pad+drawW-12, H/2);
    if (bc.patch === 'top')    ctx.fillText(val, W/2, pad+10);
    if (bc.patch === 'bottom') ctx.fillText(val, W/2, pad+drawH-4);
  }

  // Arrows showing flow direction (for inlet patches)
  const inlet = activeBCs.find(b => b.patch === 'left' || b.type === 'inlet');
  if (inlet) {
    ctx.strokeStyle = 'rgba(255,200,80,.6)';
    ctx.lineWidth = 1.5;
    for (let j = 0; j < 5; j++) {
      const yy = pad + (j+1) * drawH/6;
      ctx.beginPath(); ctx.moveTo(pad+10, yy); ctx.lineTo(pad+40, yy);
      ctx.lineTo(pad+35, yy-4); ctx.moveTo(pad+40, yy); ctx.lineTo(pad+35, yy+4);
      ctx.stroke();
    }
  }

  // Legend
  let legendText = '';
  for (const [type, col] of Object.entries(legend)) {
    legendText += `■ ${type}  `;
  }
  document.getElementById('bc-legend').textContent = legendText || 'No BCs added yet';
}

// ── MESH ──
async function createMesh() {
  const nx = parseInt(document.getElementById('mesh-nx').value);
  const ny = parseInt(document.getElementById('mesh-ny').value);
  const nz = document.getElementById('mesh-dim').value === '3d' ?
    parseInt(document.getElementById('mesh-nz').value) : 1;
  const lx = parseFloat(document.getElementById('dom-x').value);
  const ly = parseFloat(document.getElementById('dom-y').value);
  const lz = document.getElementById('mesh-dim').value === '3d' ?
    parseFloat(document.getElementById('dom-z').value) : 1.0;

  // Progress animation
  const bar = document.getElementById('mesh-prog');
  document.getElementById('mesh-prog-wrap').style.display = 'block';
  let pct = 0;
  const pInterval = setInterval(() => { pct = Math.min(pct+10, 80); bar.style.width = pct+'%'; }, 100);

  log(`Creating mesh: ${nx}×${ny}×${nz}...`);
  setStatus('Creating mesh...');
  try {
    const r = await fetch(`${API}/api/mesh/create`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ nx, ny, nz, domain: [lx, ly, lz] })
    });
    const d = await r.json();
    clearInterval(pInterval); bar.style.width = '100%';
    setTimeout(() => { document.getElementById('mesh-prog-wrap').style.display='none'; bar.style.width='0'; }, 600);

    if (d.status === 'success') {
      currentMesh = d.mesh;
      const cells = nx * ny * nz;
      document.getElementById('mesh-info').innerHTML =
        `Grid: ${nx}×${ny}×${nz}<br>Cells: ${cells.toLocaleString()}<br>dx: ${(lx/nx).toFixed(4)} m<br>dy: ${(ly/ny).toFixed(4)} m`;
      // Update props
      setEl('pp-mesh', `${nx}×${ny}×${nz}`);
      setEl('pp-cells', cells.toLocaleString());
      setEl('st-grid', `${nx}×${ny}×${nz}`);
      setEl('st-cells', cells.toLocaleString());
      setEl('st-dx', (lx/nx).toFixed(4)+' m');
      setEl('st-dy', (ly/ny).toFixed(4)+' m');
      setEl('st-mtype', document.getElementById('mesh-type').value);
      log(`Mesh created: ${cells.toLocaleString()} cells`, 'success');
      setStatus('Mesh OK', 'ok');
      toast('Mesh generated', 'ok');
      updateMeshPreview();
    } else {
      log('Mesh error: ' + d.message, 'error');
      setStatus('Mesh failed', 'er');
    }
  } catch(e) {
    clearInterval(pInterval);
    log('Mesh error: ' + e.message, 'error');
    setStatus('Error', 'er');
  }
}

// ── MESH IMPORT ──
async function importMesh(input) {
  const file = input.files[0];
  if (!file) return;
  const status = document.getElementById('import-status');
  status.textContent = '⏳ Uploading ' + file.name + '...';
  status.style.color = 'var(--txt2)';

  const formData = new FormData();
  formData.append('mesh_file', file);

  try {
    const r = await fetch(`${API}/api/mesh/import`, { method:'POST', body: formData });
    const d = await r.json();
    if (d.status === 'success') {
      status.textContent = '✅ ' + d.message;
      status.style.color = 'var(--green)';
      if (d.nx) {
        document.getElementById('mesh-nx').value = d.nx;
        document.getElementById('mesh-ny').value = d.ny || d.nx;
      }
      log('Mesh imported: ' + file.name, 'success');
      toast('Mesh imported', 'ok');
      updateMeshPreview();
      // Run blockMesh on imported file
      const r2 = await fetch(`${API}/api/mesh/run_blockmesh`, {method:'POST'});
      const d2 = await r2.json();
      if (d2.status === 'success') {
        status.textContent += ' | blockMesh ✅';
        log('blockMesh ran on imported mesh', 'success');
      } else {
        status.textContent += ' | blockMesh ❌ check log';
        log('blockMesh error: ' + d2.message, 'error');
      }
    } else {
      status.textContent = '❌ ' + d.message;
      status.style.color = 'var(--red)';
      log('Import error: ' + d.message, 'error');
    }
  } catch(e) {
    status.textContent = '❌ ' + e.message;
    status.style.color = 'var(--red)';
    log('Import error: ' + e.message, 'error');
  }
  input.value = ''; // reset so same file can be re-uploaded
}

// ── SOLVER ──
function onSolverChange() {
  const v = document.getElementById('solver-type').value;
  const descs = {
    icoFoam:           'Transient laminar incompressible (PISO). Lid-driven cavity benchmark.',
    simpleFoam:        'Steady-state incompressible (SIMPLE). Channel/pipe flow.',
    pisoFoam:          'Transient incompressible (PISO). Pulsating/unsteady flows.',
    pimpleFoam:        'Transient incompressible (PIMPLE). Large time steps.',
    buoyantSimpleFoam: 'Steady natural convection with Boussinesq buoyancy. Hot/cold walls.',
    laplacianFoam:     'Scalar heat diffusion. Solves DT∇²T=0.',
  };
  document.getElementById('solver-desc').textContent = descs[v] || '';
  const isBuoy = v === 'buoyantSimpleFoam';
  const isLap  = v === 'laplacianFoam';
  const isSteady = v === 'simpleFoam' || isBuoy;
  const bf = document.getElementById('buoyant-fields');
  const af = document.getElementById('alpha-field');
  const rf = document.getElementById('relax-fields');
  const rs = document.getElementById('ras-fields');
  if (bf) bf.style.display = isBuoy   ? '' : 'none';
  if (af) af.style.display = isLap    ? '' : 'none';
  if (rf) rf.style.display = isSteady ? '' : 'none';
  const ddt = document.getElementById('ddtScheme');
  if (ddt) ddt.value = isSteady ? 'steadyState' : 'Euler';
}

function onTurbChange() {
  const v = document.getElementById('turbulence').value;
  const rf = document.getElementById('ras-fields');
  if (rf) rf.style.display = v === 'RAS' ? '' : 'none';
}

function _collectSolverParams() {
  const g  = id => { const el=document.getElementById(id); return el?el.value:null; };
  const gn = id => { const el=document.getElementById(id); return el?parseFloat(el.value)||0:0; };
  const gi = id => { const el=document.getElementById(id); return el?parseInt(el.value)||0:0; };
  return {
    nu:gn('nu'), rho:gn('rho'),
    beta:gn('beta'), T_ref:gn('T_ref'), g:gn('g_val'), Cp:gn('Cp'), kappa:gn('kappa'),
    alpha:gn('alpha'),
    turbulence: g('turbulence')||'laminar', ras_model: g('ras_model')||'kEpsilon',
    endTime:gn('endTime'), deltaT:gn('deltaT'),
    writeInterval:gi('writeInterval'), writeControl:g('writeControl')||'timeStep',
    ddtScheme:g('ddtScheme')||'Euler', gradScheme:g('gradScheme')||'Gauss linear',
    divScheme_U:g('divScheme_U')||'Gauss linearUpwind grad(U)',
    p_solver:g('p_solver')||'PCG', p_tolerance:gn('p_tolerance')||1e-6,
    p_relTol:gn('p_relTol')||0.01,
    nCorrectors:gi('nCorrectors')||2, nNonOrthogonalCorrectors:gi('nNonOrthogonalCorrectors')||0,
    relaxation_U:gn('relaxation_U')||0.7, relaxation_p:gn('relaxation_p')||0.3,
    lid_velocity:gn('lid_velocity')||1.0, U_inlet:gn('U_inlet')||1.0,
    inlet_profile:g('inlet_profile')||'uniform',
  };
}

async function createSolver() {
  const type = document.getElementById('solver-type').value;
  const config = _collectSolverParams();
  log(`Configuring ${type}...`);
  try {
    const r = await fetch(`${API}/api/solver/create`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ type, config })
    });
    const d = await r.json();
    if (d.status === 'success') {
      currentSolver = type;
      setEl('pp-solver', type); setEl('st-solver', type); setEl('rp-solver', type);
      log(`${type} configured`, 'success'); setStatus('Solver ready','ok'); toast('Solver ready','ok');
    } else log('Solver error: ' + d.message, 'error');
  } catch(e) { log('Solver error: ' + e.message, 'error'); }
}

// ── BOUNDARY CONDITIONS ──
async function addBC() {
  const patch = document.getElementById('bc-patch').value;
  const type  = document.getElementById('bc-type').value;
  const value = parseFloat(document.getElementById('bc-val').value);

  const locMap = { left:'x_min', right:'x_max', top:'y_max', bottom:'y_min', front:'z_min', back:'z_max' };

  log(`Setting BC: ${patch} = ${type} (${value})`);
  try {
    const r = await fetch(`${API}/api/bc/set`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ patch, type, value, location: locMap[patch] })
    });
    const d = await r.json();
    if (d.status === 'success') {
      // Update local BC list
      activeBCs = activeBCs.filter(b => b.patch !== patch);
      activeBCs.push({ patch, type, value });
      renderBCTable();
      updateBCPreview();
      setEl('pp-bc', activeBCs.length);
      log(`BC set: ${patch} → ${type} = ${value}`, 'success');
      toast(`BC: ${patch} set`, 'ok');
    } else {
      log('BC error: ' + d.message, 'error');
    }
  } catch(e) { log('BC error: ' + e.message, 'error'); }
}

function renderBCTable() {
  const tbody = document.getElementById('bc-list');
  tbody.innerHTML = '';
  for (const bc of activeBCs) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${bc.patch}</td><td>${bc.type}</td><td>${bc.type==='dirichlet'||bc.type==='inlet'?bc.value:'—'}</td>
      <td><button class="bc-del" onclick="removeBC('${bc.patch}')">✕</button></td>`;
    tbody.appendChild(tr);
  }
}
function removeBC(patch) {
  activeBCs = activeBCs.filter(b => b.patch !== patch);
  renderBCTable();
  updateBCPreview();
  setEl('pp-bc', activeBCs.length);
}

async function initFields() {
  const T = parseFloat(document.getElementById('T-init').value);
  const p = parseFloat(document.getElementById('p-init').value);
  const ux = parseFloat(document.getElementById('Ux').value);
  const uy = parseFloat(document.getElementById('Uy').value);
  try {
    const r = await fetch(`${API}/api/fields/initialize`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ T, p, U:[ux,uy,0] })
    });
    const d = await r.json();
    if (d.status === 'success') { log('Fields initialized', 'success'); toast('Fields initialized','ok'); }
    else log('Init error: ' + d.message, 'error');
  } catch(e) { log('Init error: ' + e.message, 'error'); }
}

// ── SIMULATION ──
async function runSimulation() {
  if (!currentMesh)  { log('Create mesh first', 'error');   toast('Need mesh first','er'); return; }
  if (!currentSolver){ log('Create solver first', 'error'); toast('Need solver first','er'); return; }

  const maxIters = parseInt(document.getElementById('max-iters').value);
  const tolerance = parseFloat(document.getElementById('tolerance').value);

  // Disable run, enable stop
  document.getElementById('btn-run').disabled = true;
  document.getElementById('btn-stop').disabled = false;
  document.getElementById('run-btn').disabled = true;
  document.getElementById('stop-btn').disabled = false;
  document.getElementById('run-prog-sec').style.display = 'block';

  setStatus('Running simulation...', '');
  setEl('rp-status', 'running');
  setEl('mon-status', 'running');
  log(`Running ${currentSolver}: ${maxIters} iters...`);
  startTime = Date.now();
  residualHistory = {};

  // Progress animation (fake, since backend is synchronous)
  const progBar = document.getElementById('run-prog');
  let fakeP = 0;
  const fakeTimer = setInterval(() => {
    fakeP = Math.min(fakeP + 1, 90);
    progBar.style.width = fakeP + '%';
  }, maxIters * 3);

  // Monitor timer
  monTimer = setInterval(async () => {
    try {
      const sr = await fetch(`${API}/api/simulate/status`);
      const sd = await sr.json();
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      setEl('monitor-iteration', sd.iterations || 0);
      setEl('mon-iter', sd.iterations || 0);
      setEl('mon-time', elapsed + 's');
      setEl('rp-iter', sd.iterations || 0);
      setEl('rp-time', elapsed + 's');
      if (sd.residuals) {
        const r = sd.residuals;
        const rval = r.T ?? r.U ?? r.p ?? 0;
        if (rval !== null) {
          const rv = typeof rval === 'number' ? rval.toExponential(2) : '—';
          setEl('rp-res', rv);
          setEl('mon-res', rv);
          setEl('monitor-residual-t', rv);
          // Accumulate for chart
          const key = Object.keys(sd.residuals).find(k => sd.residuals[k] != null);
          if (key) {
            if (!residualHistory[key]) residualHistory[key] = [];
            residualHistory[key].push(rval);
            drawResidualChart();
            drawMiniResidual();
          }
        }
      }
    } catch(e) {}
  }, 500);

  try {
    // Collect all solver params to send alongside run params
    const solverParams = _collectSolverParams ? _collectSolverParams() : {};
    const r = await fetch(`${API}/api/simulate/run`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ max_iters: maxIters, tolerance, ...solverParams })
    });
    const d = await r.json();

    clearInterval(fakeTimer);
    clearInterval(monTimer);
    monTimer = null;
    progBar.style.width = '100%';
    setTimeout(() => { document.getElementById('run-prog-sec').style.display='none'; progBar.style.width='0'; }, 800);

    if (d.status === 'success') {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      log(`Simulation done: ${d.iterations} iters, converged=${d.converged}, ${elapsed}s`, 'success');
      setStatus(`Done: ${d.iterations} iters`, 'ok');
      toast('Simulation complete!', 'ok');
      setEl('rp-status', d.converged ? 'converged ✓' : 'done');
      setEl('mon-status', d.converged ? 'converged' : 'done');
      setEl('st-iters', d.iterations);
      setEl('st-conv', d.converged ? 'Yes ✓' : 'No');

      // Store final residuals
      if (d.residuals) {
        for (const [k, v] of Object.entries(d.residuals)) {
          if (!residualHistory[k]) residualHistory[k] = [];
          residualHistory[k].push(...v);
        }
        drawResidualChart();
        drawMiniResidual();

        // Update stat panel
        const last = d.residuals;
        if (last.T && last.T.length) setEl('st-resT', last.T[last.T.length-1].toExponential(3));
        if (last.U && last.U.length) setEl('st-resU', last.U[last.U.length-1].toExponential(3));
      }

      // Auto-visualize
      await visualizeField();

    } else {
      log('Simulation error: ' + d.message, 'error');
      setStatus('Simulation failed', 'er');
      toast('Simulation failed', 'er');
    }
  } catch(e) {
    clearInterval(fakeTimer);
    clearInterval(monTimer);
    log('Run error: ' + e.message, 'error');
    setStatus('Error', 'er');
  } finally {
    document.getElementById('btn-run').disabled = false;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('run-btn').disabled = false;
    document.getElementById('stop-btn').disabled = true;
  }
}

function stopSim() {
  if (monTimer) { clearInterval(monTimer); monTimer = null; }
  log('Simulation stop requested', 'warn');
  document.getElementById('btn-stop').disabled = true;
  document.getElementById('btn-run').disabled = false;
}

// ── VISUALIZATION ──
function updateFieldChips(fields) {
  // Dynamically update field chips based on what solver actually wrote
  const chipRow = document.querySelector('.chip-row');
  if (!chipRow) return;
  chipRow.innerHTML = '';
  const labels = { U:'U — Veloc', p:'p — Press', T:'T — Temp',
    k:'k — TKE', epsilon:'ε — Dissip', omega:'ω — Spec. Diss',
    p_rgh:'p_rgh — Hydro', nut:'νt — Turb.Visc' };
  fields.forEach(f => {
    const chip = document.createElement('div');
    chip.className = 'chip' + (f === activeField ? ' on' : '');
    chip.id = 'chip-' + f;
    chip.textContent = labels[f] || f;
    chip.onclick = () => selectField(f);
    chipRow.appendChild(chip);
  });
}

function selectField(f) {
  activeField = f;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
  const chip = document.getElementById('chip-' + f);
  if (chip) chip.classList.add('on');
  setEl('cb-field', f + (f==='T'?' [°C]':f==='p'?' [Pa]':' [m/s]'));
  visualizeField();
}

async function visualizeField() {
  try {
    // First fetch available fields so we show correct chips
    try {
      const fr = await fetch(`${API}/api/results/fields`);
      const fd = await fr.json();
      if (fd.fields && fd.fields.length > 0) {
        updateFieldChips(fd.fields);
        // If active field not available, pick first one
        if (!fd.fields.includes(activeField)) {
          activeField = fd.fields[0];
          selectField(activeField);
        }
      }
    } catch(e) {}

    const r = await fetch(`${API}/api/results/heatmap3d?field=${activeField}`);
    const d = await r.json();
    if (!d || d.status !== 'success' || !d.heatmap) {
      log('Viz error: ' + (d.message || 'no data'), 'error');
      return;
    }
    const hm = d.heatmap;
    lastHeatmap = hm;

    const shape = hm.shape || [1, hm.data.length, (hm.data[0]||[]).length];
    let [nz, ny, nx] = shape;

    // Always extrude 2D to 3D for visualization (8 layers)
    let data3d = hm.data;
    const EXTRUDE = 8;
    if (nz === 1) {
      data3d = [];
      for (let k = 0; k < EXTRUDE; k++) data3d.push(hm.data[0].map(r => [...r]));
      nz = EXTRUDE;
    }
    const hm3d = { ...hm, data: data3d, shape: [nz, ny, nx], is_3d: true };

    // ── Center 3D viewport ──
    viz3d = getViz3d('canvas-3d');
    viz3d.render3DHeatmap(hm3d, { nx, ny, nz });
    const sliceEl = document.getElementById('slice-bar');
    sliceEl.classList.add('show');
    const maxSl = nz - 1;
    document.getElementById('slice-idx').max   = maxSl;
    document.getElementById('slice-idx').value = Math.floor(maxSl / 2);
    document.getElementById('slice-disp').textContent = Math.floor(maxSl / 2);
    viz3d.sliceIndex = Math.floor(maxSl / 2);

    // ── Right panel 3D mini ──
    rightViz3d = getViz3d('right-canvas-3d');
    rightViz3d.render3DHeatmap(hm3d, { nx, ny, nz });

    // ── 2D heatmap ──
    const hm2d = { data: hm.data[0], min: hm.min, max: hm.max };
    renderHeatmap(hm2d);
    renderHeatmapTo('right-canvas-2d', hm2d);

    // ── Colorbar ──
    drawColorbar(hm.min, hm.max);
    setEl('cb-max', hm.max.toFixed(2));
    setEl('cb-min', hm.min.toFixed(2));

    // ── Stats ──
    setEl('st-field', activeField);
    setEl('st-min', hm.min.toFixed(4));
    setEl('st-max', hm.max.toFixed(4));
    setEl('st-range', (hm.max - hm.min).toFixed(4));
    setEl('pp-tmin', hm.min.toFixed(2));
    setEl('pp-tmax', hm.max.toFixed(2));

    // Flat array for mean/std
    const flat = hm.data.flat(Infinity).filter(v => isFinite(v));
    const mean = flat.reduce((a,b) => a+b, 0) / flat.length;
    const std  = Math.sqrt(flat.reduce((a,b) => a+(b-mean)**2, 0) / flat.length);
    setEl('st-mean', mean.toFixed(4));
    setEl('st-std', std.toFixed(4));

    log(`${activeField}: min=${hm.min.toFixed(2)} max=${hm.max.toFixed(2)} mean=${mean.toFixed(2)}`, 'success');

    // Mark badges
    document.getElementById('rbdg-viz').className = 'rnav-badge ok';
    document.getElementById('rbdg-stats').className = 'rnav-badge ok';

  } catch(e) {
    log('Visualization error: ' + e.message, 'error');
  }
}

// ── Colormap ──
function getColormapFn() {
  const cm = document.getElementById('colormap')?.value || 'rainbow';
  return (t) => {
    t = Math.max(0, Math.min(1, t));
    if (cm === 'rainbow')  return `hsl(${(1-t)*240},100%,${40+t*15}%)`;
    if (cm === 'coolwarm') {
      const r = t<.5 ? Math.round(130+t*250) : 255;
      const b = t>.5 ? Math.round(255-(t-.5)*500) : 255;
      const g = Math.round(50 + t*50);
      return `rgb(${r},${g},${b})`;
    }
    if (cm === 'turbo') {
      const r = Math.round(255 * Math.max(0,Math.min(1, t < .5 ? 2*t : 2-2*t + .5)));
      const g = Math.round(255 * Math.max(0,Math.min(1, t < .25 ? 4*t : t<.75 ? 1 : 4-4*t)));
      const b = Math.round(255 * Math.max(0,Math.min(1, t < .5 ? 1-2*t : 0)));
      return `rgb(${r},${g},${b})`;
    }
    // viridis approx
    const r = Math.round(255*(0.267+0.005*t+2.33*t*t-1.52*t*t*t));
    const g = Math.round(255*(0.005+1.1*t-0.3*t*t));
    const b = Math.round(255*(0.33+0.78*t-0.78*t*t));
    return `rgb(${Math.max(0,Math.min(255,r))},${Math.max(0,Math.min(255,g))},${Math.max(0,Math.min(255,b))})`;
  };
}

function renderHeatmapTo(canvasId, hm) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let data = hm.data;
  if (Array.isArray(data[0]) && Array.isArray(data[0][0])) data = data[Math.floor(data.length/2)];
  const rows = data.length, cols = data[0]?.length || 0;
  if (!cols) return;
  canvas.width = canvas.offsetWidth || 260;
  canvas.height = canvas.offsetHeight || 180;
  const cw = canvas.width/cols, ch = canvas.height/rows;
  const range = hm.max - hm.min;
  const colorFn = getColormapFn();
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const v = data[i][j];
      const norm = isFinite(v) && range > 1e-6 ? (v-hm.min)/range : .5;
      ctx.fillStyle = colorFn(norm);
      ctx.fillRect(j*cw, i*ch, cw+1, ch+1);
    }
  }
}

function drawColorbar(min, max) {
  const canvas = document.getElementById('cb-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const H = 150, W = 18;
  canvas.width = W; canvas.height = H;
  const colorFn = getColormapFn();
  for (let i = 0; i < H; i++) {
    ctx.fillStyle = colorFn(1 - i/H);
    ctx.fillRect(0, i, W, 1);
  }
}

// ── Residual Charts ──
function drawResidualChart() {
  const canvas = document.getElementById('residual-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.offsetWidth || 500;
  const H = canvas.height = canvas.offsetHeight || 200;
  ctx.fillStyle = '#080b0e'; ctx.fillRect(0,0,W,H);

  const colors = { T:'#ff6b35', U:'#32d74b', p:'#64d2ff' };
  const pad = 40;

  ctx.strokeStyle = 'rgba(54,60,68,.5)'; ctx.lineWidth = .5;
  for (let i=0;i<5;i++) {
    const y = pad + (H-2*pad)*i/4;
    ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(W-pad,y); ctx.stroke();
  }

  let hasData = false;
  for (const [key, vals] of Object.entries(residualHistory)) {
    if (!vals.length) continue;
    hasData = true;
    const maxV = Math.max(...vals.filter(isFinite)) || 1;
    const minV = Math.min(...vals.filter(v=>v>0&&isFinite(v))) || 1e-10;
    ctx.strokeStyle = colors[key] || '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    vals.forEach((v, i) => {
      const x = pad + (W-2*pad)*i/Math.max(1, vals.length-1);
      const logV = Math.log10(Math.max(v, minV));
      const logMax = Math.log10(maxV), logMin = Math.log10(minV);
      const y = H - pad - (H-2*pad)*(logV-logMin)/(logMax-logMin+1e-10);
      i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    });
    ctx.stroke();

    // Label
    ctx.fillStyle = colors[key]||'#fff';
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.fillText(key, W-pad-30, pad+12+Object.keys(residualHistory).indexOf(key)*14);
  }

  if (!hasData) {
    ctx.fillStyle = 'rgba(100,120,140,.5)';
    ctx.font = '12px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('No residual data — run simulation', W/2, H/2);
  }

  // Axes
  ctx.strokeStyle = 'rgba(54,60,68,.8)'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad,pad); ctx.lineTo(pad,H-pad); ctx.lineTo(W-pad,H-pad); ctx.stroke();
  ctx.fillStyle = 'rgba(100,120,140,.6)'; ctx.font = '9px JetBrains Mono,monospace'; ctx.textAlign='center';
  ctx.fillText('Iterations', W/2, H-6);
  ctx.save(); ctx.translate(12, H/2); ctx.rotate(-Math.PI/2);
  ctx.fillText('Residual (log)', 0, 0); ctx.restore();
}

function drawMiniResidual() {
  const canvas = document.getElementById('mini-residual');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.offsetWidth || 260;
  const H = canvas.height = 100;
  ctx.fillStyle = '#080b0e'; ctx.fillRect(0,0,W,H);
  const colors = { T:'#ff6b35', U:'#32d74b', p:'#64d2ff' };
  const pad = 8;
  for (const [key, vals] of Object.entries(residualHistory)) {
    if (!vals || vals.length < 2) continue;
    const maxV = Math.max(...vals.filter(isFinite)) || 1;
    const minV = Math.min(...vals.filter(v=>v>0&&isFinite(v))) || 1e-10;
    ctx.strokeStyle = colors[key] || '#fff'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    vals.forEach((v, i) => {
      const x = pad + (W-2*pad)*i/Math.max(1,vals.length-1);
      const logV = Math.log10(Math.max(v,minV));
      const y = H-pad-(H-2*pad)*(logV-Math.log10(minV))/(Math.log10(maxV)-Math.log10(minV)+1e-10);
      i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    });
    ctx.stroke();
  }
}

// ── Slice controls ──
function setAxis(a) {
  ['x','y','z'].forEach(ax => document.getElementById('ax-'+ax).classList.toggle('on', ax===a));
  const si = parseInt(document.getElementById('slice-idx').value) || 0;
  // Update max for new axis
  const info = viz3d?._lastInfo;
  if (info) {
    const maxIdx = a==='z' ? info.nz-1 : a==='y' ? info.ny-1 : info.nx-1;
    document.getElementById('slice-idx').max = maxIdx;
    document.getElementById('slice-idx').value = Math.floor(maxIdx/2);
    document.getElementById('slice-disp').textContent = Math.floor(maxIdx/2);
  }
  viz3d?.setSlice(a, parseInt(document.getElementById('slice-idx').value));
  rightViz3d?.setSlice(a, parseInt(document.getElementById('slice-idx').value));
}
function onSlice(v) {
  document.getElementById('slice-disp').textContent = v;
  const axis = viz3d?.sliceAxis || 'z';
  viz3d?.setSlice(axis, parseInt(v));
  rightViz3d?.setSlice(axis, parseInt(v));
}
function setRenderMode(mode) {
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('on'));
  const btn = document.getElementById('mode-' + mode);
  if (btn) btn.classList.add('on');
  viz3d?.setMode(mode);
  rightViz3d?.setMode(mode);
  // Show slice controls only in slice mode
  document.getElementById('slice-bar').classList.toggle('show', mode==='slice');
}
function resetCamera() { viz3d?.resetCamera(); }
function setViewAngle(a) { viz3d?.setViewAngle(a); }

// ── Export ──
async function exportResults(fmt) {
  log(`Exporting ${fmt.toUpperCase()}...`);
  try {
    const r = await fetch(`${API}/api/results/export`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ format: fmt })
    });
    const d = await r.json();
    if (d.status === 'success') { log(`Exported: ${d.file}`, 'success'); toast(`Exported ${fmt.toUpperCase()}`, 'ok'); }
    else log('Export error: ' + d.message, 'error');
  } catch(e) { log('Export error: ' + e.message, 'error'); }
}

async function saveCase() {
  const name = document.getElementById('case-name-inp').value || 'myCase';
  document.getElementById('case-name').textContent = name;
  try {
    const r = await fetch(`${API}/api/case/save`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name })
    });
    const d = await r.json();
    if (d.status === 'success') { log(`Case saved: ${name}`, 'success'); toast('Case saved', 'ok'); }
    else log('Save error: ' + d.message, 'error');
  } catch(e) { log('Save error: ' + e.message, 'error'); }
}

async function loadCase() {
  const name = document.getElementById('case-name-inp').value;
  if (!name) { toast('Enter case name', 'er'); return; }
  try {
    const r = await fetch(`${API}/api/case/load`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name })
    });
    const d = await r.json();
    if (d.status === 'success') { log(`Case loaded: ${name}`, 'success'); toast('Case loaded', 'ok'); }
    else log('Load error: ' + d.message, 'error');
  } catch(e) { log('Load error: ' + e.message, 'error'); }
}

// ── Utilities ──
function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
  updateMeshPreview();
  updateBCPreview();
  // Check OpenFOAM status
  try {
    const r = await fetch(`${API}/api/openfoam/info`);
    const d = await r.json();
    if (d.found || (d.openfoam && d.openfoam !== 'NOT FOUND')) {
      log('OpenFOAM found: ' + d.openfoam, 'success');
      setStatus('OpenFOAM ready', 'ok');
    } else {
      log('⚠ OpenFOAM NOT found — install OpenFOAM on the server', 'warn');
      setStatus('OpenFOAM missing', 'er');
    }
  } catch(e) { log('Backend offline: ' + e.message, 'error'); }
  log('OpenFOAM Clone v2.0 ready', 'success');
  log('Step 1: Set mesh → 2: Set solver → 3: Add BCs → 4: Run');
  // Resize handlers
  window.addEventListener('resize', () => {
    updateMeshPreview();
    updateBCPreview();
    if (viz3d) viz3d.onResize();
    if (rightViz3d) rightViz3d.onResize();
    drawResidualChart();
    drawMiniResidual();
  });
});
