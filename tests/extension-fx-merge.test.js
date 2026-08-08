/**
 * Tests del emparejamiento de tasas de la extensión.
 *
 * Cuando cargas un módulo guardado del admin, lo detectado en la página tiene
 * que actualizar por código las filas que ya tienes, sin perder las que esa
 * página no cotiza. Es la lógica central de la función y no depende del DOM,
 * así que se extrae de sidebar.js y se ejecuta en un vm.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SIDEBAR = path.join(__dirname, "..", "inteks-extension", "sidebar.js");

// Ejecuta applyDetectedToSelected() con un estado dado y devuelve el resultado.
function merge(guardadas, detectadas) {
  const src = fs.readFileSync(SIDEBAR, "utf8");
  const from = src.indexOf("function applyDetectedToSelected(");
  const to = src.indexOf("// Divisas detectadas enviadas por content.js", from);
  if (from === -1 || to === -1 || to <= from) {
    throw new Error("No se encuentra applyDetectedToSelected() en sidebar.js. " +
                    "Si se ha movido o renombrado, actualiza este arnés.");
  }
  // Se cargan como las deja pickModule(): la tasa guardada también en `was`.
  const ctx = {
    selectedRows: guardadas.map(r => ({ ...r, was: r.rate, changed: false, missing: true })),
    detectedRows: detectadas,
  };
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to) + "\n;applyDetectedToSelected();", ctx);
  return JSON.parse(JSON.stringify(ctx.selectedRows));
}

const GUARDADAS = [
  { flag: "ar", country: "Argentina", currency: "Peso", code: "ARS", rate: "1716" },
  { flag: "co", country: "Colombia", currency: "Peso", code: "COP", rate: "4000" },
  { flag: "hn", country: "Honduras", currency: "Lempira", code: "HNL", rate: "30,63" },
];

test("una tasa distinta en la página actualiza la fila y se marca", () => {
  const r = merge(GUARDADAS, [{ code: "ARS", rate: "1800" }]);
  const ars = r.find(x => x.code === "ARS");
  assert.strictEqual(ars.rate, "1800");
  assert.strictEqual(ars.was, "1716", "debe conservar la anterior para poder enseñarla");
  assert.strictEqual(ars.changed, true);
});

test("una tasa igual no se marca como cambiada", () => {
  const r = merge(GUARDADAS, [{ code: "ARS", rate: "1716" }]);
  const ars = r.find(x => x.code === "ARS");
  assert.strictEqual(ars.changed, false);
  assert.strictEqual(ars.missing, false, "aparece en la página aunque no cambie");
});

test("lo que la página no cotiza conserva su tasa guardada", () => {
  const r = merge(GUARDADAS, [{ code: "ARS", rate: "1800" }]);
  const hnl = r.find(x => x.code === "HNL");
  assert.strictEqual(hnl.rate, "30,63", "no debe vaciarse ni ponerse a cero");
  assert.strictEqual(hnl.missing, true);
  assert.strictEqual(hnl.changed, false);
});

test("el emparejamiento no distingue mayúsculas en el código", () => {
  const r = merge(GUARDADAS, [{ code: "cop", rate: "4100" }]);
  assert.strictEqual(r.find(x => x.code === "COP").rate, "4100");
});

test("una divisa de la página que no está en el módulo no se cuela sola", () => {
  const r = merge(GUARDADAS, [{ code: "BRL", rate: "5,2" }]);
  assert.strictEqual(r.length, 3, "el módulo cargado manda; lo nuevo se añade a mano");
  assert.ok(!r.some(x => x.code === "BRL"));
});

test("sin nada detectado, el módulo queda intacto", () => {
  const r = merge(GUARDADAS, []);
  assert.deepStrictEqual(r.map(x => x.rate), ["1716", "4000", "30,63"]);
  assert.ok(r.every(x => x.missing && !x.changed));
});

test("se actualizan varias filas a la vez", () => {
  const r = merge(GUARDADAS, [{ code: "ARS", rate: "1800" }, { code: "COP", rate: "4100" }]);
  assert.deepStrictEqual(r.map(x => x.rate), ["1800", "4100", "30,63"]);
  assert.deepStrictEqual(r.map(x => x.changed), [true, true, false]);
});
