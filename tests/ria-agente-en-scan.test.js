/**
 * Tests de scanPage() cuando una moneda trae varios agentes de pago (Ria).
 *
 * elegirAgente() (ver tests/ria-eleccion-agente.test.js) ya decide bien entre
 * varios agentes; esto prueba que scanPage() la usa de verdad: agrupa las
 * filas por moneda y, cuando hay más de una, aplica la preferencia guardada.
 * Se carga parser.js entero en un vm con un `document` de mentira, para no
 * depender de un navegador real.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PARSER = path.join(__dirname, "..", "inteks-extension", "parser.js");

// `filas`: texto de cada elemento que capturaría el selector real (tr, li...).
// Con newlines internos, como el innerText real de una fila con varias
// celdas -- scanPage ya colapsa los espacios antes de analizar el texto.
function cargar(filas) {
  const src = fs.readFileSync(PARSER, "utf8");
  const ctx = {
    window: {},
    document: {
      body: { innerText: filas.join("\n") },
      querySelectorAll: () => filas.map(t => ({ innerText: t })),
    },
  };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx.window.SignalosParser;
}

// Incluye a propósito "4-72 Servici" (agente real de Ria con dígitos en el
// nombre): antes confundía el "4" con la tasa (ver
// tests/extension-rate-agent-digits.test.js para el arnés de extractRate).
const COLOMBIA = [
  "Ria Colombia\n\n\n3650\n\nCOP",
  "Bancolombia\n\n\n3606\n\nCOP",
  "Davivienda\n\n\n3641\n\nCOP",
  "Almacenes Ex\n\n\n3607\n\nCOP",
  "4-72 Servici\n\n\n3660\n\nCOP",
];

// Con solo una moneda en pantalla, scanPage cae al fallback de texto plano
// (results.length < 2); se añade una segunda moneda para no depender de eso.
const HONDURAS = ["Banco Ficohs\n\n\n30,86\n\nHNL"];

test("con preferencia configurada, se elige ese agente aunque otro pague más", () => {
  const p = cargar([...COLOMBIA, ...HONDURAS]);
  const filas = p.scanPage({ COP: ["Davivienda"] });
  const cop = filas.find(f => f.code === "COP");
  assert.strictEqual(cop.agent, "Davivienda");
  assert.strictEqual(cop.rate, "3641");
  assert.strictEqual(cop.agentMotivo, "preferencia");
  assert.strictEqual(cop.agentAlternativa.agent, "4-72 Servici",
    "avisa de que 4-72 paga mas, sin cambiar la eleccion");
});

test("sin preferencias, se coge la tasa más alta (con dígitos en el nombre incluido)", () => {
  const p = cargar([...COLOMBIA, ...HONDURAS]);
  const filas = p.scanPage({});
  const cop = filas.find(f => f.code === "COP");
  assert.strictEqual(cop.rate, "3660");
  assert.strictEqual(cop.agent, "4-72 Servici");
  assert.strictEqual(cop.agentMotivo, "sin-preferencia");
});

test("scanPage() sin argumento no revienta (preferencias opcionales)", () => {
  const p = cargar([...COLOMBIA, ...HONDURAS]);
  assert.doesNotThrow(() => p.scanPage());
});

test("una moneda con una sola fila no lleva campos de agente", () => {
  const p = cargar(["Banco Ficohs\n\n\n30,86\n\nHNL", ...COLOMBIA]);
  const filas = p.scanPage({});
  const hnl = filas.find(f => f.code === "HNL");
  assert.strictEqual(hnl.rate, "30,86");
  assert.strictEqual(hnl.agent, undefined, "sin varios candidatos no hay nada que decidir");
  assert.strictEqual(hnl.agentMotivo, undefined);
  // Y la forma del objeto es la misma de siempre: flag, country, currency, code, rate.
  assert.deepStrictEqual(Object.keys(hnl).sort(), ["code", "country", "currency", "flag", "rate"]);
});

test("con varios candidatos, se listan todos en agentOpciones para poder elegir con un clic", () => {
  const p = cargar([...COLOMBIA, ...HONDURAS]);
  const filas = p.scanPage({});
  const cop = filas.find(f => f.code === "COP");
  assert.strictEqual(cop.agentOpciones.length, COLOMBIA.length);
  assert.ok(cop.agentOpciones.some(o => o.agent === "Davivienda" && o.rate === "3641"));
  assert.ok(cop.agentOpciones.some(o => o.agent === "Ria Colombia" && o.rate === "3650"));
  // El panel lateral solo ofrece el <select> cuando hay más de un candidato;
  // en el caso de una sola fila, agentOpciones no debe aparecer.
  const hnl = filas.find(f => f.code === "HNL");
  assert.strictEqual(hnl.agentOpciones, undefined);
});

test("extractAgent separa el nombre del agente del número", () => {
  const p = cargar([]);
  const cur = p.CODE_MAP.COP;
  assert.strictEqual(p.extractAgent("Ria Colombia 3650 COP", cur), "Ria Colombia");
  assert.strictEqual(p.extractAgent("Davivienda 3641 COP", cur), "Davivienda");
});
