/**
 * Tests de la elección de agente en Ria.
 *
 * Ria ofrece VARIOS agentes de pago por país, cada uno con su tasa y a veces en
 * monedas distintas. El criterio real del negocio no es «la tasa más alta»:
 * en Colombia se recomienda Davivienda (3.613,36) aunque 4-72 pague más
 * (3.645), porque 4-72 es el servicio postal. Y Ria Colombia se descarta por
 * ser un servicio nuevo. Eso no se deduce de ningún número: manda una lista de
 * preferencias que fija el usuario.
 *
 * Los datos son los reales de las capturas del 2026-08-08.
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
  const from = src.indexOf("function normalizeAgent(");
  const to = src.indexOf("// Recorre líneas de texto", from);
  if (from === -1 || to === -1 || to <= from) {
    throw new Error("No se encuentra el bloque de elección de agente en parser.js " +
                    "(de normalizeAgent a 'Recorre líneas de texto').");
  }
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to), ctx);
  const norm = v => (v == null ? v : JSON.parse(JSON.stringify(v)));
  return {
    elegirAgente: (c, p, m) => norm(ctx.elegirAgente(c, p, m)),
    normalizeAgent: a => ctx.normalizeAgent(a),
  };
}

// Colombia tal y como sale en pantalla, con los nombres truncados por Ria
const COLOMBIA = [
  { agent: "Ria Colombia",    rate: "3645",    currency: "COP" },
  { agent: "Bancolombia",     rate: "3604,16", currency: "COP" },
  { agent: "Banco W (Pag",    rate: "3597,26", currency: "COP" },
  { agent: "Davivienda",      rate: "3613,36", currency: "COP" },
  { agent: "4-72 Servici",    rate: "3645",    currency: "COP" },
  { agent: "Almacenes Ex",    rate: "3605,31", currency: "COP" },
];

const PARAGUAY = [
  { agent: "Banco Famili", rate: "6900", currency: "PYG" },
  { agent: "Maxicambios",  rate: "1,10", currency: "USD" },
];

const HONDURAS = [
  { agent: "Banco Atlant", rate: "30,84", currency: "HNL" },
  { agent: "Banco Promer", rate: "30,84", currency: "HNL" },
  { agent: "Banco Lafise", rate: "30,80", currency: "HNL" },
  { agent: "Banco De Occ", rate: "30,84", currency: "HNL" },
  { agent: "Davivienda H", rate: "30,80", currency: "HNL" },
  { agent: "Banco Ficohs", rate: "30,86", currency: "HNL" },
];

// ── La preferencia manda sobre la tasa ─────────────────────────────────────

test("se elige el preferido aunque otro pague más", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(COLOMBIA, ["Davivienda", "Bancolombia"], "COP");
  assert.strictEqual(r.elegido.agent, "Davivienda");
  assert.strictEqual(r.elegido.rate, "3613,36");
  assert.strictEqual(r.motivo, "preferencia");
});

test("se respeta el orden de la lista, no la tasa", () => {
  const { elegirAgente } = cargar();
  // Bancolombia (3604,16) va antes que Almacenes (3605,31) en la lista
  const r = elegirAgente(COLOMBIA, ["Bancolombia", "Almacenes Exito"], "COP");
  assert.strictEqual(r.elegido.agent, "Bancolombia");
});

test("si el primero de la lista no aparece, se pasa al siguiente", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(COLOMBIA, ["Banco Que No Existe", "Davivienda"], "COP");
  assert.strictEqual(r.elegido.agent, "Davivienda");
});

// ── Nombres truncados: Ria corta las etiquetas ─────────────────────────────

test("empareja aunque la página trunque el nombre", () => {
  const { elegirAgente } = cargar();
  // En pantalla pone "Almacenes Ex"; el usuario escribe el nombre completo
  const r = elegirAgente(COLOMBIA, ["Almacenes Exito"], "COP");
  assert.strictEqual(r.elegido.agent, "Almacenes Ex");
});

test("empareja cuando la página alarga el nombre", () => {
  const { elegirAgente } = cargar();
  // En Honduras la etiqueta es "Davivienda H"; el usuario escribe "Davivienda"
  const r = elegirAgente(HONDURAS, ["Davivienda"], "HNL");
  assert.strictEqual(r.elegido.agent, "Davivienda H");
});

test("no empareja agentes distintos que empiezan igual", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(HONDURAS, ["Banco Ficohsa"], "HNL");
  assert.strictEqual(r.elegido.agent, "Banco Ficohs",
    "Banco Ficohs si, pero no Banco Lafise ni Banco Promer");
});

// ── Aviso cuando otro paga bastante más ────────────────────────────────────

test("avisa si otro agente paga más, sin cambiar la elección", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(COLOMBIA, ["Davivienda"], "COP");
  assert.strictEqual(r.elegido.agent, "Davivienda");
  assert.ok(r.mejorAlternativa, "deberia avisar de que hay algo mejor");
  assert.strictEqual(r.mejorAlternativa.agent, "Ria Colombia");
  assert.ok(r.mejorAlternativa.diffPct > 0.5,
    "la diferencia debe expresarse en porcentaje: " + r.mejorAlternativa.diffPct);
});

test("no avisa si el preferido ya es el que más paga", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(HONDURAS, ["Banco Ficohsa"], "HNL");
  assert.strictEqual(r.mejorAlternativa, null);
});

// ── Moneda local: no comparar peras con manzanas ───────────────────────────

test("solo se consideran los agentes de la moneda local", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(PARAGUAY, ["Banco Familiar"], "PYG");
  assert.strictEqual(r.elegido.agent, "Banco Famili");
  assert.ok(r.descartados.some(d => d.agent === "Maxicambios" && d.motivo === "otra-moneda"),
    "Maxicambios cotiza en USD y debe quedar descartado por moneda");
});

test("un agente en otra moneda nunca gana aunque su número sea mayor", () => {
  const { elegirAgente } = cargar();
  // Sin preferencias, 6900 PYG debe ganar a 1,10 USD por ser la moneda local
  const r = elegirAgente(PARAGUAY, [], "PYG");
  assert.strictEqual(r.elegido.agent, "Banco Famili");
});

// ── Sin preferencias configuradas ──────────────────────────────────────────

test("sin lista de preferencias se coge la más alta, y se avisa", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(COLOMBIA, [], "COP");
  assert.strictEqual(r.elegido.rate, "3645");
  assert.strictEqual(r.motivo, "sin-preferencia",
    "hay que poder distinguir una eleccion tuya de una por defecto");
});

test("si ningún preferido aparece, se coge la más alta y se avisa", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(COLOMBIA, ["Banco Inexistente"], "COP");
  assert.strictEqual(r.motivo, "sin-preferencia");
  assert.strictEqual(r.elegido.rate, "3645");
});

test("sin ningún agente en la moneda local no se elige nada", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente(PARAGUAY, ["Banco Familiar"], "EUR");
  assert.strictEqual(r.elegido, null);
  assert.strictEqual(r.motivo, "ninguno");
});

test("una lista de candidatos vacía no rompe nada", () => {
  const { elegirAgente } = cargar();
  const r = elegirAgente([], ["Davivienda"], "COP");
  assert.strictEqual(r.elegido, null);
  assert.strictEqual(r.motivo, "ninguno");
});

// ── Normalización de nombres ───────────────────────────────────────────────

test("los nombres se comparan sin acentos ni mayúsculas", () => {
  const { normalizeAgent } = cargar();
  assert.strictEqual(normalizeAgent("Almacenes Éxito"), normalizeAgent("almacenes exito"));
  assert.strictEqual(normalizeAgent("  Banco   W  "), "banco w");
});
