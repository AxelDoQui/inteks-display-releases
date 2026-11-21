const $ = (id) => document.getElementById(id);
let pestana = null;

// La dirección se admite pegada de cualquier forma: con o sin http://, con / o /admin.html al final.
function normalizarServidor(t) {
  t = String(t || "").trim();
  if (!t) return "";
  if (!/^https?:\/\//i.test(t)) t = "http://" + t;
  try { return new URL(t).origin; } catch (e) { return ""; }
}

function pintar(est) {
  const activo = !!(est && est.activo);
  $("vista-inicio").classList.toggle("oculto", activo);
  $("vista-activa").classList.toggle("oculto", !activo);
  $("estado").textContent = (est && est.texto) || "";
}

async function pintarZonas() {
  const { zonas = {} } = await chrome.storage.local.get("zonas");
  const z = zonas[new URL(pestana.url).origin];
  const caja = $("zonas"); caja.textContent = "";
  if (!z || !z.lista.length) { caja.innerHTML = "<small>Ninguno todavía.</small>"; return; }
  z.lista.forEach((r, i) => {
    const f = document.createElement("div");
    const n = document.createElement("span"); n.textContent = r.nombre;
    const x = document.createElement("span"); x.className = "x"; x.textContent = "✕"; x.title = "Quitar";
    x.onclick = async () => {
      z.lista.splice(i, 1); z.activa = 0;
      if (!z.lista.length) delete zonas[new URL(pestana.url).origin];
      await chrome.storage.local.set({ zonas }); pintarZonas();
    };
    f.append(n, x); caja.appendChild(f);
  });
}

// Pide al servidor las pantallas y las pone en la lista por su nombre. Devuelve true si va bien.
async function cargarPantallas(servidor, token) {
  const sel = $("pantalla"); sel.textContent = "";
  if (!servidor || !token) { sel.innerHTML = "<option value=''>Primero rellena la conexión (abajo)</option>"; return false; }
  try {
    const r = await fetch(servidor + "/api/screens", { headers: { "X-SignalOS-Token": token }, cache: "no-store", signal: AbortSignal.timeout(4000) });
    if (r.status === 401) { sel.innerHTML = "<option value=''>Token no válido</option>"; $("estado").textContent = "El token de API no es válido."; return false; }
    if (!r.ok) throw new Error(r.status);
    const lista = Object.values(await r.json()).filter((p) => p && p.id);
    if (!lista.length) { sel.innerHTML = "<option value=''>No hay pantallas enlazadas</option>"; return false; }
    const { pantalla = "" } = await chrome.storage.local.get("pantalla");
    for (const p of lista) {
      const o = document.createElement("option");
      o.value = p.id; o.textContent = (p.name && p.name !== p.id) ? p.name + " (" + p.id + ")" : p.id;
      if (p.id === pantalla) o.selected = true;
      sel.appendChild(o);
    }
    $("estado").textContent = "";
    return true;
  } catch (e) {
    sel.innerHTML = "<option value=''>No se alcanza el servidor</option>";
    $("estado").textContent = "No se alcanza InTeks Display en " + servidor;
    return false;
  }
}

async function iniciar() {
  [pestana] = await chrome.tabs.query({ active: true, currentWindow: true });
  pintarZonas();
  const { servidor = "", token = "" } = await chrome.storage.local.get(["servidor", "token"]);
  $("servidor").value = servidor; $("token").value = token;
  if (!servidor || !token) $("ajustes").open = true;
  const { estado } = await chrome.storage.session.get("estado");
  pintar(estado);
  if (!(estado && estado.activo)) await cargarPantallas(servidor, token);
}
chrome.storage.onChanged.addListener((c, area) => { if (area === "session" && c.estado) pintar(c.estado.newValue); });

$("guardar").onclick = async () => {
  const servidor = normalizarServidor($("servidor").value), token = $("token").value.trim();
  if (!servidor) { $("estado").textContent = "Escribe la dirección del servidor."; return; }
  $("servidor").value = servidor;
  await chrome.storage.local.set({ servidor, token });
  if (await cargarPantallas(servidor, token)) $("estado").textContent = "Conectado con InTeks Display ✔";
};
$("pantalla").onchange = () => chrome.storage.local.set({ pantalla: $("pantalla").value });
$("elegir").onclick = async () => {
  await chrome.scripting.executeScript({ target: { tabId: pestana.id }, files: ["elegir.js"] });
  window.close();
};
$("mostrar").onclick = async () => {
  const { servidor = "", token = "" } = await chrome.storage.local.get(["servidor", "token"]);
  const pantalla = $("pantalla").value;
  if (!servidor || !token) { $("estado").textContent = "Primero rellena la conexión con InTeks Display."; $("ajustes").open = true; return; }
  if (!pantalla) { $("estado").textContent = "Elige la pantalla donde se enseña."; return; }
  const { zonas = {} } = await chrome.storage.local.get("zonas");
  const zz = zonas[new URL(pestana.url).origin];
  if (!zz || !zz.lista.length) { $("estado").textContent = "Primero añade un recuadro (botón 1)."; return; }
  await chrome.storage.local.set({ pantalla });
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: pestana.id });
  await chrome.storage.session.set({ estado: { activo: true, texto: "Esperando a la pantalla…" } });
  chrome.runtime.sendMessage({ tipo: "iniciar", datos: { streamId, servidor, token, pantalla, tabId: pestana.id } });
};
$("parar").onclick = () => chrome.runtime.sendMessage({ tipo: "parar" });
iniciar();
