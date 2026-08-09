/**
 * Orden de reproduccion: en fila o al azar.
 *
 * Una pantalla de tienda repite el mismo ciclo todo el dia. Con pocos
 * contenidos, el orden fijo hace que el cliente que espera su turno vea
 * exactamente la misma secuencia tres veces seguidas.
 *
 * Lo delicado no es barajar -eso es Fisher-Yates- sino el empalme entre una
 * vuelta y la siguiente: si la ultima de una vuelta es la primera de la
 * siguiente, el mismo cartel sale dos veces seguidas y parece que se ha
 * colgado. Por eso ordenReproduccion recibe cual fue el ultimo.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Orden de reproduccion";
const FIN = "// ── fin del orden";

// random devuelve siempre lo mismo para que el barajado sea predecible y se
// pueda afirmar algo concreto en vez de "sale una permutacion cualquiera".
function cargar(random) {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el bloque de orden en player.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { Math: { floor: Math.floor, random: random || Math.random } };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const plano = c => JSON.parse(JSON.stringify(c));

// ── En fila ────────────────────────────────────────────────────────────────

test("sin aleatorio, el orden es el que puso el usuario", () => {
  const c = cargar();
  assert.deepStrictEqual(plano(c.ordenReproduccion(4, false, -1)), [0, 1, 2, 3]);
});

test("sin aleatorio, el ultimo reproducido da igual", () => {
  // El orden lo decide el usuario arrastrando en la playlist; nada lo altera.
  const c = cargar();
  assert.deepStrictEqual(plano(c.ordenReproduccion(3, false, 0)), [0, 1, 2]);
});

// ── Al azar ────────────────────────────────────────────────────────────────

test("al azar salen todos, una sola vez cada uno", () => {
  // Barajar no puede perder ni duplicar contenidos: se veria como una
  // diapositiva que desaparece del ciclo sin motivo.
  const c = cargar();
  const o = plano(c.ordenReproduccion(6, true, -1));
  assert.strictEqual(o.length, 6);
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2, 3, 4, 5]);
});

test("al azar de verdad cambia el orden", () => {
  const c = cargar(() => 0);          // barajado determinista
  assert.notDeepStrictEqual(plano(c.ordenReproduccion(3, true, -1)), [0, 1, 2]);
});

test("el mismo contenido no sale dos veces seguidas al cambiar de vuelta", () => {
  // Con random()=0 la baraja de 3 da [1,2,0]. Si la vuelta anterior acabo en 1,
  // el 1 abriria la siguiente: dos veces seguidas.
  const c = cargar(() => 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(3, true, -1)), [1, 2, 0],
    "control: sin ultimo, la baraja empieza por 1");
  const o = plano(c.ordenReproduccion(3, true, 1));
  assert.notStrictEqual(o[0], 1, "no puede repetir el ultimo de la vuelta anterior");
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2],
    "y sigue habiendo los tres");
});

// ── Casos limite ───────────────────────────────────────────────────────────

test("con un solo contenido no hay nada que evitar", () => {
  // Repetirlo es inevitable: es el unico que hay. No puede quedarse en bucle
  // intentando que no se repita.
  const c = cargar(() => 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(1, true, 0)), [0]);
});

test("una playlist vacia no da orden ninguno", () => {
  const c = cargar();
  assert.deepStrictEqual(plano(c.ordenReproduccion(0, true, -1)), []);
  assert.deepStrictEqual(plano(c.ordenReproduccion(0, false, -1)), []);
});

test("dos contenidos al azar siempre alternan", () => {
  // Con dos, evitar la repeticion obliga a alternar. Es lo esperable.
  const c = cargar(() => 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(2, true, 1))[0], 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(2, true, 0))[0], 1);
});
