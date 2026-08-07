/**
 * Tests de la lógica de horario de pantalla.
 *
 * player.html es un HTML monolítico con el JS inline, así que no hay nada que
 * importar. En vez de copiar las funciones aquí (una copia se desincroniza al
 * primer cambio y dejaría de probar nada), este arnés EXTRAE el bloque real de
 * player.html y lo ejecuta en un contexto vm con un Date falso inyectado.
 * Si alguien edita isScreenActive() en player.html, estos tests lo ven.
 *
 * Ejecutar:  node --test tests/
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

// ── Extrae el bloque de funciones de horario tal cual está en player.html
function extractScheduleSource() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const from = src.indexOf("function getDayName()");
  const to = src.indexOf("function showStandby()");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error(
      "No se encuentran getDayName()/showStandby() en player.html. " +
      "Si se han renombrado, actualiza los marcadores de este arnés."
    );
  }
  return src.slice(from, to);
}

/**
 * Evalúa isScreenActive() como si fuera un instante concreto.
 * @param {{day:number, hour:number, minute:number}} at  day: 0=domingo … 6=sábado
 */
function isActiveAt(at, { schedule = null, config = null, preview = false } = {}) {
  class FakeDate {
    getDay() { return at.day; }
    getHours() { return at.hour; }
    getMinutes() { return at.minute; }
  }
  // PREVIEW es una dependencia real de isScreenActive(): en modo vista previa
  // la pantalla se muestra siempre, sin mirar el horario.
  const ctx = {
    Date: FakeDate, screenSchedule: schedule, screenConfig: config, PREVIEW: preview,
  };
  vm.createContext(ctx);
  vm.runInContext(extractScheduleSource() + "\n;__r = isScreenActive();", ctx);
  return ctx.__r;
}

const LUNES = 1;
const diurno = { lunes: { enabled: true, start: "08:00", end: "20:00" } };
const nocturno = { lunes: { enabled: true, start: "22:00", end: "02:00" } };

// ── Horario diurno: comportamiento que YA funciona y no debe romperse
test("horario diurno: activa dentro del intervalo", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 12, minute: 0 }, { schedule: diurno }), true);
});

test("horario diurno: inactiva antes de la hora de inicio", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 7, minute: 0 }, { schedule: diurno }), false);
});

test("horario diurno: inactiva después de la hora de fin", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 21, minute: 0 }, { schedule: diurno }), false);
});

// ── Horario nocturno (cruza medianoche): el bug
test("horario nocturno: activa antes de medianoche", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 23, minute: 0 }, { schedule: nocturno }), true);
});

test("horario nocturno: activa después de medianoche", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 1, minute: 0 }, { schedule: nocturno }), true);
});

test("horario nocturno: inactiva a mediodía", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 12, minute: 0 }, { schedule: nocturno }), false);
});

test("horario nocturno: activa justo en la hora de inicio", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 22, minute: 0 }, { schedule: nocturno }), true);
});

test("horario nocturno: activa justo en la hora de fin", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 2, minute: 0 }, { schedule: nocturno }), true);
});

test("horario nocturno: inactiva un minuto después del fin", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 2, minute: 1 }, { schedule: nocturno }), false);
});

// ── Reglas que no dependen del intervalo
test("always_on ignora el horario y mantiene la pantalla activa", () => {
  const r = isActiveAt({ day: LUNES, hour: 3, minute: 0 }, { schedule: diurno, config: { always_on: true } });
  assert.strictEqual(r, true);
});

test("día deshabilitado deja la pantalla inactiva", () => {
  const off = { lunes: { enabled: false, start: "08:00", end: "20:00" } };
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 12, minute: 0 }, { schedule: off }), false);
});

test("sin horario configurado la pantalla está siempre activa", () => {
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 4, minute: 0 }, { schedule: null }), true);
});

test("la vista previa del admin ignora el horario y siempre muestra contenido", () => {
  // Mismo instante y horario que dejan la pantalla apagada en el test de arriba.
  const fuera = { day: LUNES, hour: 3, minute: 0 };
  assert.strictEqual(isActiveAt(fuera, { schedule: diurno }), false);
  assert.strictEqual(isActiveAt(fuera, { schedule: diurno, preview: true }), true);
});
