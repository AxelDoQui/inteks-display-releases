// El service worker no debe servir el panel de administración desde la caché.
//
// Caso real (2026-10-28): tras actualizar, el panel seguía mostrando la pantalla
// vieja (sin el botón «Actualizar ahora») porque sw.js la guardaba y la servía
// primero. El player SÍ necesita su caché para funcionar sin red.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function cargarSW() {
  const manejadores = {};
  const llamadasAlmacen = [];
  const sandbox = {
    self: {
      location: { origin: "http://localhost" },
      addEventListener: (tipo, fn) => { manejadores[tipo] = fn; },
      skipWaiting: () => {},
      clients: { claim: () => {} },
    },
    caches: {
      keys: async () => [],
      delete: async () => true,
      open: async (n) => { llamadasAlmacen.push(n); return { match: async () => undefined, put: () => {} }; },
    },
    fetch: async () => ({ status: 200, clone() { return this; } }),
    URL,
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "sw.js"), "utf8"), sandbox);
  return { manejadores, llamadasAlmacen, sandbox };
}

function interceptado(manejadores, ruta) {
  let respondido = false;
  manejadores.fetch({
    request: { url: "http://localhost" + ruta, method: "GET" },
    respondWith: () => { respondido = true; },
  });
  return respondido;
}

test("el panel y el login nunca pasan por la caché", () => {
  const { manejadores } = cargarSW();
  for (const ruta of ["/admin.html", "/admin", "/login.html", "/login"]) {
    assert.strictEqual(interceptado(manejadores, ruta), false, ruta + " no debe cachearse");
  }
});

test("el player sigue cacheado para funcionar sin red", () => {
  const { manejadores } = cargarSW();
  for (const ruta of ["/player.html", "/uploads/0001_logo.png", "/vendor/qrcode.min.js"]) {
    assert.strictEqual(interceptado(manejadores, ruta), true, ruta + " sí debe cachearse");
  }
});

test("la API y los vídeos tampoco se cachean", () => {
  const { manejadores } = cargarSW();
  assert.strictEqual(interceptado(manejadores, "/api/content"), false);
  assert.strictEqual(interceptado(manejadores, "/uploads/0002_clip.mp4"), false);
});

test("la caché cambió de nombre: borra el admin.html viejo guardado", () => {
  const { sandbox } = cargarSW();
  const fuente = fs.readFileSync(path.join(__dirname, "..", "sw.js"), "utf8");
  assert.ok(!/CACHE\s*=\s*'signalos-v1'/.test(fuente), "debe usar un nombre distinto de signalos-v1");
  assert.ok(sandbox);
});
