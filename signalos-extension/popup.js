async function init() {
  let url = 'http://localhost';
  try { const d = await chrome.storage.local.get(['serverUrl']); if (d.serverUrl) url = d.serverUrl; } catch (e) {}
  document.getElementById('server-url').value = url;
  await checkStatus(url);
}

async function checkStatus(url) {
  const dot = document.getElementById('dot');
  const txt = document.getElementById('status-txt');
  try {
    const r = await fetch(`${url}/api/info`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      const d = await r.json();
      dot.className = 'dot online';
      txt.textContent = `Conectado — Puerto ${d.port}`;
      return;
    }
  } catch (e) {}
  dot.className = 'dot';
  txt.textContent = 'Sin conexión con SignalOS';
}

document.getElementById('save').addEventListener('click', async () => {
  const url = document.getElementById('server-url').value.trim().replace(/\/+$/, '');
  try { await chrome.storage.local.set({ serverUrl: url }); } catch (e) {}
  await checkStatus(url);
});

// Muestra el motivo en el propio popup. Antes esto fallaba en silencio: se
// cerraba la ventana y no pasaba nada, sin ninguna pista de por qué.
function panelError(msg) {
  const el = document.getElementById('panel-error');
  el.textContent = msg;
  el.style.display = 'block';
}

// Garantiza que el content script está vivo en la pestaña. Solo se inyecta al
// CARGAR la página, así que en una pestaña abierta antes de instalar o recargar
// la extensión no hay nadie escuchando y sendMessage rechaza. En ese caso se
// inyecta a mano, en el mismo orden que declara el manifiesto.
async function ensureContentScript(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: 'PING' });
    return true;
  } catch (e) {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['parser.js', 'content.js'] });
    return true;
  }
}

document.getElementById('open-panel').addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) { panelError('No se encuentra la pestaña activa.'); return; }
    await ensureContentScript(tab.id);
    await chrome.tabs.sendMessage(tab.id, { type: 'OPEN_SIDEBAR' });
    window.close();
  } catch (e) {
    // Chrome bloquea la inyección en sus propias páginas y en la Web Store.
    panelError('No se puede abrir el panel en esta pestaña. Abre la web de ' +
               'tipos de cambio en una pestaña normal (http o https) e inténtalo ahí.');
  }
});

init();
