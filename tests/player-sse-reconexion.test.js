/**
 * Reconexión de la conexión SSE del player tras un corte.
 *
 * Bug real: cada corte de conexión creaba un EventSource nuevo sin cerrar el
 * anterior. El navegador lo sigue reintentando por su cuenta (es el
 * comportamiento por defecto de EventSource si no se llama a close()), así
 * que con las horas se acumulan conexiones zombis -algo mucho más frecuente
 * en el WiFi de un televisor que en un PC- hasta agotar la memoria del
 * navegador del TV y cerrarlo.
 *
 * Se carga connectSSE() de player.html en un vm con un EventSource de
 * mentira que registra cuántas instancias se crean y si se cierran.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const from = src.indexOf("let reloadTimer=null;");
  const to = src.indexOf("// Banderas como im", from);
  if (from === -1 || to === -1 || to <= from) {
    throw new Error("No se encuentra connectSSE() en player.html " +
                    "(de 'let reloadTimer=null;' a 'Banderas como imágenes'). Si se ha movido, actualiza el arnés.");
  }

  const instancias = [];
  class FakeEventSource {
    constructor(url) { this.url = url; this.closed = false; instancias.push(this); }
    close() { this.closed = true; }
  }
  const timers = [];
  const ctx = {
    EventSource: FakeEventSource,
    encodeURIComponent,
    SCREEN_ID: "TV1",
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    clearTimeout() {},
    location: { href: "" },
    olvidarIdentidad() {},
    loadPlaylist() {},
  };
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to), ctx);
  return { ctx, instancias, timers };
}

test("al fallar la conexión SSE, se cierra la vieja antes de programar una nueva", () => {
  const { ctx, instancias } = cargar();
  ctx.connectSSE();
  assert.strictEqual(instancias.length, 1);
  instancias[0].onerror();
  assert.strictEqual(instancias[0].closed, true,
    "la conexión vieja debe cerrarse; si no, el navegador la sigue reintentando sola");
});

test("el reintento crea una única conexión nueva, no otra en paralelo", () => {
  const { ctx, instancias, timers } = cargar();
  ctx.connectSSE();
  instancias[0].onerror();
  assert.strictEqual(instancias.length, 1, "todavía no se crea la nueva: espera al setTimeout");
  timers[0]();   // dispara el reintento programado
  assert.strictEqual(instancias.length, 2, "se crea una conexión nueva tras el reintento");
  assert.strictEqual(instancias[0].closed, true, "la primera sigue cerrada");
  assert.strictEqual(instancias[1].closed, false, "la nueva empieza abierta");
});

test("varios cortes seguidos no acumulan conexiones sin cerrar", () => {
  const { ctx, instancias, timers } = cargar();
  ctx.connectSSE();
  for (let i = 0; i < 5; i++) {
    instancias[instancias.length - 1].onerror();
    timers[timers.length - 1]();
  }
  assert.strictEqual(instancias.length, 6, "una conexión inicial + 5 reintentos");
  const abiertas = instancias.filter(e => !e.closed);
  assert.strictEqual(abiertas.length, 1, "solo la última debe seguir abierta; el resto, cerradas");
});
