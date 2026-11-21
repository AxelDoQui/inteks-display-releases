// Fondo: crea el documento invisible que captura y emite, y guarda el estado para el popup.
const OFFSCREEN = "emisor.html";

async function asegurarEmisor() {
  if (await chrome.offscreen.hasDocument()) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN, reasons: ["USER_MEDIA", "WEB_RTC"],
    justification: "Capturar el recuadro elegido y enviarlo a la tablet",
  });
}

chrome.runtime.onMessage.addListener((m, sender, responder) => {
  if (m.tipo === "iniciar") {
    asegurarEmisor().then(() => {
      chrome.storage.local.set({ compartiendo: true, mostrando: true });
      chrome.runtime.sendMessage({ tipo: "emitir", ...m.datos });
      responder(true);
    });
    return true;
  }
  if (m.tipo === "parar") {
    chrome.runtime.sendMessage({ tipo: "detener" });
    chrome.storage.local.set({ compartiendo: false, mostrando: true, tabletOk: false });
    chrome.storage.session.set({ estado: { texto: "", activo: false } });
    // Se espera un poco para que al emisor le dé tiempo de decirle «0» a la pantalla y avisar al servidor.
    setTimeout(() => chrome.offscreen.hasDocument().then((h) => { if (h) chrome.offscreen.closeDocument(); }), 800);
  }
  if (m.tipo === "estado") {
    chrome.storage.session.set({ estado: m.estado });
    chrome.storage.local.set({ tabletOk: /conectada/i.test(m.estado.texto || "") });   // para la barra flotante
  }
  if (m.tipo === "estado-mostrar") chrome.storage.local.set({ mostrando: m.valor });
});

// La barra flotante de la página escribe «mostrando» en el almacén; aquí se le pasa al emisor.
chrome.storage.onChanged.addListener((c, area) => {
  if (area === "local" && c.mostrando) chrome.runtime.sendMessage({ tipo: "mostrar", valor: c.mostrando.newValue !== false }).catch(() => {});
});
