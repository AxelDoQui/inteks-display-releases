/**
 * Carpetas y etiquetas en la Librería del panel (lógica pura).
 *
 * Ejecutar:  node --test tests/organizar.test.js
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
  { id: "a", type: "image", name: "uno.png", folder: "Verano", tags: ["Oferta", "Nuevo"] },
  { id: "b", type: "image", name: "dos.png", folder: "Tienda & Cía", tags: ["oferta"] },
  { id: "c", type: "video", name: "tres.mp4" },
  { id: "d", type: "image", name: "cuatro.png", folder: "Año nuevo", tags: [] },
];
const ids = (opc) => Array.from(cargar().filtrarOrdenar(items, {}, { orden: "nombre", ...opc }), (i) => i.id).sort();

test("sin filtro de carpeta: todo", () => {
  assert.deepStrictEqual(ids({}), ["a", "b", "c", "d"]);
  assert.deepStrictEqual(ids({ carpeta: "all" }), ["a", "b", "c", "d"]);
});
test("filtra por carpeta sin fijarse en acentos ni mayúsculas", () => {
  assert.deepStrictEqual(ids({ carpeta: "c:verano" }), ["a"]);
  assert.deepStrictEqual(ids({ carpeta: "c:ANO NUEVO" }), ["d"]);
  assert.deepStrictEqual(ids({ carpeta: "c:Tienda & Cía" }), ["b"]);
});
test("none deja los que no tienen carpeta", () => {
  assert.deepStrictEqual(ids({ carpeta: "none" }), ["c"]);
});
test("una carpeta llamada «todas» o «__sin__» no choca con los valores especiales", () => {
  const raros = [
    { id: "x", type: "image", name: "x", folder: "todas" },
    { id: "y", type: "image", name: "y", folder: "__sin__" },
    { id: "z", type: "image", name: "z" },
  ];
  const f = (carpeta) => Array.from(cargar().filtrarOrdenar(raros, {}, { orden: "nombre", carpeta }), (i) => i.id).sort();
  assert.deepStrictEqual(f("c:todas"), ["x"]);
  assert.deepStrictEqual(f("c:__sin__"), ["y"]);
  assert.deepStrictEqual(f("none"), ["z"]);
  assert.deepStrictEqual(f("all"), ["x", "y", "z"]);
});
test("filtra por una y por dos etiquetas (todas)", () => {
  assert.deepStrictEqual(ids({ etiquetas: ["oferta"] }), ["a", "b"]);
  assert.deepStrictEqual(ids({ etiquetas: ["OFERTA", "nuevo"] }), ["a"]);
  assert.deepStrictEqual(ids({ etiquetas: ["oferta", "inexistente"] }), []);
  assert.deepStrictEqual(ids({ etiquetas: [] }), ["a", "b", "c", "d"]);
});
test("el texto también busca en carpeta y etiquetas", () => {
  assert.deepStrictEqual(ids({ texto: "verano" }), ["a"]);
  assert.deepStrictEqual(ids({ texto: "nuevo" }), ["a", "d"]);
  assert.deepStrictEqual(ids({ texto: "tres" }), ["c"]);
});
test("combina carpeta, etiqueta y tipo", () => {
  assert.deepStrictEqual(ids({ carpeta: "c:verano", etiquetas: ["oferta"], tipo: "image" }), ["a"]);
  assert.deepStrictEqual(ids({ carpeta: "c:verano", tipo: "video" }), []);
});
test("listasDeOrganizacion: únicas y ordenadas en español", () => {
  const l = cargar().listasDeOrganizacion([
    ...items,
    { id: "e", type: "image", name: "e", folder: "verano", tags: ["ÁRBOL", "zeta", "nuevo"] },
    { id: "f", type: "image", name: "f", folder: "  ", tags: "mal" },
  ]);
  assert.deepStrictEqual(Array.from(l.carpetas), ["Año nuevo", "Tienda & Cía", "Verano"]);
  assert.deepStrictEqual(Array.from(l.etiquetas), ["ÁRBOL", "Nuevo", "Oferta", "zeta"]);
});
test("listasDeOrganizacion con lista vacía", () => {
  const l = cargar().listasDeOrganizacion([]);
  assert.strictEqual(l.carpetas.length, 0);
  assert.strictEqual(l.etiquetas.length, 0);
});
