/**
 * Que una pantalla se entere de que el servidor se ha actualizado.
 *
 * Al instalar una version nueva cambia el archivo en disco, pero la pagina que
 * el televisor lleva horas mostrando SIGUE SIENDO LA DE ANTES: el contenido se
 * refresca por SSE, el codigo no. Hasta ahora la unica forma de que entrara
 * codigo nuevo era la recarga de seguridad de cada 4 horas, o ir a la tienda.
 * Pasó de verdad: se instalo la 1.0.17 y el televisor seguia pintando el
 * tablero con el fallo de la version anterior.
 *
 * La regla tiene que ser tacana: recargar una pantalla de tienda es visible, y
 * hacerlo cuando no toca -por un dato ausente, por un reinicio del servidor con
 * la misma version- seria peor que no hacerlo.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Recarga por version";
const FIN = "// ── fin de la recarga por version";

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra el bloque "${INICIO}" .. "${FIN}" en player.html`);
  }
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

test("si el servidor cambia de version, la pantalla se recarga", () => {
  const c = cargar();
  assert.strictEqual(c.debeRecargarPorVersion("1.0.16", "1.0.17"), true);
});

test("con la misma version no se toca nada", () => {
  // Un reinicio del servidor no cambia el codigo: recargar ahi seria un
  // parpadeo gratis en el escaparate.
  const c = cargar();
  assert.strictEqual(c.debeRecargarPorVersion("1.0.17", "1.0.17"), false);
});

test("sin dato no se recarga", () => {
  // Un servidor viejo no manda la version, y una respuesta a medias tampoco.
  // Ante la duda, no tocar: la pantalla esta pintando bien.
  const c = cargar();
  assert.strictEqual(c.debeRecargarPorVersion("", "1.0.17"), false);
  assert.strictEqual(c.debeRecargarPorVersion("1.0.17", ""), false);
  assert.strictEqual(c.debeRecargarPorVersion(undefined, undefined), false);
  assert.strictEqual(c.debeRecargarPorVersion(null, "1.0.17"), false);
});

test("tambien recarga si la version BAJA", () => {
  // Volver a una version anterior es tan cambio de codigo como avanzar, y pasa
  // de verdad cuando algo sale mal y se reinstala la de antes.
  const c = cargar();
  assert.strictEqual(c.debeRecargarPorVersion("1.0.17", "1.0.16"), true);
});
