// Al hacer clic en el icono de la extensión, alterna el panel lateral en la pestaña activa.
// (El popup de configuración se abre con clic derecho > Opciones, o desde default_popup.)
chrome.action.onClicked.addListener((tab) => {
  if (tab && tab.id) chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_SIDEBAR' }).catch(() => {});
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === 'SEND_TO_SIGNALOS') {
    // El envío real lo hace el sidebar vía fetch; el background solo confirma el relay.
    sendResponse({ ok: true });
  }
  return true;
});
