// Vive en cada pestaña: inyecta el panel lateral (iframe) y hace de puente con él.
let sidebarVisible = false;
let sidebarFrame = null;
let scanInterval = null;

function createSidebar() {
  sidebarFrame = document.createElement('iframe');
  sidebarFrame.id = 'signalos-sidebar';
  sidebarFrame.src = chrome.runtime.getURL('sidebar.html');
  sidebarFrame.style.cssText = [
    'position:fixed','top:0','right:0','width:320px','height:100vh','border:none',
    'z-index:2147483647','box-shadow:-4px 0 24px rgba(0,0,0,.45)',
    'transform:translateX(100%)','transition:transform .3s ease','background:#0c0c0e','color-scheme:dark'
  ].map(s => s + ' !important').join(';');
  document.documentElement.appendChild(sidebarFrame);
}

function toggleSidebar(force) {
  if (!sidebarFrame) createSidebar();
  sidebarVisible = (typeof force === 'boolean') ? force : !sidebarVisible;
  sidebarFrame.style.setProperty('transform', sidebarVisible ? 'translateX(0)' : 'translateX(100%)', 'important');
  if (sidebarVisible) { scanAndUpdate(); startAutoScan(); }
  else { stopAutoScan(); }
}

async function scanAndUpdate() {
  let detected = [];
  try {
    let prefs = {};
    try { prefs = (await chrome.storage.local.get('agentPrefs')).agentPrefs || {}; } catch (e) {}
    detected = window.SignalosParser.scanPage(prefs);
  } catch (e) {}
  if (sidebarFrame && sidebarVisible && sidebarFrame.contentWindow) {
    sidebarFrame.contentWindow.postMessage({
      type: 'SIGNALOS_DETECTED', rows: detected,
      url: location.href, title: document.title
    }, '*');
  }
}

function startAutoScan() { stopAutoScan(); scanInterval = setInterval(scanAndUpdate, 30000); }
function stopAutoScan() { if (scanInterval) { clearInterval(scanInterval); scanInterval = null; } }

// Mensajes desde el background (toggle) / popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // PING deja que el popup compruebe si este script está vivo en la pestaña.
  // Los content scripts solo se inyectan al CARGAR la página, así que en una
  // pestaña abierta antes de instalar la extensión no hay nadie escuchando.
  if (msg && msg.type === 'PING') { sendResponse({ ok: true }); return; }
  if (msg && msg.type === 'TOGGLE_SIDEBAR') toggleSidebar();
  if (msg && msg.type === 'OPEN_SIDEBAR') toggleSidebar(true);
});

// Mensajes desde el panel lateral (iframe)
window.addEventListener('message', (e) => {
  const d = e.data || {};
  if (d.type === 'SIGNALOS_RESCAN') scanAndUpdate();
  else if (d.type === 'SIGNALOS_CLOSE') toggleSidebar(false);
});
