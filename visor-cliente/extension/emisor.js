// Documento invisible: captura la pestaña, recorta el recuadro y lo emite por WebRTC a la tablet.
// El vídeo va directo del PC a la pantalla; el servidor de InTeks Display solo hace de buzón del «saludo» inicial.
const video = document.getElementById("v");
const lienzo = document.createElement("canvas");
const ctx = lienzo.getContext("2d");
let sesion = null;           // { servidor, token, pantalla, tabId, activa, pc }
let rect = null;             // último recuadro medido por la pestaña
let flujoPestana = null, timer = null, latido = null;
let mostrando = true, canal = null;
const MAX_ANCHO = 1280, FPS = 10, LATIDO_MS = 5000, RENOVAR_MS = 10 * 60 * 1000;

const estado = (texto) => chrome.runtime.sendMessage({ tipo: "estado", estado: { activo: true, texto } });
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

// Habla con el servidor de InTeks Display (que solo hace de buzón del saludo). Con el api_token.
async function servidor(metodo, ruta, cuerpo) {
  const r = await fetch(sesion.servidor + ruta, {
    method: metodo,
    headers: { "X-SignalOS-Token": sesion.token, "Content-Type": "application/json" },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    cache: "no-store",
  });
  if (r.status === 401) throw new Error("token");
  if (r.status === 404) throw new Error("pantalla");
  return r.json();
}
function esperarHielo(pc) {
  return new Promise((ok) => {
    if (pc.iceGatheringState === "complete") return ok();
    const t = setTimeout(ok, 3000);
    pc.addEventListener("icegatheringstatechange", () => {
      if (pc.iceGatheringState === "complete") { clearTimeout(t); ok(); }
    });
  });
}
const enviarEstado = () => { try { if (canal && canal.readyState === "open") canal.send(mostrando ? "1" : "0"); } catch (e) {} };

function dibujar() {
  if (!mostrando || !rect || !rect.visible || !video.videoWidth) {
    // Recuadro oculto: pantalla negra, nunca otra parte de la página.
    if (lienzo.width !== 640 || lienzo.height !== 360) { lienzo.width = 640; lienzo.height = 360; }
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, lienzo.width, lienzo.height);
    return;
  }
  const k = video.videoWidth / rect.iw;     // píxeles del vídeo por píxel CSS (vale con zoom)
  const sx = Math.max(0, rect.l * k), sy = Math.max(0, rect.t * k);
  const sw = Math.min(rect.w * k, video.videoWidth - sx), sh = Math.min(rect.h * k, video.videoHeight - sy);
  if (sw < 4 || sh < 4) return;
  const f = Math.min(1, MAX_ANCHO / sw);
  const w = Math.round(sw * f), h = Math.round(sh * f);
  if (Math.abs(lienzo.width - w) > 2 || Math.abs(lienzo.height - h) > 2) { lienzo.width = w; lienzo.height = h; }
  ctx.drawImage(video, sx, sy, sw, sh, 0, 0, lienzo.width, lienzo.height);
}

async function conectar() {
  // Repite mientras se esté mostrando: si la wifi se corta, se vuelve a emparejar sola.
  while (sesion && sesion.activa) {
    // Red local: no hace falta ningún servidor externo (ni de Google) para encontrarse.
    const pc = new RTCPeerConnection({ iceServers: [] });
    sesion.pc = pc;
    canal = pc.createDataChannel("ctl");
    canal.onopen = enviarEstado;
    const pista = lienzo.captureStream(FPS).getVideoTracks()[0];
    pista.contentHint = "detail";
    const envio = pc.addTrack(pista);
    try {
      const p = envio.getParameters(); p.encodings = [{ maxBitrate: 2500000 }]; await envio.setParameters(p);
    } catch (e) {}
    const caida = new Promise((ok) => pc.addEventListener("connectionstatechange", () => {
      if (["failed", "closed"].includes(pc.connectionState)) ok();
      if (pc.connectionState === "connected") estado("Pantalla conectada ✔");
      if (pc.connectionState === "disconnected") {
        setTimeout(() => { if (pc.connectionState === "disconnected") ok(); }, 5000);
      }
    }));
    try {
      await pc.setLocalDescription(await pc.createOffer());
      await esperarHielo(pc);
      let n = (await servidor("POST", "/api/visor/oferta", { screen: sesion.pantalla, sdp: pc.localDescription.sdp })).n;
      estado("Esperando a la pantalla…");
      let resp = null, desde = Date.now();
      while (sesion && sesion.activa && sesion.pc === pc && !resp) {
        await dormir(1500);
        if (Date.now() - desde > RENOVAR_MS) {              // la oferta caduca a la media hora: se renueva
          desde = Date.now();
          const o = await servidor("POST", "/api/visor/oferta", { screen: sesion.pantalla, sdp: pc.localDescription.sdp }).catch(() => null);
          if (o && o.n) n = o.n;
        }
        const r = await servidor("GET", "/api/visor/respuesta?screen=" + encodeURIComponent(sesion.pantalla) + "&n=" + n).catch((e) => {
          if (e.message === "token" || e.message === "pantalla") throw e;
          return null;
        });
        if (r && r.ok && r.sdp) resp = r.sdp;
      }
      if (resp) {
        await pc.setRemoteDescription({ type: "answer", sdp: resp });
        await caida;
        if (sesion && sesion.activa) estado("Se perdió la conexión; reconectando…");
      }
    } catch (e) {
      estado(e.message === "token" ? "El token de API no es válido (míralo en Ajustes del panel); reintentando…"
        : e.message === "pantalla" ? "Esa pantalla ya no existe en InTeks Display; reintentando…"
        : "Sin conexión con InTeks Display; reintentando…");
      await dormir(4000);
    }
    try { pc.close(); } catch (e) {}
  }
}

function ponerMostrando(v) {
  mostrando = !!v;
  enviarEstado();
  chrome.runtime.sendMessage({ tipo: "estado-mostrar", valor: mostrando });
}

async function empezar(d) {
  detener();
  sesion = { ...d, activa: true, pc: null };
  mostrando = true; chrome.runtime.sendMessage({ tipo: "estado-mostrar", valor: true });
  try {
    flujoPestana = await navigator.mediaDevices.getUserMedia({ video: { mandatory: {
      chromeMediaSource: "tab", chromeMediaSourceId: d.streamId } }, audio: false });
  } catch (e) { estado("No se pudo capturar la pestaña: " + e.message); sesion.activa = false; return; }
  video.srcObject = flujoPestana; await video.play();
  timer = setInterval(dibujar, 1000 / FPS);
  latido = setInterval(enviarEstado, LATIDO_MS);   // la pantalla oculta la imagen si dejan de llegar
  conectar();
}
function detener() {
  if (sesion) {
    sesion.activa = false;
    try { if (canal && canal.readyState === "open") canal.send("0"); } catch (e) {}   // la pantalla vuelve a la publicidad
    servidor("POST", "/api/visor/cerrar", { screen: sesion.pantalla }).catch(() => {});
    const pc = sesion.pc;
    setTimeout(() => { try { pc && pc.close(); } catch (e) {} }, 300);   // deja salir el «0»
  }
  if (timer) clearInterval(timer);
  if (latido) clearInterval(latido);
  timer = null; latido = null;
  if (flujoPestana) flujoPestana.getTracks().forEach((t) => t.stop());
  flujoPestana = null; rect = null; sesion = null;
}

chrome.runtime.onMessage.addListener((m, sender) => {
  if (m.tipo === "emitir") empezar(m);
  else if (m.tipo === "detener") detener();
  else if (m.tipo === "mostrar") ponerMostrando(m.valor);
  else if (m.tipo === "rect" && sesion && sender.tab && sender.tab.id === sesion.tabId) rect = m;
});
