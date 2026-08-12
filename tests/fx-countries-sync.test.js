/**
 * La tabla de países del selector de divisas está duplicada: una copia en
 * admin.html (FX_COUNTRIES) y otra en inteks-extension/parser.js. Mismo
 * motivo que currency-db-sync.test.js con CURRENCY_DB: la extensión es un
 * paquete aparte y no puede importar del admin.
 *
 * Si falla, sincroniza parser.js copiando el bloque FX_COUNTRIES de admin.html.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");

function entradas(file, desde, hasta) {
  const src = fs.readFileSync(path.join(ROOT, file), "utf8");
  const a = src.indexOf(desde);
  const b = src.indexOf(hasta, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra FX_COUNTRIES en ${file} ` +
                    `(marcadores "${desde}" .. "${hasta}").`);
  }
  return src.slice(a, b).split("\n")
    .map(l => l.trim().replace(/,$/, ""))
    .filter(l => l.startsWith('{country:"'));
}

const enAdmin = () => entradas("admin.html", "const FX_COUNTRIES = [", "// Identifica una opción del selector");
const enExt = () => entradas("inteks-extension/parser.js", "const FX_COUNTRIES = [", "// El flag de FX_COUNTRIES");

test("las entradas de FX_COUNTRIES son idénticas en admin y en la extensión", () => {
  const a = enAdmin(), e = enExt();
  assert.strictEqual(a.length, e.length, "distinto número de países");
  const distintas = a.filter((l, i) => l !== e[i]);
  assert.deepStrictEqual(distintas, [],
    "entradas que difieren entre las dos copias: " + distintas.join(" | "));
});
