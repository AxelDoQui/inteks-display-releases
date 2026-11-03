/** Los vídeos suenan por defecto; solo callan si la pantalla lo apaga en su playlist. */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const src = fs.readFileSync(path.join(__dirname, "..", "player.html"), "utf8");
const linea = src.match(/^function sonidoVideos.*$/m)[0];
const rol = (r) => ({ wallRol: () => r });

function con(cfg) {
  const ctx = { screenConfig: cfg, ...rol("") };
  vm.createContext(ctx);
  vm.runInContext(linea, ctx);
  return ctx.sonidoVideos();
}

test("suena por defecto y con la casilla activa", () => {
  assert.strictEqual(con(null), true);
  assert.strictEqual(con({}), true);
  assert.strictEqual(con({ video_sonido: true }), true);
});
test("calla solo si la pantalla lo apaga", () => {
  assert.strictEqual(con({ video_sonido: false }), false);
});
test("el panel guarda y lee la casilla", () => {
  const a = fs.readFileSync(path.join(__dirname, "..", "admin.html"), "utf8");
  assert.ok(a.includes('id="plm-sonido"') && a.includes("video_sonido=document.getElementById(\"plm-sonido\")"));
});

test("un vídeo silenciado calla aunque la pantalla deje sonar", () => {
  const ctx = { screenConfig: {}, ...rol("") };
  vm.createContext(ctx);
  vm.runInContext(linea, ctx);
  assert.strictEqual(ctx.sonidoVideos({ silencio: true }), false);
  assert.strictEqual(ctx.sonidoVideos({}), true);
  assert.ok(fs.readFileSync(path.join(__dirname, "..", "admin.html"), "utf8").includes("toggleSilencio"));
});

test("en un videowall solo suena la pantalla que manda", () => {
  const f = (r) => { const c = { screenConfig: {}, ...rol(r) }; vm.createContext(c); vm.runInContext(linea, c); return c.sonidoVideos({}); };
  assert.strictEqual(f("manda"), true);
  assert.strictEqual(f("sigue"), false);
});
