/**
 * Filtrar y ordenar la Librería del panel (lógica pura).
 *
 * Ejecutar:  node --test tests/libreria-filtro.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Librería: filtrar y ordenar";
const FIN = "// ── fin de filtrar y ordenar";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) throw new Error("No se encuentra el bloque de filtrar y ordenar en admin.html");
  const ctx = { String, Array, Object, Math, Number };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const items = [
  { id: "a", type: "image", name: "Cartel Verano.png" },
  { id: "b", type: "video", name: "spot.mp4" },
  { id: "c", type: "fx", name: "Divisas" },
  { id: "d", type: "image", name: "árbol.jpg" },
];
const info = {
  a: { size: 500, created: 100, uses: [{}, {}] },
  b: { size: 9000, created: 300, uses: [] },
  d: { size: 20, created: 200, uses: [{}] },
};
const ids = (opc) => Array.from(cargar().filtrarOrdenar(items, info, opc), (i) => i.id);

test("filtra por texto", () => {
  assert.deepStrictEqual(ids({ texto: "verano" }), ["a"]);
});
test("el texto ignora mayúsculas y acentos", () => {
  assert.deepStrictEqual(ids({ texto: "ARBOL" }), ["d"]);
});
test("filtra por tipo video", () => {
  assert.deepStrictEqual(ids({ tipo: "video" }), ["b"]);
});
test("tipo otros = ni imagen ni vídeo", () => {
  assert.deepStrictEqual(ids({ tipo: "otros" }), ["c"]);
});
test("orden nuevos: sin fecha al final", () => {
  assert.deepStrictEqual(ids({ orden: "nuevos" }), ["b", "d", "a", "c"]);
});
test("orden nombre sin acentos", () => {
  assert.deepStrictEqual(ids({ orden: "nombre" }), ["d", "a", "c", "b"]);
});
test("orden tamano", () => {
  assert.deepStrictEqual(ids({ orden: "tamano" }), ["b", "a", "d", "c"]);
});
test("orden usados, empate por nombre", () => {
  assert.deepStrictEqual(ids({ orden: "usados" }), ["a", "d", "c", "b"]);
});
test("funciona con info vacía", () => {
  const r = cargar().filtrarOrdenar(items, {}, { orden: "nuevos" });
  assert.strictEqual(r.length, 4);
});
test("formatoTamano", () => {
  const { formatoTamano } = cargar();
  assert.strictEqual(formatoTamano(0), "0 B");
  assert.strictEqual(formatoTamano(1536), "1,5 KB");
  assert.strictEqual(formatoTamano(48 * 1024 * 1024), "48 MB");
  assert.strictEqual(formatoTamano(undefined), "");
});
