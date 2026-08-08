/**
 * Tests del agrupamiento en páginas del módulo de divisas.
 *
 * Mismo arnés que schedule.test.js: extrae la función del propio player.html y
 * la ejecuta en un vm, para no probar una copia que se desincronice.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

function loadGroupRowsIntoPages() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const from = src.indexOf("function groupRowsIntoPages(");
  const to = src.indexOf("function setupFxPagination(");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error(
      "No se encuentra groupRowsIntoPages() antes de setupFxPagination() en " +
      "player.html. Si se ha renombrado o movido, actualiza este arnés."
    );
  }
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to), ctx);
  const fn = ctx.groupRowsIntoPages;
  // Los arrays creados dentro del vm pertenecen a otro realm: su prototipo no
  // es el Array de este módulo, y deepStrictEqual falla por eso aunque la
  // estructura sea idéntica. Un round-trip por JSON los trae a este realm sin
  // relajar la comparación de valores.
  return (heights, avail) => JSON.parse(JSON.stringify(fn(heights, avail)));
}

const group = loadGroupRowsIntoPages;

test("si todas las filas caben, sale una sola página", () => {
  assert.deepStrictEqual(group()([50, 50, 50], 300), [[0, 1, 2]]);
});

test("las filas que desbordan pasan a la página siguiente", () => {
  assert.deepStrictEqual(group()([50, 50, 50, 50], 120), [[0, 1], [2, 3]]);
});

test("con muy poco alto cabe una fila por página", () => {
  assert.deepStrictEqual(group()([50, 50, 50, 50], 80), [[0], [1], [2], [3]]);
});

test("menos alto disponible produce más páginas (efecto del pie)", () => {
  const alturas = [40, 40, 40, 40, 40];
  assert.deepStrictEqual(group()(alturas, 200), [[0, 1, 2, 3, 4]]);
  assert.deepStrictEqual(group()(alturas, 150), [[0, 1, 2], [3, 4]]);
});

test("una fila más alta que el espacio disponible se coloca igualmente", () => {
  assert.deepStrictEqual(group()([200], 100), [[0]]);
});

test("sin filas no hay páginas", () => {
  assert.deepStrictEqual(group()([], 300), []);
});

// ── Reparto equilibrado ────────────────────────────────────────────────────
// Llenar la primera página hasta arriba deja huérfana la última: con 8 divisas
// salían 7 y 1, y esa última se estiraba a pantalla completa. Queda feo y no
// se lee mejor. Si hacen falta dos páginas, se reparten a la mitad.

test("ocho filas en dos páginas salen a cuatro y cuatro", () => {
  // Caben 7 por página, pero 7+1 es justo lo que hay que evitar
  const alturas = new Array(8).fill(100);
  const p = group()(alturas, 750);
  assert.strictEqual(p.length, 2);
  assert.deepStrictEqual(p.map(x => x.length), [4, 4]);
});

test("cuando no es divisible, la primera página lleva una más", () => {
  const p = group()(new Array(9).fill(100), 750);
  assert.deepStrictEqual(p.map(x => x.length), [5, 4]);
});

test("no se deja nunca una página con una sola fila si se puede evitar", () => {
  for (const n of [8, 9, 11, 13, 15]) {
    const p = group()(new Array(n).fill(100), 750);
    const minimo = Math.min(...p.map(x => x.length));
    assert.ok(minimo > 1,
      `con ${n} filas queda una pagina de ${minimo}: ${JSON.stringify(p.map(x => x.length))}`);
  }
});

test("si caben todas en una, no se parten", () => {
  const p = group()(new Array(5).fill(100), 750);
  assert.deepStrictEqual(p.map(x => x.length), [5]);
});

test("tres páginas también se reparten parejas", () => {
  const p = group()(new Array(15).fill(100), 750);   // caben 7 -> 3 paginas
  assert.deepStrictEqual(p.map(x => x.length), [5, 5, 5]);
});

test("no se pierde ni se repite ninguna fila al repartir", () => {
  const p = group()(new Array(13).fill(100), 750);
  const todas = p.flat();
  assert.strictEqual(todas.length, 13);
  assert.deepStrictEqual(todas, [...todas].sort((a, b) => a - b), "deben ir en orden");
  assert.strictEqual(new Set(todas).size, 13, "sin repetidas");
});
