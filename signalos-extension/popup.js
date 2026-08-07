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

document.getElementById('open-panel').addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id) { chrome.tabs.sendMessage(tab.id, { type: 'OPEN_SIDEBAR' }).catch(() => {}); }
    window.close();
  } catch (e) {}
});

init();
