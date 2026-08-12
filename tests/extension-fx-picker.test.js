/**
 * Selector de país/moneda de la extensión (sidebar.js), añadido cuando se
 * quitó la detección automática: en vez de escanear la página, se busca y se
 * añade de un listado predefinido -igual que en el admin.
 *
 * Mismo arnés que fx-currency-picker.test.js (el equivalente del admin):
 * carga parser.js de verdad en un vm, nada de copias que se desincronicen.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PARSER = path.join(__dirname, "..", "inteks-extension", "parser.js");

// Todo lo que salga del vm pasa por JSON: los objetos creados dentro
// pertenecen a otro realm y deepStrictEqual los rechaza por prototipo aunque
// la estructura sea idéntica. Mismo problema, misma solución que en
// fx-currency-picker.test.js (el equivalente del admin).
const norm = v => (v === undefined || v === null ? v : JSON.parse(JSON.stringify(v)));

function loadParser() {
  const src = fs.readFileSync(PARSER, "utf8");
  const ctx = { window: {} };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  const p = ctx.window.SignalosParser;
  return {
    fxPickerOptions: () => norm(p.fxPickerOptions()),
    fxFilterOptions: (opts, q) => norm(p.fxFilterOptions(opts, q)),
    fxOptionKey: o => p.fxOptionKey(o),
    isoToEmoji: iso => p.isoToEmoji(iso),
  };
}

const find = (opts, country, code) => opts.find(o => o.country === country && o.code === code);

test("el selector incluye países de sobra conocidos", () => {
  const { fxPickerOptions } = loadParser();
  const opts = fxPickerOptions();
  assert.ok(find(opts, "Argentina", "ARS"), "falta Argentina/ARS");
  assert.ok(find(opts, "Colombia", "COP"), "falta Colombia/COP");
  assert.ok(find(opts, "Honduras", "HNL"), "falta Honduras/HNL");
});

test("un país de doble moneda aparece con sus dos monedas, la local primero", () => {
  const { fxPickerOptions } = loadParser();
  const ve = fxPickerOptions().filter(o => o.country === "Venezuela").map(o => o.code);
  assert.deepStrictEqual(ve, ["VES", "USD"]);
});

test("cada opción tiene una clave única", () => {
  const { fxPickerOptions, fxOptionKey } = loadParser();
  const keys = fxPickerOptions().map(fxOptionKey);
  const dup = keys.filter((k, i) => keys.indexOf(k) !== i);
  assert.deepStrictEqual(dup, [], "claves duplicadas: " + dup.join(", "));
});

test("las opciones salen ordenadas por país", () => {
  const { fxPickerOptions } = loadParser();
  const paises = fxPickerOptions().map(o => o.country);
  assert.deepStrictEqual(paises, paises.slice().sort((a, b) => a.localeCompare(b, "es")));
});

// ── Buscador ───────────────────────────────────────────────────────────────

test("buscar por nombre de país", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  const r = fxFilterOptions(fxPickerOptions(), "vene");
  assert.deepStrictEqual(r.map(o => o.code), ["VES", "USD"]);
});

test("la búsqueda ignora acentos en ambos sentidos", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  const opts = fxPickerOptions();
  assert.ok(fxFilterOptions(opts, "panama").some(o => o.country === "Panamá"));
  assert.ok(fxFilterOptions(opts, "Perú").some(o => o.country === "Perú"));
});

test("la búsqueda no distingue mayúsculas", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  assert.ok(fxFilterOptions(fxPickerOptions(), "HONDURAS").some(o => o.country === "Honduras"));
});

test("se puede buscar por código de moneda", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  const opts = fxPickerOptions();
  const esperados = opts.filter(o => o.code === "USD").length;
  assert.strictEqual(fxFilterOptions(opts, "usd").length, esperados);
  assert.ok(esperados > 1, "deberia haber varios paises en dolares");
});

test("se puede buscar por nombre de moneda", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  const r = fxFilterOptions(fxPickerOptions(), "lempira");
  assert.deepStrictEqual(r.map(o => o.country), ["Honduras"]);
});

test("sin texto devuelve todas las opciones", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  const opts = fxPickerOptions();
  assert.strictEqual(fxFilterOptions(opts, "").length, opts.length);
});

test("una búsqueda sin resultados devuelve lista vacía", () => {
  const { fxPickerOptions, fxFilterOptions } = loadParser();
  assert.deepStrictEqual(fxFilterOptions(fxPickerOptions(), "zzzzz"), []);
});

// ── isoToEmoji ───────────────────────────────────────────────────────────────
// El flag de FX_COUNTRIES es un código ISO de 2 letras, como en admin.html.
// La extensión no empaqueta los SVG de /vendor/flags, así que se convierte a
// su emoji equivalente en vez de mantener una segunda tabla de banderas.

test("un código ISO conocido da el emoji de bandera correcto", () => {
  const { isoToEmoji } = loadParser();
  assert.strictEqual(isoToEmoji("ar"), "🇦🇷");
  assert.strictEqual(isoToEmoji("US"), "🇺🇸");   // no distingue mayúsculas
});

test("toda opción del selector convierte a un emoji de bandera de verdad", () => {
  const { fxPickerOptions, isoToEmoji } = loadParser();
  const rotas = fxPickerOptions()
    .filter(o => !/^\p{Regional_Indicator}\p{Regional_Indicator}$/u.test(isoToEmoji(o.flag)))
    .map(o => `${o.country}/${o.code} (${o.flag})`);
  assert.deepStrictEqual(rotas, [], "no convierten a un emoji de bandera valido: " + rotas.join(", "));
});

test("un código inválido no revienta, cae al emoji genérico", () => {
  const { isoToEmoji } = loadParser();
  assert.strictEqual(isoToEmoji(""), "🏳");
  assert.strictEqual(isoToEmoji("xyz"), "🏳");
  assert.strictEqual(isoToEmoji(null), "🏳");
});
