/**
 * Visor de cliente en player.html: la capa que enseña el recuadro del mostrador.
 *
 * Se extrae visorCliente() tal cual está en player.html y se ejecuta con un
 * RTCPeerConnection, un fetch y un reloj falsos. Lo que importa:
 *   - la capa SOLO se ve con conexión Y con el "1" del mostrador (por defecto, oculta);
 *   - se oculta con "0", si se corta la conexión o si el PC deja de avisar;
 *   - responde a cada oferta nueva una sola vez y nunca a una ya respondida;
 *   - tras un corte vuelve a conectar sola cuando llega una oferta nueva.
 *
 * Ejecutar:  node --test tests/visor-cliente-player.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

function cargar() {
  const src = fs.readFileSync(path.join(__dirname, "..", "player.html"), "utf8");
  const a = src.indexOf("function visorCliente(env)");
  const b = src.indexOf("// ── fin del visor de cliente", a);
  if (a === -1 || b === -1) throw new Error("No se encuentra visorCliente() en player.html");
  return new Function(src.slice(a, b) + "\nreturn visorCliente;")();
}

function montar() {
  const t = { ahora: 1000, timers: [], id: 0 };
  const el = () => ({ style: {}, children: [], setAttribute() {}, appendChild(h) { this.children.push(h); } });
  const cuerpo = el();
  const pcs = [];
  class PC {
    constructor(cfg) { this.cfg = cfg; this.iceGatheringState = "complete"; this.iceConnectionState = "new"; this.cerrado = false; pcs.push(this); }
    setRemoteDescription(d) { this.remota = d; return Promise.resolve(); }
    createAnswer() { return Promise.resolve({ type: "answer", sdp: "v=0 respuesta" }); }
    setLocalDescription(d) { this.localDescription = d; return Promise.resolve(); }
    close() { this.cerrado = true; }
  }
  const servidor = { oferta: { ok: false }, respuestas: [], respondeOk: true };
  const env = {
    document: { createElement: () => el(), body: cuerpo },
    SCREEN_ID: "tablet",
    RTCPeerConnection: PC,
    MediaStream: function () {},
    Date: { now: () => t.ahora },
    setTimeout: (f, ms) => { t.timers.push({ f, en: t.ahora + ms, id: ++t.id }); return t.id; },
    clearTimeout: (id) => { t.timers = t.timers.filter((x) => x.id !== id); },
    setInterval: (f, ms) => { t.timers.push({ f, cada: ms, en: t.ahora + ms, id: ++t.id }); return t.id; },
    fetch: (url, o) => {
      if (url.startsWith("/api/visor/oferta")) return Promise.resolve({ json: async () => servidor.oferta });
      if (url === "/api/visor/respuesta") {
        servidor.respuestas.push(JSON.parse(o.body));
        return Promise.resolve({ json: async () => ({ ok: servidor.respondeOk }) });
      }
      return Promise.reject(new Error("url inesperada " + url));
    },
  };
  const visor = cargar()(env);
  const capa = cuerpo.children[0];
  async function vaciar() { for (let i = 0; i < 20; i++) await Promise.resolve(); }
  async function avanzar(ms) {
    const fin = t.ahora + ms;
    for (;;) {
      const prox = t.timers.filter((x) => x.en <= fin).sort((p, q) => p.en - q.en)[0];
      if (!prox) break;
      t.ahora = prox.en;
      if (prox.cada) prox.en += prox.cada; else t.timers = t.timers.filter((x) => x !== prox);
      prox.f(); await vaciar();
    }
    t.ahora = fin;
  }
  return { visor, capa, pcs, servidor, avanzar, vaciar };
}
const hielo = (pc, estado) => { pc.iceConnectionState = estado; pc.oniceconnectionstatechange(); };
const mensaje = (pc, dato) => {
  if (!pc.canal) { pc.canal = {}; pc.ondatachannel({ channel: pc.canal }); }
  pc.canal.onmessage({ data: dato });
};
const OFERTA = (n, respondida = false) => ({ ok: true, n, sdp: "v=0 oferta", respondida });

test("empieza oculta y no abre nada sin oferta", async () => {
  const m = montar();
  await m.avanzar(20000);
  assert.strictEqual(m.capa.style.display, "none");
  assert.strictEqual(m.pcs.length, 0);
});

test("contesta a la oferta y solo muestra con conexión y «1»", async () => {
  const m = montar();
  m.servidor.oferta = OFERTA(1);
  await m.avanzar(5000);
  assert.strictEqual(m.pcs.length, 1);
  assert.deepStrictEqual(m.pcs[0].cfg, { iceServers: [] }, "sin servidores externos");
  assert.deepStrictEqual(m.servidor.respuestas, [{ screen: "tablet", n: 1, sdp: "v=0 respuesta" }]);
  assert.strictEqual(m.capa.style.display, "none", "sin conexión no se ve");
  hielo(m.pcs[0], "connected");
  assert.strictEqual(m.capa.style.display, "none", "conectada pero sin aviso del mostrador: oculta");
  mensaje(m.pcs[0], "1");
  assert.strictEqual(m.capa.style.display, "block");
  mensaje(m.pcs[0], "0");
  assert.strictEqual(m.capa.style.display, "none");
  mensaje(m.pcs[0], "1");
  assert.strictEqual(m.capa.style.display, "block");
});

test("sin avisos del PC se oculta sola; con avisos se mantiene", async () => {
  const m = montar();
  m.servidor.oferta = OFERTA(1);
  await m.avanzar(5000);
  hielo(m.pcs[0], "connected"); mensaje(m.pcs[0], "1");
  for (let i = 0; i < 4; i++) { await m.avanzar(5000); mensaje(m.pcs[0], "1"); }
  assert.strictEqual(m.capa.style.display, "block", "con latidos se mantiene");
  await m.avanzar(17000);
  assert.strictEqual(m.capa.style.display, "none", "sin latidos se oculta");
});

test("si se corta la conexión vuelve la publicidad y reconecta con la oferta nueva", async () => {
  const m = montar();
  m.servidor.oferta = OFERTA(1);
  await m.avanzar(5000);
  hielo(m.pcs[0], "connected"); mensaje(m.pcs[0], "1");
  hielo(m.pcs[0], "failed");
  assert.strictEqual(m.capa.style.display, "none");
  assert.ok(m.pcs[0].cerrado);
  // La misma oferta (ya respondida) no se vuelve a contestar...
  await m.avanzar(10000);
  assert.strictEqual(m.pcs.length, 1);
  // ...una nueva sí.
  m.servidor.oferta = OFERTA(2);
  await m.avanzar(5000);
  assert.strictEqual(m.pcs.length, 2);
  assert.strictEqual(m.servidor.respuestas[1].n, 2);
  hielo(m.pcs[1], "connected"); mensaje(m.pcs[1], "1");
  assert.strictEqual(m.capa.style.display, "block");
});

test("«disconnected» que no se recupera en 5 s la oculta; si se recupera, se queda", async () => {
  const m = montar();
  m.servidor.oferta = OFERTA(1);
  await m.avanzar(5000);
  hielo(m.pcs[0], "connected"); mensaje(m.pcs[0], "1");
  hielo(m.pcs[0], "disconnected");
  assert.strictEqual(m.capa.style.display, "block", "un bache corto no la quita");
  await m.avanzar(5000);
  assert.strictEqual(m.capa.style.display, "none");
  m.servidor.oferta = OFERTA(2);
  await m.avanzar(5000);
  hielo(m.pcs[1], "connected"); mensaje(m.pcs[1], "1");
  hielo(m.pcs[1], "disconnected"); await m.avanzar(2000); hielo(m.pcs[1], "connected");
  await m.avanzar(2000);
  assert.strictEqual(m.pcs[1].cerrado, false);
});

test("no contesta a una oferta ya respondida por otro", async () => {
  const m = montar();
  m.servidor.oferta = OFERTA(7, true);
  await m.avanzar(15000);
  assert.strictEqual(m.pcs.length, 0);
});

test("si el servidor rechaza la respuesta, suelta la conexión", async () => {
  const m = montar();
  m.servidor.respondeOk = false;
  m.servidor.oferta = OFERTA(1);
  await m.avanzar(5000);
  assert.ok(m.pcs[0].cerrado);
  assert.strictEqual(m.capa.style.display, "none");
});

test("si no llega a conectar en 30 s, la suelta", async () => {
  const m = montar();
  m.servidor.oferta = OFERTA(1);
  await m.avanzar(5000);
  await m.avanzar(31000);
  assert.ok(m.pcs[0].cerrado);
});

test("player.html solo la activa en una pantalla real, no en la previa", () => {
  const src = fs.readFileSync(path.join(__dirname, "..", "player.html"), "utf8");
  assert.match(src, /if\(SCREEN_ID && !PREVIEW && window\.RTCPeerConnection\)\{\s*try\{ visorCliente\(/);
});
