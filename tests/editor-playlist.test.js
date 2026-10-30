/**
 * Editor de playlist del panel (lógica pura).
 *
 * Ejecutar:  node --test tests/editor-playlist.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Editor de playlist";
const FIN = "// ── fin del editor de playlist";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) throw new Error("No se encuentra el bloque del editor de playlist en admin.html");
  const ctx = { String, Array, Object, Math, Number, Set };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}
const E = cargar();
const img = (id, d) => ({ id, type: "image", name: id, duration: d });

test("resumenPlaylist: vacía", () => {
  const r = E.resumenPlaylist([], []);
  assert.strictEqual(r.n, 0);
  assert.strictEqual(r.texto, "Sin contenido");
});
test("resumenPlaylist: una imagen de 8 s", () => {
  const r = E.resumenPlaylist([img("a", 8)], []);
  assert.strictEqual(r.texto, "1 elemento · 8 s por vuelta");
  assert.strictEqual(r.segundos, 8);
});
test("resumenPlaylist: tres imágenes suman segundos", () => {
  assert.strictEqual(E.resumenPlaylist([img("a", 8), img("b", 8), img("c", 15)], []).texto, "3 elementos · 31 s por vuelta");
});
test("resumenPlaylist: minutos y segundos", () => {
  const pl = Array.from({ length: 8 }, (_, i) => img("i" + i, 12));
  assert.strictEqual(E.resumenPlaylist(pl, []).texto, "8 elementos · 1 min 36 s por vuelta");
});
test("resumenPlaylist: minuto exacto sin segundos", () => {
  assert.strictEqual(E.resumenPlaylist([img("a", 60)], []).texto, "1 elemento · 1 min por vuelta");
});
test("resumenPlaylist: vídeo sin duración añade + vídeos", () => {
  const r = E.resumenPlaylist([img("a", 8), { id: "v", type: "video", name: "v" }], []);
  assert.strictEqual(r.videosSinDuracion, 1);
  assert.strictEqual(r.texto, "2 elementos · 8 s por vuelta + vídeos");
});
test("resumenPlaylist: el vídeo no suma segundos aunque traiga duration", () => {
  const r = E.resumenPlaylist([{ id: "v", type: "video", name: "v", duration: 20 }, img("a", 8)], []);
  assert.strictEqual(r.segundos, 8);
  assert.strictEqual(r.videosSinDuracion, 1);
  assert.strictEqual(r.texto, "2 elementos · 8 s por vuelta + vídeos");
});
test("resumenPlaylist: un paquete cuenta como un elemento", () => {
  const r = E.resumenPlaylist([img("a", 8), { type: "package", pkg_id: "p1" }], []);
  assert.strictEqual(r.n, 2);
  assert.strictEqual(r.segundos, 8);
});

test("idsEnPlaylist ignora paquetes", () => {
  const s = E.idsEnPlaylist([img("a", 8), { type: "package", pkg_id: "p1" }, img("b", 8)]);
  assert.deepStrictEqual(Array.from(s).sort(), ["a", "b"]);
});
test("idsEnPlaylist con playlist vacía o nula", () => {
  assert.strictEqual(E.idsEnPlaylist(null).size, 0);
});

test("insertarEn: inicio, medio y final", () => {
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2, 3], ["x"], 0)), ["x", 1, 2, 3]);
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2, 3], ["x", "y"], 1)), [1, "x", "y", 2, 3]);
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2, 3], ["x"], 3)), [1, 2, 3, "x"]);
});
test("insertarEn: fuera de rango o no numérica va al final", () => {
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2], ["x"], 99)), [1, 2, "x"]);
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2], ["x"], -1)), [1, 2, "x"]);
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2], ["x"], undefined)), [1, 2, "x"]);
  assert.deepStrictEqual(Array.from(E.insertarEn([1, 2], ["x"], "a")), [1, 2, "x"]);
});
test("insertarEn no muta", () => {
  const l = [1, 2], n = ["x"];
  const r = E.insertarEn(l, n, 0);
  assert.deepStrictEqual(l, [1, 2]);
  assert.deepStrictEqual(n, ["x"]);
  assert.notStrictEqual(r, l);
});

test("ajustesDistintosDeDefecto", () => {
  const f = E.ajustesDistintosDeDefecto;
  assert.strictEqual(f({ playlist: [img("a", 8)] }), false);
  assert.strictEqual(f({}), false);
  assert.strictEqual(f({ priority_every: 4, safe_margin: 0 }), false);
  assert.strictEqual(f({ priority_every: 6 }), true);
  assert.strictEqual(f({ safe_margin: 3 }), true);
  assert.strictEqual(f({ playlist: [{ id: "a", priority: true }] }), true);
});

test("resumenPlaylist: paquete suma sus imágenes y marca sus vídeos", () => {
  const items = [img("a", 8), img("b", 8), { id: "v", type: "video", name: "v" }];
  const paquetes = [{ id: "p1", items: [{ id: "a", duration: 10 }, { id: "b" }, { id: "v" }, { id: "borrado", duration: 99 }] }];
  const r = E.resumenPlaylist([img("x", 5), { type: "package", pkg_id: "p1" }], items, paquetes);
  assert.strictEqual(r.n, 2);
  assert.strictEqual(r.segundos, 5 + 10 + 8);
  assert.strictEqual(r.videosSinDuracion, 1);
  assert.strictEqual(r.texto, "2 elementos · 23 s por vuelta + vídeos");
});
test("resumenPlaylist: paquete con itemIds antiguos usa la librería", () => {
  const items = [{ id: "a", type: "image", name: "a", duration: 12 }, { id: "b", type: "image", name: "b" }];
  const r = E.resumenPlaylist([{ type: "package", pkg_id: "p1" }], items, [{ id: "p1", itemIds: ["a", "b"] }]);
  assert.strictEqual(r.segundos, 20);
});
test("resumenPlaylist: paquete inexistente cuenta como un elemento", () => {
  const r = E.resumenPlaylist([{ type: "package", pkg_id: "zz" }], [], []);
  assert.strictEqual(r.n, 1);
  assert.strictEqual(r.segundos, 0);
});
