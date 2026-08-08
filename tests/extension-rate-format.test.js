/**
 * Tests del formato de tasas que detecta la extensión.
 *
 * Convención española: la COMA separa decimales y el PUNTO los millares.
 * Se publica con un máximo de 2 decimales tras la coma.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PARSER = path.join(__dirname, "..", "inteks-extension", "parser.js");

function loadNormalize() {
  const src = fs.readFileSync(PARSER, "utf8");
  const from = src.indexOf("function normalizeRate(");
  const to = src.indexOf("function extractRate(", from);
  if (from === -1 || to === -1 || to <= from) {
    throw new Error("No se encuentra normalizeRate() antes de extractRate() en " +
                    "parser.js. Si se ha movido, actualiza este arnés.");
  }
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to), ctx);
  return ctx.normalizeRate;
}

// ── El punto es separador de millares ──────────────────────────────────────

test("el punto de millares no es un decimal", () => {
  const n = loadNormalize();
  // El fallo que motivó esto: 1.716,50 se publicaba como "1.716" (uno coma siete)
  assert.strictEqual(n("1.716,50"), "1716,50");
  assert.strictEqual(n("1.716"), "1716");
  assert.strictEqual(n("27.500"), "27500");
});

test("un punto con menos de tres cifras detrás sí es decimal", () => {
  const n = loadNormalize();
  // "1.08" es una cotización plausible de euro/dólar, no mil ochenta.
  assert.strictEqual(n("1.08"), "1,08");
  assert.strictEqual(n("1.0850"), "1,09");
});

// ── La coma es separador decimal ───────────────────────────────────────────

test("la coma marca los decimales", () => {
  const n = loadNormalize();
  assert.strictEqual(n("1,14"), "1,14");
  assert.strictEqual(n("30,63"), "30,63");
});

test("se recorta a dos decimales como máximo", () => {
  const n = loadNormalize();
  assert.strictEqual(n("1716,5432"), "1716,54");
  assert.strictEqual(n("0,123456"), "0,12");
});

test("se redondea, no se trunca", () => {
  const n = loadNormalize();
  assert.strictEqual(n("1,999"), "2");
  assert.strictEqual(n("30,638"), "30,64");
});

// ── Enteros y ceros ────────────────────────────────────────────────────────

test("un entero se queda sin decimales", () => {
  const n = loadNormalize();
  assert.strictEqual(n("4000"), "4000");
  assert.strictEqual(n("6960"), "6960");
  assert.strictEqual(n("1716,00"), "1716", "no tiene sentido publicar 1716,00");
});

test("se conservan los dos decimales aunque el segundo sea cero", () => {
  const n = loadNormalize();
  assert.strictEqual(n("1,10"), "1,10");
  assert.strictEqual(n("1,1"), "1,10");
});

// ── Formato anglosajón ─────────────────────────────────────────────────────

test("con los dos separadores manda el último", () => {
  const n = loadNormalize();
  assert.strictEqual(n("1.716,54"), "1716,54", "formato español");
  assert.strictEqual(n("1,716.54"), "1716,54", "formato inglés");
});

// ── Entradas inválidas ─────────────────────────────────────────────────────

test("lo que no es un número se descarta", () => {
  const n = loadNormalize();
  assert.strictEqual(n(""), null);
  assert.strictEqual(n("abc"), null);
  assert.strictEqual(n("-5"), null, "una tasa negativa no existe");
  assert.strictEqual(n("0"), null, "una tasa de cero tampoco");
});
