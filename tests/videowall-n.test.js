/** Videowall de N pantallas: cuántas pantallas pide un contenido y cómo se recorta cada trozo. */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const leer = (f) => fs.readFileSync(path.join(__dirname, "..", f), "utf8");
const admin = leer("admin.html"), player = leer("player.html");

test("cuántas pantallas pide un contenido según su tamaño", () => {
  const linea = admin.match(/^function pantallasQuePide.*$/m)[0];
  const c = {}; vm.createContext(c); vm.runInContext(linea, c);
  assert.strictEqual(c.pantallasQuePide(1920, 1080, 16 / 9), 1);
  assert.strictEqual(c.pantallasQuePide(3840, 1080, 16 / 9), 2);
  assert.strictEqual(c.pantallasQuePide(5760, 1080, 16 / 9), 3);
  assert.strictEqual(c.pantallasQuePide(1080, 1920, 9 / 16), 1);   // en vertical
  assert.strictEqual(c.pantallasQuePide(2160, 1920, 9 / 16), 2);   // dos verticales una al lado de la otra
  assert.strictEqual(c.pantallasQuePide(100, 1000, 16 / 9), 1);    // nunca 0
});

test("cada pantalla del muro enseña su trozo: de 0 % a 100 %", () => {
  assert.ok(player.includes('slide.style.setProperty("--wall-x",(wn>1?wi*100/(wn-1):50)+"%")'));
  assert.ok(player.includes("object-position:var(--wall-x,50%) center"));
  const pos = (i, n) => (n > 1 ? (i * 100) / (n - 1) : 50);
  assert.deepStrictEqual([0, 1, 2].map((i) => pos(i, 3)), [0, 50, 100]);
  assert.deepStrictEqual([0, 1].map((i) => pos(i, 2)), [0, 100]);   // como el muro de 2 de siempre
});

test("el panel enlaza N pantallas y desvincula el muro entero", () => {
  assert.ok(admin.includes('id="wall-picker"') && admin.includes("wall_ids:ids,wall_idx:i"));
  assert.ok(admin.includes("const {wall_ids,wall_idx,wall_pos,partner,...resto}=cfg"));
  assert.ok(admin.includes("avisarTamanoWall(sid,item);"));
});
