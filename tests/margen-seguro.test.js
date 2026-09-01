/**
 * El margen de seguridad de los bordes.
 *
 * Algunos televisores recortan un 3-5% de cada borde (sobrebarrido) y se comen
 * lo que haya pegado al filo. Se puede pedir que el contenido se separe, pero
 * va POR PANTALLA y por defecto a CERO: un margen puesto donde no hace falta le
 * quita sitio a un tablero de divisas que ya va justo, asi que solo lo paga
 * quien lo pide.
 *
 * El recorte a 5 no es cosmetico: mas que eso no es un margen, es un televisor
 * mal configurado, y dejarlo subir mas solo escondería el sintoma.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Margen de seguridad";
const FIN = "// ── fin del margen de seguridad";

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  assert.ok(a >= 0 && b > a, "no se encuentra el bloque del margen en player.html");
  const ctx = { document: { getElementById: () => null } };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

test("sin ajuste no hay margen", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss(null), "0px");
  assert.strictEqual(margenSeguroCss(undefined), "0px");
  assert.strictEqual(margenSeguroCss({}), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: 0 }), "0px");
});

test("un ajuste normal se convierte en porcentaje", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss({ safe_margin: 3 }), "3%");
  assert.strictEqual(margenSeguroCss({ safe_margin: 5 }), "5%");
});

test("se recorta a 5 y nunca es negativo", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss({ safe_margin: 40 }), "5%");
  assert.strictEqual(margenSeguroCss({ safe_margin: -3 }), "0px");
});

test("la basura vale cero, no deja una pantalla rota", () => {
  const { margenSeguroCss } = cargar();
  // El panel no es el unico que escribe content.json -esta la extension, esta
  // una copia restaurada de otra tienda-, asi que el player no puede fiarse de
  // que le llegue un numero sano.
  assert.strictEqual(margenSeguroCss({ safe_margin: "" }), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: "tres" }), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: null }), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: {} }), "0px");
});

test("un texto con un numero dentro se entiende igual", () => {
  const { margenSeguroCss } = cargar();
  // Un <input type=number> devuelve cadena, y una copia vieja de content.json
  // puede traerlo asi.
  assert.strictEqual(margenSeguroCss({ safe_margin: "3" }), "3%");
});

test("un decimal se queda en el entero de abajo", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss({ safe_margin: 2.7 }), "2%");
});
