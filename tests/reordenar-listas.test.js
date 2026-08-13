/**
 * Tests de moverEnLista(), la funcion que reordena playlists y filas de divisas.
 *
 * admin.html es un HTML monolitico con el JS inline, asi que no hay nada que
 * importar. En vez de copiar la funcion aqui -una copia se desincroniza al
 * primer cambio y dejaria de probar nada-, este arnes la EXTRAE tal cual esta
 * en admin.html y la ejecuta en un contexto vm.
 *
 * Que se prueba y por que importa: esta funcion la usan el arrastre Y los
 * botones subir/bajar. Si pierde o duplica un elemento, una playlist de tienda
 * se corrompe sin que nadie lo note hasta que falta un contenido.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");

function cargarMoverEnLista() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const from = src.indexOf("function moverEnLista(");
  const to = src.indexOf("function moverFxRow(");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error(
      "No se encuentran moverEnLista()/moverFxRow() en admin.html. " +
      "Si se han renombrado, actualiza los marcadores de este arnes."
    );
  }
  const ctx = {};
  vm.createContext(ctx);
  // Se expone con var para que quede colgada del contexto: las funciones
  // declaradas con "function" si se cuelgan, pero const y let no.
  vm.runInContext(src.slice(from, to) + ";var _m = moverEnLista;", ctx);
  return ctx._m;
}

const moverEnLista = cargarMoverEnLista();

test("mueve un elemento hacia abajo", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 0, 1), true);
  assert.deepStrictEqual(l, ["b", "a", "c"]);
});

test("mueve un elemento hacia arriba", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 2, 1), true);
  assert.deepStrictEqual(l, ["a", "c", "b"]);
});

test("subir el primero no hace nada", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 0, -1), false);
  assert.deepStrictEqual(l, ["a", "b", "c"]);
});

test("bajar el ultimo no hace nada", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 2, 3), false);
  assert.deepStrictEqual(l, ["a", "b", "c"]);
});

test("moverse a la misma posicion no hace nada", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 1, 1), false);
  assert.deepStrictEqual(l, ["a", "b", "c"]);
});

test("nunca pierde ni duplica elementos", () => {
  const l = ["a", "b", "c", "d", "e"];
  moverEnLista(l, 4, 0);
  moverEnLista(l, 1, 3);
  moverEnLista(l, 0, 2);
  assert.strictEqual(l.length, 5);
  assert.deepStrictEqual([...l].sort(), ["a", "b", "c", "d", "e"]);
});

test("indices invalidos no rompen la lista", () => {
  const l = ["a", "b"];
  assert.strictEqual(moverEnLista(l, null, 1), false);
  assert.strictEqual(moverEnLista(l, 0, null), false);
  assert.strictEqual(moverEnLista(l, 9, 0), false);
  assert.deepStrictEqual(l, ["a", "b"]);
});

test("una lista vacia no revienta", () => {
  const l = [];
  assert.strictEqual(moverEnLista(l, 0, 1), false);
  assert.deepStrictEqual(l, []);
});
