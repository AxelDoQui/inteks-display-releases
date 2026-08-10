/**
 * extractRate() y extractAgent() cuando el nombre del agente trae dígitos.
 *
 * Bug real: en Ria, el agente "4-72 Servici" (el servicio postal colombiano)
 * hacía que extractRate() devolviera "4" en vez de la tasa real, porque
 * antes se quedaba con el PRIMER número de la fila y "4-72" se parte en dos
 * números sueltos al no tener espacio alrededor del guion. Las dos funciones
 * comparten ahora findRateMatch(), que busca desde el final: la tasa queda
 * pegada al código de moneda, el ruido va delante.
 *
 * Se carga parser.js entero en un vm (no una porción) porque extractRate y
 * extractAgent llaman a normalizeRate y a findRateMatch, todas en el mismo
 * cierre.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PARSER = path.join(__dirname, "..", "inteks-extension", "parser.js");

function cargar() {
  const src = fs.readFileSync(PARSER, "utf8");
  const ctx = { window: {}, document: { querySelectorAll: () => [], body: { innerText: "" } } };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx.window.SignalosParser;
}

test("un agente con dígitos en el nombre no confunde su número con la tasa", () => {
  const p = cargar();
  const cop = p.CODE_MAP.COP;
  assert.strictEqual(p.extractRate("4-72 Servici 3650 COP", cop), "3650");
  assert.strictEqual(p.extractAgent("4-72 Servici 3650 COP", cop), "4-72 Servici");
});

test("con separadores de miles, sigue sacando la tasa completa", () => {
  const p = cargar();
  const cop = p.CODE_MAP.COP;
  assert.strictEqual(p.extractRate("4-72 Servici 3.650,50 COP", cop), "3650,50");
});

test("un agente sin dígitos se sigue comportando igual que antes", () => {
  const p = cargar();
  const cop = p.CODE_MAP.COP;
  assert.strictEqual(p.extractRate("Davivienda 3641 COP", cop), "3641");
  assert.strictEqual(p.extractAgent("Davivienda 3641 COP", cop), "Davivienda");
});

test("una fila normal de moneda + tasa no cambia (sin agente de por medio)", () => {
  const p = cargar();
  const usd = p.CODE_MAP.USD;
  assert.strictEqual(p.extractRate("Dólar estadounidense 1,08 USD", usd), "1,08");
});

test("un año detrás de la tasa se sigue descartando", () => {
  const p = cargar();
  const usd = p.CODE_MAP.USD;
  // "actualizado" no aporta dígitos; el año 2024 debe perder frente a 1,08
  // tanto si aparece antes como después del número real.
  assert.strictEqual(p.extractRate("USD 1,08 (actualizado 2024)", usd), "1,08");
});
