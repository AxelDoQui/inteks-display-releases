// Panel lateral de SignalOS Pro — corre dentro del iframe inyectado en la página.
let selectedRows = [];
let detectedRows = [];
let savedModules = [];   // módulos de divisas que ya existen en el admin
let serverUrl = 'http://localhost';   // puerto 80 por defecto (SignalOS); configurable
let apiToken = '';                    // token de API (Ajustes del admin); requerido si hay contraseña
let screens = [];

// Cabeceras con el token de API para los endpoints protegidos del servidor.
function authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  if (apiToken) h['X-SignalOS-Token'] = apiToken;
  return h;
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  setupEventListeners();
  await checkConnection();
  await loadScreens();
  await loadModules();
  // Pedir a la página que escanee (el iframe ya está listo)
  window.parent.postMessage({ type: 'SIGNALOS_RESCAN' }, '*');
});

async function loadConfig() {
  try {
    const data = await chrome.storage.local.get(['serverUrl', 'apiToken']);
    if (data.serverUrl) serverUrl = data.serverUrl;
    if (data.apiToken) apiToken = data.apiToken;
  } catch (e) {}
  document.getElementById('server-url').value = serverUrl;
  document.getElementById('api-token').value = apiToken;
}

async function checkConnection() {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-txt');
  try {
    const r = await fetch(`${serverUrl}/api/info`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      const d = await r.json();
      dot.className = 'dot online';
      txt.textContent = `● puerto ${d.port}`;
      return true;
    }
  } catch (e) {}
  dot.className = 'dot offline';
  txt.textContent = '○ sin conexión';
  return false;
}

async function loadScreens() {
  const sel = document.getElementById('screen-select');
  sel.innerHTML = '<option value="">Todas las pantallas</option>';  // reset siempre
  try {
    const r = await fetch(`${serverUrl}/api/screens`, { headers: authHeaders(), signal: AbortSignal.timeout(3000) });
    if (!r.ok) {  // 401 (falta token) u otro error: NO poblar con basura
      if (r.status === 401) {
        document.getElementById('status-txt').textContent = '● falta token';
      }
      return;
    }
    const data = await r.json();
    if (!data || typeof data !== 'object' || data.auth_required) return;
    // Solo claves cuyo valor sea un objeto-pantalla (descarta {error,auth_required})
    screens = Object.keys(data).filter(id => id !== 'admin' && data[id] && typeof data[id] === 'object');
    screens.forEach(id => {
      const opt = document.createElement('option');
      opt.value = id; opt.textContent = id;
      sel.appendChild(opt);
    });
  } catch (e) {}
}

// ── Módulos ya guardados en el admin ───────────────────────────────────────
// El servidor no necesita nada nuevo: /api/content ya devuelve todo el
// contenido y acepta el token de la extensión.
async function loadModules() {
  const sel = document.getElementById('module-select');
  sel.innerHTML = '<option value="">Empezar de cero</option>';
  savedModules = [];
  let data;
  try {
    const r = await fetch(`${serverUrl}/api/content`, { headers: authHeaders(), signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    data = await r.json();
  } catch (e) { return; }

  // El mismo módulo vive en la librería y copiado en cada playlist. Se indexa
  // por id y se anota en qué pantallas aparece, solo para etiquetarlo.
  const porId = new Map();
  const anota = (item, pantalla) => {
    if (!item || item.type !== 'fx') return;
    const id = item.id || item.title || 'fx';
    if (!porId.has(id)) porId.set(id, { id, title: item.title || 'Tipos de cambio', rows: item.rows || [], screens: [] });
    if (pantalla) porId.get(id).screens.push(pantalla);
  };
  (data.items || []).forEach(i => anota(i, null));
  Object.entries(data.screens || {}).forEach(([sid, cfg]) => (cfg.playlist || []).forEach(i => anota(i, sid)));

  savedModules = [...porId.values()];
  savedModules.forEach(m => {
    const o = document.createElement('option');
    o.value = m.id;
    const donde = m.screens.length ? ` — ${m.screens.join(', ')}` : ' — sin asignar';
    o.textContent = `${m.title} (${m.rows.length})${donde}`;
    sel.appendChild(o);
  });
}

// Carga las filas del módulo elegido como punto de partida. Se guarda la tasa
// original en `was` para poder enseñar de dónde a dónde ha cambiado.
function pickModule() {
  const id = document.getElementById('module-select').value;
  const m = savedModules.find(x => x.id === id);
  selectedRows = m
    ? m.rows.map(r => ({ ...r, was: r.rate, changed: false, missing: true }))
    : [];
  applyDetectedToSelected();
  renderSelected(); renderDetected(); updateSendBtn();
}

// Empareja por código lo detectado en la página con lo que ya tienes cargado.
function applyDetectedToSelected() {
  selectedRows.forEach(r => {
    const det = detectedRows.find(d => (d.code || '').toUpperCase() === (r.code || '').toUpperCase());
    if (!det) { r.missing = true; return; }
    r.missing = false;
    r.changed = String(det.rate) !== String(r.was);
    r.rate = det.rate;
  });
}

// Divisas detectadas enviadas por content.js
window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'SIGNALOS_DETECTED') {
    detectedRows = e.data.rows || [];
    applyDetectedToSelected();
    renderDetected(); renderSelected(); updateSendBtn();
  }
});

function renderDetected() {
  const list = document.getElementById('detected-list');
  if (!detectedRows.length) {
    list.innerHTML = '<div class="empty-msg">No se detectaron divisas en esta página.<br>Usa "Añadir manualmente".</div>';
    return;
  }
  list.innerHTML = '';
  detectedRows.forEach((row) => {
    const isSel = selectedRows.find(r => r.code === row.code);
    const el = document.createElement('div');
    el.className = 'fx-row' + (isSel ? ' selected' : '');
    el.innerHTML = `
      <input type="checkbox" ${isSel ? 'checked' : ''}>
      <span class="fx-flag">${row.flag}</span>
      <div class="fx-info"><div class="fx-code">${row.code}</div><div class="fx-name">${row.country}</div></div>
      <input type="text" class="fx-rate-input" value="${row.rate}">`;
    const chk = el.querySelector('input[type=checkbox]');
    const rateInp = el.querySelector('.fx-rate-input');
    chk.addEventListener('change', (ev) => {
      if (ev.target.checked) addToSelected({ ...row, rate: rateInp.value });
      else removeFromSelected(row.code);
    });
    rateInp.addEventListener('input', (ev) => {
      const s = selectedRows.find(r => r.code === row.code);
      if (s) s.rate = ev.target.value;
      row.rate = ev.target.value;
    });
    list.appendChild(el);
  });
}

function addToSelected(row) {
  if (!selectedRows.find(r => r.code === row.code)) selectedRows.push({ ...row });
  renderSelected(); updateSendBtn();
}
function removeFromSelected(code) {
  selectedRows = selectedRows.filter(r => r.code !== code);
  renderSelected(); updateSendBtn(); renderDetected();
}
function renderSelected() {
  const list = document.getElementById('selected-list');
  document.getElementById('selected-count').textContent = selectedRows.length;
  if (!selectedRows.length) { list.innerHTML = '<div class="empty-msg">Elige un módulo arriba o selecciona divisas</div>'; return; }
  list.innerHTML = '';
  const cargado = !!document.getElementById('module-select').value;
  selectedRows.forEach((row) => {
    const el = document.createElement('div');
    el.className = 'fx-row' + (row.changed ? ' changed' : '') + (cargado && row.missing ? ' missing' : '');
    // Cuando la página ha traído una tasa distinta, se enseña la anterior
    // tachada: publicar cotizaciones a ciegas es justo lo que hay que evitar.
    const was = row.changed ? `<span class="fx-was">${row.was}</span>` : '';
    el.innerHTML = `
      <span class="fx-flag">${row.flag}</span>
      <div class="fx-info"><div class="fx-code">${row.code}</div><div class="fx-name">${row.country}</div></div>
      ${was}
      <input type="text" class="fx-rate-input" value="${row.rate}"${cargado && row.missing ? ' title="No aparece en esta página; se mantiene la tasa guardada"' : ''}>
      <button class="fx-remove" title="Quitar">&times;</button>`;
    el.querySelector('.fx-rate-input').addEventListener('input', (ev) => {
      const r = selectedRows.find(r => r.code === row.code);
      if (r) { r.rate = ev.target.value; r.changed = String(r.rate) !== String(r.was); }
    });
    el.querySelector('.fx-remove').addEventListener('click', () => removeFromSelected(row.code));
    list.appendChild(el);
  });
  if (cargado) {
    const n = selectedRows.filter(r => r.changed).length;
    const sin = selectedRows.filter(r => r.missing).length;
    const hint = document.createElement('div');
    hint.className = 'fx-hint';
    hint.textContent = `${n} tasa(s) actualizadas desde esta página` +
      (sin ? ` · ${sin} sin dato aquí, conservan la guardada` : '');
    list.appendChild(hint);
  }
}
function updateSendBtn() { document.getElementById('send-btn').disabled = selectedRows.length === 0; }

async function sendToSignalOS() {
  const btn = document.getElementById('send-btn');
  const screenId = document.getElementById('screen-select').value;
  btn.textContent = 'Enviando...'; btn.disabled = true;
  const payload = {
    rows: selectedRows.map(r => ({ flag: r.flag, country: r.country, currency: r.currency, code: r.code, rate: r.rate })),
    screen_ids: screenId ? [screenId] : []
  };
  try {
    const r = await fetch(`${serverUrl}/api/fx-update`, {
      method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(payload)
    });
    if (r.status === 401) { const e = new Error('auth'); e.auth = true; throw e; }
    const d = await r.json();
    if (d.ok) {
      btn.textContent = `✓ Actualizado (${d.updated_screens.length} pant.)`;
      btn.style.background = 'var(--success)';
      document.getElementById('last-update').textContent =
        'Última: ' + new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
      // Lo publicado pasa a ser la nueva base: sin esto seguiría marcando como
      // "cambiada" una tasa que el servidor ya tiene guardada.
      selectedRows.forEach(r => { r.was = r.rate; r.changed = false; });
      renderSelected();
      loadModules();
      setTimeout(() => { btn.textContent = 'Actualizar SignalOS'; btn.style.background = ''; updateSendBtn(); }, 2000);
    } else { throw new Error(d.error || 'Error'); }
  } catch (e) {
    btn.textContent = e && e.auth ? '✗ Falta el token de API' : '✗ Error — reintentar';
    btn.style.background = 'var(--danger)';
    setTimeout(() => { btn.textContent = 'Actualizar SignalOS'; btn.style.background = ''; btn.disabled = false; }, 3000);
  }
}

function addManual() {
  const flag = document.getElementById('m-flag').value.trim();
  const code = document.getElementById('m-code').value.trim().toUpperCase();
  const rate = document.getElementById('m-rate').value.trim();
  if (!code || !rate) return;
  const known = window.SignalosParser && window.SignalosParser.CODE_MAP[code];
  addToSelected({
    flag: (known && known.flag) || flag || '🏳',
    country: (known && known.country) || code,
    currency: (known && known.currency) || code,
    code, rate
  });
  document.getElementById('m-flag').value = '';
  document.getElementById('m-code').value = '';
  document.getElementById('m-rate').value = '';
  document.getElementById('m-code').focus();
}

async function saveConfig() {
  serverUrl = document.getElementById('server-url').value.trim().replace(/\/+$/, '');
  apiToken = document.getElementById('api-token').value.trim();
  try { await chrome.storage.local.set({ serverUrl, apiToken }); } catch (e) {}
  await checkConnection(); await loadScreens(); await loadModules();
}

function setupEventListeners() {
  document.getElementById('send-btn').addEventListener('click', sendToSignalOS);
  document.getElementById('m-add').addEventListener('click', addManual);
  document.getElementById('save-config').addEventListener('click', saveConfig);
  document.getElementById('module-select').addEventListener('change', pickModule);
  document.getElementById('rescan-btn').addEventListener('click', () => window.parent.postMessage({ type: 'SIGNALOS_RESCAN' }, '*'));
  document.getElementById('close-btn').addEventListener('click', () => window.parent.postMessage({ type: 'SIGNALOS_CLOSE' }, '*'));
  ['m-flag', 'm-code', 'm-rate'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') addManual(); });
  });
}

setInterval(checkConnection, 30000);
