/**
 * Mandar a pantallas: mensaje de resultado y duración (lógica pura).
 *
 * Ejecutar:  node --test tests/mandar-pantallas.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Mandar a pantallas";
const FIN = "// ── fin de mandar a pantallas";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) throw new Error("No se encuentra el bloque de mandar a pantallas en admin.html");
  const ctx = { String, Array, Object, Math, Number, isFinite };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

test("mensajeEnvio: varios sitios y alguno ya lo tenía", () => {
  assert.strictEqual(cargar().mensajeEnvio({ added: 3, skipped: 1 }), "Añadido en 3 sitios · 1 ya lo tenía");
});
test("mensajeEnvio: un sitio", () => {
  assert.strictEqual(cargar().mensajeEnvio({ added: 1, skipped: 0 }), "Añadido en 1 sitio");
});
test("mensajeEnvio: nada añadido", () => {
  assert.strictEqual(cargar().mensajeEnvio({ added: 0, skipped: 2 }), "No se añadió nada: ya lo tenían");
});
test("mensajeEnvio: varios ya lo tenían", () => {
  assert.strictEqual(cargar().mensajeEnvio({ added: 2, skipped: 3 }), "Añadido en 2 sitios · 3 ya lo tenían");
});
test("duracionValida", () => {
  const c = cargar();
  assert.strictEqual(c.duracionValida("15"), 15);
  assert.strictEqual(c.duracionValida(8), 8);
  assert.strictEqual(c.duracionValida(1), 1);
  assert.strictEqual(c.duracionValida(3600), 3600);
  assert.strictEqual(c.duracionValida("0"), null);
  assert.strictEqual(c.duracionValida("x"), null);
  assert.strictEqual(c.duracionValida(""), null);
  assert.strictEqual(c.duracionValida(null), null);
  assert.strictEqual(c.duracionValida(3601), null);
});
