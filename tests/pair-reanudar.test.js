/**
 * /pair pedía un código SIEMPRE, sin mirar si el dispositivo ya estaba
 * enlazado. Bastaba con que alguien dejara /pair como página de inicio del
 * televisor —cosa que pasa, porque nadie recuerda la URL larga del player—
 * para que cada encendido pidiera un código nuevo.
 *
 * Y no había arreglo posible desde el panel: pair-claim rechazaba el nombre
 * real de esa pantalla por duplicado, así que o te inventabas «Escaparate-2»
 * con la playlist vacía, o borrabas la pantalla buena.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PAIR = path.join(__dirname, "..", "pair.html");
const INICIO = "// ── Decisión de arranque";
const FIN = "// ── fin de la decisión de arranque";

function cargar() {
  const src = fs.readFileSync(PAIR, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra decidirArranque en pair.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { URLSearchParams };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const params = q => new URLSearchParams(q);

test("sin identidad guardada, pide código", () => {
  const d = cargar().decidirArranque(null, params(""));
  assert.strictEqual(d.accion, "pedir");
  assert.strictEqual(d.knownAs, "");
});

test("con identidad guardada, reanuda en vez de pedir código", () => {
  // El caso de todos los días: el TV se enciende y alguien había dejado /pair
  // como página de inicio.
  const d = cargar().decidirArranque("Escaparate", params(""));
  assert.strictEqual(d.accion, "reanudar");
  assert.strictEqual(d.screen, "Escaparate");
});

test("con ?nuevo=1 pide código aunque haya identidad", () => {
  // La vía de escape: reenlazar a propósito un televisor que ya funcionaba.
  const d = cargar().decidirArranque("Escaparate", params("nuevo=1"));
  assert.strictEqual(d.accion, "pedir");
});

test("?era= viaja como known_as para que el panel sugiera el reenlace", () => {
  const d = cargar().decidirArranque(null, params("nuevo=1&era=Escaparate"));
  assert.strictEqual(d.accion, "pedir");
  assert.strictEqual(d.knownAs, "Escaparate");
});

test("si falta ?era= pero queda identidad, se usa esa como sugerencia", () => {
  const d = cargar().decidirArranque("Caja-1", params("nuevo=1"));
  assert.strictEqual(d.knownAs, "Caja-1");
});

test("?era= manda sobre la identidad que quede suelta", () => {
  const d = cargar().decidirArranque("Vieja", params("nuevo=1&era=Escaparate"));
  assert.strictEqual(d.knownAs, "Escaparate");
});

test("?era= sin ?nuevo=1 no impide reanudar", () => {
  // era= es solo una pista para el panel; no es una orden de desenlazar.
  const d = cargar().decidirArranque("Escaparate", params("era=Otra"));
  assert.strictEqual(d.accion, "reanudar");
  assert.strictEqual(d.screen, "Escaparate");
});
