/**
 * Cache de imagenes y videos dentro del propio televisor.
 *
 * El texto, las divisas, el clima y el ticker ya aguantan sin servidor, pero
 * las imagenes y los videos dependian de la cache del navegador: si el PC del
 * servidor esta apagado y el TV arranca en frio, el escaparate se queda vacio.
 *
 * La solucion completa (service worker) exige HTTPS, y montar un tunel en cada
 * tienda es una dependencia externa que no compensa. IndexedDB funciona en la
 * red local tal cual, sobre http, sin depender de nadie.
 *
 * Aqui se prueba el nucleo, que es puro: que se cachea, que URL se usa y que se
 * suelta cuando deja de hacer falta. El pegamento con IndexedDB no se puede
 * probar en Node y va marcado como tal en player.html.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Medios guardados en el televisor";
const FIN = "// ── fin del nucleo de medios";

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el nucleo de medios en player.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { Object };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const img = s => ({ type: "image", src: s });
const vid = s => ({ type: "video", src: s });

// ── Que merece la pena guardar ─────────────────────────────────────────────

test("las imagenes y los videos subidos se guardan", () => {
  const c = cargar();
  assert.strictEqual(c.esMedioCacheable(img("/uploads/cartel.png")), true);
  assert.strictEqual(c.esMedioCacheable(vid("/uploads/promo.mp4")), true);
});

test("lo que no sirve nuestro servidor no se guarda", () => {
  // Una imagen remota puede ser enorme, cambiar sola o no permitir la descarga
  // por CORS. Guardarla seria llenar el televisor sin ganar nada.
  const c = cargar();
  assert.strictEqual(c.esMedioCacheable(img("https://ejemplo.com/foto.jpg")), false);
  assert.strictEqual(c.esMedioCacheable(img("/assets/icon.svg")), false);
});

test("los modulos que ya funcionan sin servidor no se tocan", () => {
  const c = cargar();
  assert.strictEqual(c.esMedioCacheable({ type: "fx", rows: [] }), false);
  assert.strictEqual(c.esMedioCacheable({ type: "text", title: "hola" }), false);
  assert.strictEqual(c.esMedioCacheable({ type: "url", src: "/uploads/x" }), false,
    "un iframe no es un archivo que se pueda guardar");
});

test("un item raro no rompe nada", () => {
  const c = cargar();
  assert.strictEqual(c.esMedioCacheable(null), false);
  assert.strictEqual(c.esMedioCacheable({}), false);
  assert.strictEqual(c.esMedioCacheable(img("")), false);
});

// ── Que hay que descargar para una playlist ────────────────────────────────

test("se listan los medios de la playlist, sin repetir", () => {
  const c = cargar();
  const pl = [img("/uploads/a.png"), { type: "fx" }, vid("/uploads/b.mp4"),
              img("/uploads/a.png")];
  assert.deepStrictEqual(JSON.parse(JSON.stringify(c.mediosDePlaylist(pl))),
    ["/uploads/a.png", "/uploads/b.mp4"]);
});

test("una playlist vacia o sin medios no pide nada", () => {
  const c = cargar();
  assert.deepStrictEqual(JSON.parse(JSON.stringify(c.mediosDePlaylist([]))), []);
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(c.mediosDePlaylist([{ type: "fx" }]))), []);
});

// ── Que URL se usa al pintar ───────────────────────────────────────────────

test("si esta guardado se usa la copia local", () => {
  const c = cargar();
  const mapa = { "/uploads/a.png": "blob:xyz" };
  assert.strictEqual(c.urlDeMedio("/uploads/a.png", mapa), "blob:xyz");
});

test("si no esta guardado se usa la del servidor", () => {
  // Nunca se deja de pintar por no tener copia: la red es el respaldo.
  const c = cargar();
  assert.strictEqual(c.urlDeMedio("/uploads/b.png", {}), "/uploads/b.png");
  assert.strictEqual(c.urlDeMedio("/uploads/b.png", null), "/uploads/b.png");
});

// ── Soltar lo que ya no hace falta ─────────────────────────────────────────

test("se sueltan los medios que ya no estan en la playlist", () => {
  // Un player de señalizacion esta semanas encendido. Sin soltar las URL de
  // objeto, cada cambio de playlist deja memoria retenida para siempre.
  const c = cargar();
  const mapa = { "/uploads/a.png": "blob:1", "/uploads/vieja.png": "blob:2" };
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(c.sobrantes(mapa, ["/uploads/a.png"]))),
    ["/uploads/vieja.png"]);
});

test("si todo sigue en uso no se suelta nada", () => {
  const c = cargar();
  const mapa = { "/uploads/a.png": "blob:1" };
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(c.sobrantes(mapa, ["/uploads/a.png"]))), []);
});

test("con la playlist vacia se suelta todo", () => {
  const c = cargar();
  const mapa = { "/uploads/a.png": "blob:1", "/uploads/b.png": "blob:2" };
  assert.strictEqual(c.sobrantes(mapa, []).length, 2);
});
