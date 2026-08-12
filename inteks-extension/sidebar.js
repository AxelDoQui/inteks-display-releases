// Panel lateral de InTeks Display — corre dentro del iframe inyectado en la página.
let selectedRows = [];
let savedModules = [];   // módulos de divisas que ya existen en el admin
let serverUrl = 'http://localhost';   // puerto 80 por defecto (InTeks Display); configurable
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
// original en `was` para poder enseñar de dónde a dónde ha cambiado si se edita.
function pickModule() {
  const id = document.getElementById('module-select').value;
  const m = savedModules.find(x => x.id === id);
  selectedRows = m ? m.rows.map(r => ({ ...r, was: r.rate, changed: false })) : [];
  renderSelected(); updateSendBtn();
}

// ── Selector de país/moneda, con buscador — mismo comportamiento que el de
// admin.html (fxPickerOptions/fxFilterOptions viven en parser.js, duplicadas
// de admin.html; ver tests/fx-countries-sync.test.js). Sin esto, la única
// forma de añadir una divisa era escribir el código de memoria a mano.
let fxComboOpts = [], fxComboIdx = -1;

function fxOptions() {
  return (window.SignalosParser && window.SignalosParser.fxPickerOptions)
    ? window.SignalosParser.fxPickerOptions() : [];
}

function renderFxCombo() {
  const inp = document.getElementById('fx-country-search');
  const list = document.getElementById('fx-country-list');
  if (!inp || !list || !window.SignalosParser) return;
  fxComboOpts = window.SignalosParser.fxFilterOptions(fxOptions(), inp.value);
  if (fxComboIdx >= fxComboOpts.length) fxComboIdx = fxComboOpts.length - 1;
  list.innerHTML = '';
  if (!fxComboOpts.length) {
    list.innerHTML = '<div class="empty-msg">Ningún país coincide</div>';
    return;
  }
  fxComboOpts.forEach((o, i) => {
    const yaEsta = selectedRows.some(r => r.code === o.code && r.country === o.country);
    const el = document.createElement('div');
    el.className = 'fx-combo-item' + (i === fxComboIdx ? ' active' : '');
    el.innerHTML = `<span class="fx-flag">${window.SignalosParser.isoToEmoji(o.flag)}</span>
      <span class="fx-combo-info">${o.country} <span class="fx-combo-currency">— ${o.currency}</span></span>
      <span class="fx-combo-code">${o.code}</span>
      ${yaEsta ? '<span class="fx-combo-check" title="ya está en la lista">✓</span>' : ''}`;
    el.addEventListener('mousedown', (e) => { e.preventDefault(); pickFxCombo(o); });
    el.addEventListener('mouseenter', () => { fxComboIdx = i; marcarFxCombo(); });
    list.appendChild(el);
  });
}

function marcarFxCombo() {
  const list = document.getElementById('fx-country-list');
  if (!list) return;
  [...list.children].forEach((el, i) => el.classList.toggle('active', i === fxComboIdx));
  const act = list.children[fxComboIdx];
  if (act) act.scrollIntoView({ block: 'nearest' });
}

function abrirFxCombo() {
  const list = document.getElementById('fx-country-list');
  if (!list) return;
  renderFxCombo();
  list.style.display = '';
}
function cerrarFxCombo() {
  const list = document.getElementById('fx-country-list');
  if (list) list.style.display = 'none';
  fxComboIdx = -1;
}

// Añade la opción elegida y deja el foco en su tasa, que es lo único que falta.
function pickFxCombo(o) {
  const dup = selectedRows.some(r => r.code === o.code && r.country === o.country);
  if (dup) { cerrarFxCombo(); return; }
  addToSelected({ flag: window.SignalosParser.isoToEmoji(o.flag), country: o.country, currency: o.currency, code: o.code, rate: '' });
  const inp = document.getElementById('fx-country-search');
  if (inp) inp.value = '';
  cerrarFxCombo();
  const inputs = document.querySelectorAll('#selected-list .fx-rate-input');
  if (inputs.length) inputs[inputs.length - 1].focus();
}

// Dos entradas son la misma fila si coinciden PAÍS y código: varios países
// comparten moneda (varios usan USD) y cada uno es una fila válida a la vez.
function addToSelected(row) {
  if (selectedRows.some(r => r.code === row.code && r.country === row.country)) return;
  selectedRows.push({ agent: '', ...row });
  renderSelected(); updateSendBtn();
}
function removeFromSelected(row) {
  selectedRows = selectedRows.filter(r => r !== row);
  renderSelected(); updateSendBtn();
}
function renderSelected() {
  const list = document.getElementById('selected-list');
  document.getElementById('selected-count').textContent = selectedRows.length;
  if (!selectedRows.length) { list.innerHTML = '<div class="empty-msg">Busca y añade divisas arriba</div>'; return; }
  list.innerHTML = '';
  selectedRows.forEach((row) => {
    const el = document.createElement('div');
    el.className = 'fx-row' + (row.changed ? ' changed' : '');
    // Cuando se edita la tasa a mano, se enseña la anterior tachada: publicar
    // una cifra sin darse cuenta de que cambió es justo lo que hay que evitar.
    const was = row.changed ? `<span class="fx-was">${row.was}</span>` : '';
    const agentVal = String(row.agent || '').replace(/"/g, '&quot;');
    el.innerHTML = `
      <div class="fx-row-main">
        <span class="fx-flag">${row.flag}</span>
        <div class="fx-info"><div class="fx-code">${row.code}</div><div class="fx-name">${row.country}</div></div>
        ${was}
        <input type="text" class="fx-rate-input" value="${row.rate}">
        <button class="fx-remove" title="Quitar">&times;</button>
      </div>
      <input type="text" class="fx-agent-input" placeholder="Ventanilla (opcional): Davivienda, 4-72…" value="${agentVal}">`;
    el.querySelector('.fx-rate-input').addEventListener('input', (ev) => {
      row.rate = ev.target.value;
      row.changed = String(row.rate) !== String(row.was);
    });
    el.querySelector('.fx-agent-input').addEventListener('input', (ev) => { row.agent = ev.target.value; });
    el.querySelector('.fx-remove').addEventListener('click', () => removeFromSelected(row));
    list.appendChild(el);
  });
}
function updateSendBtn() { document.getElementById('send-btn').disabled = selectedRows.length === 0; }

async function enviarAServidor() {
  const btn = document.getElementById('send-btn');
  const screenId = document.getElementById('screen-select').value;
  // Qué módulo tocar en el servidor. Sin esto, una pantalla con más de un
  // módulo de divisas (p.ej. Western Union y Ria) recibía el mismo cambio en
  // los dos: el servidor no tenía forma de saber cuál de ellos era.
  const moduleId = document.getElementById('module-select').value;
  btn.textContent = 'Enviando...'; btn.disabled = true;
  const payload = {
    rows: selectedRows.map(r => {
      const row = { flag: r.flag, country: r.country, currency: r.currency, code: r.code, rate: r.rate };
      if (r.agent && r.agent.trim()) row.agent = r.agent.trim();
      return row;
    }),
    screen_ids: screenId ? [screenId] : []
  };
  if (moduleId) payload.item_id = moduleId;
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
      setTimeout(() => { btn.textContent = 'Actualizar InTeks Display'; btn.style.background = ''; updateSendBtn(); }, 2000);
    } else { throw new Error(d.error || 'Error'); }
  } catch (e) {
    btn.textContent = e && e.auth ? '✗ Falta el token de API' : '✗ Error — reintentar';
    btn.style.background = 'var(--danger)';
    setTimeout(() => { btn.textContent = 'Actualizar InTeks Display'; btn.style.background = ''; btn.disabled = false; }, 3000);
  }
}

// Respaldo para códigos que no están en el listado predefinido.
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
  document.getElementById('send-btn').addEventListener('click', enviarAServidor);
  document.getElementById('m-add').addEventListener('click', addManual);
  document.getElementById('save-config').addEventListener('click', saveConfig);
  document.getElementById('module-select').addEventListener('change', pickModule);
  document.getElementById('close-btn').addEventListener('click', () => window.parent.postMessage({ type: 'SIGNALOS_CLOSE' }, '*'));
  ['m-flag', 'm-code', 'm-rate'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') addManual(); });
  });

  document.getElementById('toggle-manual-btn').addEventListener('click', () => {
    const wrap = document.getElementById('manual-row-wrap');
    wrap.style.display = wrap.style.display === 'none' ? '' : 'none';
  });

  const searchInp = document.getElementById('fx-country-search');
  searchInp.addEventListener('focus', abrirFxCombo);
  searchInp.addEventListener('input', () => { fxComboIdx = 0; abrirFxCombo(); });
  searchInp.addEventListener('keydown', (e) => {
    const list = document.getElementById('fx-country-list');
    const abierto = list && list.style.display !== 'none';
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!abierto) { abrirFxCombo(); return; }
      fxComboIdx = Math.max(0, Math.min(fxComboOpts.length - 1, fxComboIdx + (e.key === 'ArrowDown' ? 1 : -1)));
      marcarFxCombo();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const o = fxComboOpts[fxComboIdx >= 0 ? fxComboIdx : 0];
      if (o) pickFxCombo(o);
    } else if (e.key === 'Escape') { cerrarFxCombo(); searchInp.blur(); }
  });
  // mousedown en los items se adelanta al blur, así que aquí solo hay que cerrar.
  searchInp.addEventListener('blur', () => setTimeout(cerrarFxCombo, 120));
}

setInterval(checkConnection, 30000);
