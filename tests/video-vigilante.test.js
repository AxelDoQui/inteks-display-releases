/**
 * El vigilante de vídeo del reproductor: un vídeo que no arranca desde la copia local se
 * prueba por red (y se recuerda); si tampoco, se salta y se avisa al servidor; si arranca,
 * se avisa de que ya se ve. Se extrae tal cual de player.html y se ejecuta en un contexto vm.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const src = fs.readFileSync(path.join(__dirname, "..", "player.html"), "utf8");
const a = src.indexOf("// Avisa al servidor de que un vídeo no se pudo ver");
const b = src.indexOf("function showSlide(idx){");
assert.ok(a > 0 && b > a, "no se encuentra el vigilante en player.html");

function arnes(mediosLocales) {
  let tick = null; const enviados = []; const recordados = []; const oyentes = {};
  const attrs = { src: "blob:local" }; let cargas = 0, plays = 0;
  const v = {
    currentTime: 0, error: null, muted: true,
    getAttribute: (k) => attrs[k], setAttribute: (k, x) => { attrs[k] = x; },
    load: () => { cargas++; }, play: () => { plays++; return Promise.resolve(); },
    addEventListener: (e, f) => { oyentes[e] = f; }, removeEventListener: (e) => { delete oyentes[e]; },
  };
  const ctx = {
    PREVIEW: false, SCREEN_ID: "HI", mediosLocales, clearInterval: () => { tick = null; },
    setInterval: (f) => { tick = f; return 1; },
    fetch: (u, o) => { enviados.push(JSON.parse(o.body)); return Promise.resolve(); },
    recordarVideoEnRed: (s) => recordados.push(s),
  };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  let terminado = 0;
  const item = { id: "v1", name: "mi.mp4", src: "/uploads/mi.mp4" };
  ctx.vigilarVideo(v, item, () => { terminado++; });
  return { v, attrs, enviados, recordados, oyentes, tick: () => tick && tick(), terminado: () => terminado, cargas: () => cargas, plays: () => plays };
}
const pasar = (h, n) => { for (let i = 0; i < n; i++) h.tick(); };

test("si arranca, avisa de que ya se ve y termina con 'ended'", () => {
  const h = arnes({ "/uploads/mi.mp4": "blob:local" });
  for (let t = 0.5; t <= 2; t += 0.5) { h.v.currentTime = t; h.tick(); }
  assert.deepEqual(h.enviados, [{ video_ok: "v1", screen: "HI" }]);
  h.oyentes.ended();
  assert.equal(h.terminado(), 1);
});
test("desde la copia local no arranca: prueba por red y lo recuerda", () => {
  const h = arnes({ "/uploads/mi.mp4": "blob:local" });
  pasar(h, 11);
  assert.equal(h.attrs.src, "/uploads/mi.mp4");
  assert.deepEqual(h.recordados, ["/uploads/mi.mp4"]);
  assert.equal(h.terminado(), 0);
  assert.equal(h.enviados.length, 0);
});
test("por red tampoco: salta al siguiente y avisa con el motivo", () => {
  const h = arnes({ "/uploads/mi.mp4": "blob:local" });
  pasar(h, 11); pasar(h, 11);
  assert.equal(h.terminado(), 1);
  assert.equal(h.enviados.length, 1);
  assert.equal(h.enviados[0].video_fallo.motivo, "no llega a arrancar");
  assert.equal(h.enviados[0].video_fallo.name, "mi.mp4");
});
test("sin copia local, un error salta directo y avisa", () => {
  const h = arnes({});
  h.attrs.src = "/uploads/mi.mp4";
  h.v.error = { code: 4 }; h.oyentes.error();
  assert.equal(h.terminado(), 1);
  assert.match(h.enviados[0].video_fallo.motivo, /error del reproductor/);
});
test("se atasca a mitad: lo cuenta como 'se queda parado'", () => {
  const h = arnes({});
  h.attrs.src = "/uploads/mi.mp4";
  h.v.currentTime = 2; h.tick();
  pasar(h, 11);
  assert.equal(h.enviados.at(-1).video_fallo.motivo, "se queda parado");
});
