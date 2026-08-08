// NOTA: no hay listener de chrome.action.onClicked. El manifiesto declara
// "default_popup", y con un popup declarado ese evento NUNCA se dispara: al
// pulsar el icono Chrome abre el popup y no avisa al background. El listener
// que había aquí era código muerto. La apertura del panel la hace popup.js.

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === 'SEND_TO_SIGNALOS') {
    // El envío real lo hace el sidebar vía fetch; el background solo confirma el relay.
    sendResponse({ ok: true });
  }
  return true;
});
