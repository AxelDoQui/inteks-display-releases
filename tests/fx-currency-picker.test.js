/**
 * Tests del selector de país/moneda del admin.
 *
 * Mismo arnés que los demás: extrae del propio admin.html los bloques que hacen
 * falta y los ejecuta en un vm, para no probar copias que se desincronicen.
 * Se extraen varios trozos porque no son contiguos en el archivo.
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
    slice(src, "const FX_EXTRA_PAIRS = [", "// ── FX Module", "el selector de divisas"),
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
    CURRENCY_DB: norm(ctx.__db),
    fxPickerOptions: () => norm(ctx.fxPickerOptions()),
    fxRowFromKey: k => norm(ctx.fxRowFromKey(k)),
    fxOptionKey: o => ctx.fxOptionKey(o),
  };
}

const find = (opts, country, code) => opts.find(o => o.country === country && o.code === code);

test("el selector incluye las divisas de la base", () => {
  const { fxPickerOptions } = loadPicker();
  const opts = fxPickerOptions();
  assert.ok(find(opts, "Argentina", "ARS"), "falta Argentina/ARS");
  assert.ok(find(opts, "Colombia", "COP"), "falta Colombia/COP");
});

test("los países que faltaban ya están", () => {
  const { fxPickerOptions } = loadPicker();
  const opts = fxPickerOptions();
  for (const [country, code] of [["Ecuador", "USD"], ["Honduras", "HNL"],
                                 ["Nicaragua", "NIO"], ["Panamá", "PAB"],
                                 ["El Salvador", "USD"], ["Belice", "BZD"],
                                 ["Jamaica", "JMD"]]) {
    assert.ok(find(opts, country, code), `falta ${country}/${code}`);
  }
});

test("un país de doble moneda aparece con sus dos monedas, la local primero", () => {
  const { fxPickerOptions } = loadPicker();
  const ve = fxPickerOptions().filter(o => o.country === "Venezuela").map(o => o.code);
  assert.deepStrictEqual(ve, ["VEF", "USD"],
    "Venezuela debe ofrecer bolívar y dólar, en ese orden");
});

test("los pares con dólar no contaminan la base de monedas", () => {
  const { CURRENCY_DB } = loadPicker();
  // CODE_MAP se construye desde CURRENCY_DB con "el último gana" y lo usa el
  // OCR. Si Venezuela+USD viviera ahí, el OCR etiquetaría como Venezuela
  // cualquier dólar que detectase en una web.
  const usd = CURRENCY_DB.filter(c => c.code === "USD");
  assert.strictEqual(usd.length, 1, "USD debe aparecer una sola vez en CURRENCY_DB");
  assert.strictEqual(usd[0].country, "Estados Unidos");
});

test("rellena la fila a partir de la clave de la opción", () => {
  const { fxPickerOptions, fxRowFromKey, fxOptionKey } = loadPicker();
  const ve = find(fxPickerOptions(), "Venezuela", "USD");
  assert.deepStrictEqual(fxRowFromKey(fxOptionKey(ve)), {
    flag: "ve", country: "Venezuela", currency: "Dólar estadounidense",
    code: "USD", rate: "",
  });
});

test("una clave desconocida no devuelve nada", () => {
  const { fxRowFromKey } = loadPicker();
  assert.strictEqual(fxRowFromKey("zz|ZZZ"), null);
  assert.strictEqual(fxRowFromKey(""), null);
});

test("cada opción tiene una clave única", () => {
  const { fxPickerOptions, fxOptionKey } = loadPicker();
  const keys = fxPickerOptions().map(fxOptionKey);
  const dup = keys.filter((k, i) => keys.indexOf(k) !== i);
  assert.deepStrictEqual(dup, [], "claves duplicadas: " + dup.join(", "));
});

test("las opciones salen ordenadas por país", () => {
  const { fxPickerOptions } = loadPicker();
  const paises = fxPickerOptions().map(o => o.country);
  assert.deepStrictEqual(paises, paises.slice().sort((a, b) => a.localeCompare(b, "es")));
});

test("toda opción con bandera tiene su SVG en vendor/flags", () => {
  const { fxPickerOptions } = loadPicker();
  const disponibles = new Set(
    fs.readdirSync(FLAGS_DIR).filter(f => f.endsWith(".svg")).map(f => f.slice(0, -4))
  );
  const rotas = fxPickerOptions()
    .filter(o => o.flag && !disponibles.has(o.flag))
    .map(o => `${o.country}/${o.code} (${o.flag})`);
  assert.deepStrictEqual(rotas, [],
    "Apuntan a una bandera que no existe en vendor/flags: " + rotas.join(", "));
});

test("XAF es la única sin bandera, y se queda vacía en vez de rota", () => {
  const { fxPickerOptions } = loadPicker();
  // África Central no tiene emoji de país, así que no hay código ISO posible.
  const sinBandera = fxPickerOptions().filter(o => !o.flag).map(o => o.code);
  assert.deepStrictEqual(sinBandera, ["XAF"]);
});
