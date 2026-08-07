/**
 * La base de monedas está duplicada: una copia en admin.html y otra en
 * signalos-extension/parser.js. La extensión es un paquete aparte y no puede
 * importar del admin, así que la duplicación es inevitable.
 *
 * Lo que sí se puede evitar es que se separen en silencio. Ya pasó una vez: se
 * amplió la del admin de 35 a 94 monedas y la extensión se quedó atrás,
 * dejándola sin reconocer 63 divisas al escanear páginas. Este test lo caza.
 *
 * Si falla, sincroniza parser.js copiando el bloque de admin.html.
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
    throw new Error(`No se encuentra CURRENCY_DB en ${file} ` +
                    `(marcadores "${desde}" .. "${hasta}").`);
  }
  return src.slice(a, b).split("\n")
    .map(l => l.trim().replace(/,$/, ""))
    .filter(l => l.startsWith('{code:"'));
}

const enAdmin = () => entradas("admin.html", "const CURRENCY_DB = [", "const CODE_MAP");
const enExt = () => entradas("signalos-extension/parser.js", "const CURRENCY_DB = [", "const CODE_MAP");

const codigos = ls => ls.map(l => l.match(/code:"([A-Z]{3})"/)[1]);

test("la extensión conoce exactamente las mismas monedas que el admin", () => {
  const a = new Set(codigos(enAdmin()));
  const e = new Set(codigos(enExt()));
  const faltanEnExt = [...a].filter(c => !e.has(c));
  const sobranEnExt = [...e].filter(c => !a.has(c));
  assert.deepStrictEqual(faltanEnExt, [],
    "en admin.html pero no en parser.js: " + faltanEnExt.join(", "));
  assert.deepStrictEqual(sobranEnExt, [],
    "en parser.js pero no en admin.html: " + sobranEnExt.join(", "));
});

test("las entradas son idénticas, no solo los códigos", () => {
  // Los alias son lo que hace funcionar la detección: si divergen, la
  // extensión reconocería divisas distintas de las que espera el admin.
  const a = enAdmin(), e = enExt();
  assert.strictEqual(a.length, e.length, "distinto número de entradas");
  const distintas = a.filter((l, i) => l !== e[i])
                     .map(l => l.match(/code:"([A-Z]{3})"/)[1]);
  assert.deepStrictEqual(distintas, [],
    "entradas que difieren entre las dos copias: " + distintas.join(", "));
});
