/**
 * Etiqueta de la versión del APK en la tarjeta de pantalla (lógica pura).
 *
 * Ejecutar:  node --test tests/apk-version.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── APK de la caja";
const FIN = "// ── fin de APK de la caja";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) throw new Error("No se encuentra el bloque de APK en admin.html");
  const ctx = { String };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}
const est = (apk, srv) => cargar().estadoApk(apk, srv);

test("sin apk no hay etiqueta", () => {
  assert.strictEqual(est("", "1.0.49"), null);
  assert.strictEqual(est(undefined, "1.0.49"), null);
  assert.strictEqual(est(null, "1.0.49"), null);
});
test("igual que el servidor: sin aviso", () => {
  const e = est("1.0.49", "1.0.49");
  assert.strictEqual(e.texto, "APK 1.0.49");
  assert.strictEqual(e.aviso, false);
});
test("distinto: aviso con las dos versiones", () => {
  const e = est("1.0.40", "1.0.49");
  assert.strictEqual(e.texto, "APK antiguo: 1.0.40 (servidor 1.0.49)");
  assert.strictEqual(e.aviso, true);
});
test("más nuevo que el servidor también avisa (solo compara cadenas)", () => {
  assert.strictEqual(est("1.0.60", "1.0.49").aviso, true);
});
test("sin versión del servidor no se alarma", () => {
  const e = est("1.0.49", "");
  assert.strictEqual(e.texto, "APK 1.0.49");
  assert.strictEqual(e.aviso, false);
});
