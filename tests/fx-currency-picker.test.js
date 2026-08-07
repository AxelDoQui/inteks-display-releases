/**
 * Tests del selector de país/moneda del admin.
 *
 * Mismo arnés que los demás: extrae del propio admin.html los bloques que hacen
 * falta y los ejecuta en un vm, para no probar copias que se desincronicen.
 * Se extraen tres trozos porque no son contiguos en el archivo.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.join(__dirname, "..");
const ADMIN = path.join(ROOT, "admin.html");
const FLAGS_DIR = path.join(ROOT, "vendor", "flags");

function slice(src, from, to, what) {
  const a = src.indexOf(from);
  const b = src.indexOf(to, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra el bloque de ${what} en admin.html ` +
                    `(marcadores "${from}" .. "${to}"). Si se ha movido, actualiza el arnés.`);
  }
  return src.slice(a, b);
}

function loadPicker() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const code = [
    slice(src, "const CURRENCY_DB = [", "const CODE_MAP", "CURRENCY_DB"),
    slice(src, "function flagCode(", "function flagImg(", "flagCode"),
    slice(src, "function fxRowFromCurrency(", "// ── FX Module", "fxRowFromCurrency"),
  ].join("\n");
  const ctx = {};
  vm.createContext(ctx);
  // Las declaraciones `function` sí se cuelgan del objeto de contexto, pero
  // `const` no: vive en el ámbito léxico del script. Hay que exportarla a mano.
  vm.runInContext(code + "\n;__db = CURRENCY_DB;", ctx);
  // Todo lo que salga del vm pasa por JSON: los objetos creados dentro
  // pertenecen a otro realm y deepStrictEqual los rechaza por prototipo aunque
  // la estructura sea idéntica.
  const norm = v => (v === undefined || v === null ? v : JSON.parse(JSON.stringify(v)));
  return {
    fxRowFromCurrency: code2 => norm(ctx.fxRowFromCurrency(code2)),
    CURRENCY_DB: norm(ctx.__db),
  };
}

test("rellena la fila a partir del código de moneda", () => {
  const { fxRowFromCurrency } = loadPicker();
  assert.deepStrictEqual(
    fxRowFromCurrency("ARS"),
    { flag: "ar", country: "Argentina", currency: "Peso argentino", code: "ARS", rate: "" }
  );
});

test("convierte el emoji de la base en código de país de dos letras", () => {
  const { fxRowFromCurrency } = loadPicker();
  // El campo de bandera tiene maxlength=2: un emoji ocupa 4 unidades UTF-16 y
  // se truncaría, así que la conversión no es cosmética.
  assert.strictEqual(fxRowFromCurrency("USD").flag, "us");
  assert.strictEqual(fxRowFromCurrency("JPY").flag, "jp");
  assert.strictEqual(fxRowFromCurrency("EUR").flag, "eu");
});

test("un código desconocido no devuelve nada", () => {
  const { fxRowFromCurrency } = loadPicker();
  assert.strictEqual(fxRowFromCurrency("ZZZ"), null);
  assert.strictEqual(fxRowFromCurrency(""), null);
});

test("la tasa se deja vacía para que la escriba el usuario", () => {
  const { fxRowFromCurrency } = loadPicker();
  assert.strictEqual(fxRowFromCurrency("COP").rate, "");
});

test("toda divisa con bandera tiene su SVG en vendor/flags", () => {
  const { CURRENCY_DB, fxRowFromCurrency } = loadPicker();
  const disponibles = new Set(
    fs.readdirSync(FLAGS_DIR).filter(f => f.endsWith(".svg")).map(f => f.slice(0, -4))
  );
  const rotas = CURRENCY_DB
    .map(c => fxRowFromCurrency(c.code))
    .filter(r => r && r.flag && !disponibles.has(r.flag))
    .map(r => `${r.code} (${r.flag})`);
  assert.deepStrictEqual(rotas, [],
    "Estas divisas apuntan a una bandera que no existe en vendor/flags: " + rotas.join(", "));
});

test("XAF es la única sin bandera, y se queda vacía en vez de rota", () => {
  const { fxRowFromCurrency, CURRENCY_DB } = loadPicker();
  // África Central no tiene emoji de país, así que no hay código ISO posible.
  assert.strictEqual(fxRowFromCurrency("XAF").flag, "");
  const sinBandera = CURRENCY_DB
    .map(c => fxRowFromCurrency(c.code))
    .filter(r => r && !r.flag)
    .map(r => r.code);
  assert.deepStrictEqual(sinBandera, ["XAF"]);
});
