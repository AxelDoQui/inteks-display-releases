/**
 * Tests de la resiliencia del player cuando el servidor no responde.
 *
 * Una pantalla de señalización no puede quedarse en negro porque el servidor
 * se reinicie. Estos tests fijan las dos reglas que lo garantizan: cuándo se
 * considera que hay corte, y que lo guardado en caché se pueda recuperar.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

function loadResiliencia(localStorageStub) {
  const src = fs.readFileSync(PLAYER, "utf8");
  const from = src.indexOf("const OFFLINE_AFTER_MS");
  const to = src.indexOf("function getDayName()");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error("No se encuentra el bloque de resiliencia en player.html " +
                    "(de OFFLINE_AFTER_MS a getDayName). Si se ha movido, actualiza el arnés.");
  }
  const ctx = {
    SCREEN_ID: "Prueba",
    localStorage: localStorageStub || { getItem: () => null, setItem() {}, removeItem() {} },
    playlist: [], screenConfig: null, screenSchedule: null,
    rebuildSlides() {}, showSlide() {}, JSON, Date,
  };
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to) + "\n;__ms = OFFLINE_AFTER_MS;", ctx);
  return ctx;
}

// ── Cuándo se considera que hay corte ──────────────────────────────────────

test("recién contactado el servidor, no hay corte", () => {
  const c = loadResiliencia();
  assert.strictEqual(c.isOffline(1000, 1000), false);
});

test("un corte breve no cuenta: los reinicios rápidos no deben notarse", () => {
  const c = loadResiliencia();
  assert.strictEqual(c.isOffline(0, 30 * 1000), false, "30 s no es un corte");
  assert.strictEqual(c.isOffline(0, 119 * 1000), false, "justo antes del umbral tampoco");
});

test("pasados dos minutos sin contacto sí se considera corte", () => {
  const c = loadResiliencia();
  assert.strictEqual(c.isOffline(0, 121 * 1000), true);
  assert.strictEqual(c.isOffline(0, 3600 * 1000), true);
});

test("el umbral es de dos minutos", () => {
  const c = loadResiliencia();
  assert.strictEqual(c.__ms, 120000);
});

// ── Caché local: sobrevivir a un arranque sin servidor ─────────────────────

function stubStorage(inicial) {
  const store = { ...(inicial || {}) };
  return {
    _store: store,
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
  };
}

test("guardar y recuperar deja la playlist tal cual", () => {
  const ls = stubStorage();
  const c = loadResiliencia(ls);
  c.playlist = [{ type: "fx", title: "WU", rows: [1, 2] }];
  c.screenConfig = { rotation: 90, schedule: { lunes: { enabled: true } } };
  c.saveCache();

  const c2 = loadResiliencia(ls);              // simula recargar la página
  assert.strictEqual(c2.restoreFromCache(), true);
  assert.strictEqual(c2.playlist.length, 1);
  assert.strictEqual(c2.playlist[0].title, "WU");
  assert.strictEqual(c2.screenConfig.rotation, 90, "la configuración también se recupera");
  assert.ok(c2.screenSchedule, "y el horario, o la pantalla se encendería fuera de hora");
});

test("sin nada guardado, recuperar no hace nada", () => {
  const c = loadResiliencia(stubStorage());
  assert.strictEqual(c.restoreFromCache(), false);
});

test("una caché corrupta no rompe el arranque", () => {
  const c = loadResiliencia(stubStorage({ "signalos_cache_Prueba": "{esto no es json" }));
  assert.strictEqual(c.restoreFromCache(), false);
});

test("no se recupera una playlist vacía: no borraría lo que ya se ve", () => {
  const ls = stubStorage();
  const c = loadResiliencia(ls);
  c.playlist = [];
  c.saveCache();
  assert.strictEqual(loadResiliencia(ls).restoreFromCache(), false);
});

test("cada pantalla tiene su propia caché", () => {
  const ls = stubStorage();
  const c = loadResiliencia(ls);
  c.playlist = [{ type: "text" }];
  c.saveCache();
  assert.ok(Object.keys(ls._store).some(k => k.includes("Prueba")),
    "la clave debe llevar el id de pantalla: " + Object.keys(ls._store));
});
