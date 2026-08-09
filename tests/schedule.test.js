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
    // Los festivos son fechas concretas, así que el reloj falso también tiene
    // que saber en qué día del calendario estamos. Por defecto, un lunes
    // cualquiera que no es festivo en ninguna parte.
    getFullYear() { return at.year === undefined ? 2026 : at.year; }
    getMonth() { return at.month === undefined ? 5 : at.month; }   // 0 = enero
    getDate() { return at.date === undefined ? 15 : at.date; }
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

// ── Festivos ───────────────────────────────────────────────────────────────
// El horario semanal no sabe de fiestas: el 25 de diciembre cae en un día
// laborable cualquiera y la tienda está cerrada igual. Un festivo es una fecha
// concreta que manda sobre la regla del día de la semana.

// Un lunes 25 de diciembre de 2026, a mediodía: dentro del horario diurno.
const NAVIDAD = { day: LUNES, hour: 12, minute: 0, year: 2026, month: 11, date: 25 };

test("un festivo cerrado apaga la pantalla aunque el día de la semana esté abierto", () => {
  const s = { ...diurno, holidays: [{ date: "2026-12-25", enabled: false }] };
  assert.strictEqual(isActiveAt(NAVIDAD, { schedule: diurno }), true, "control: sin festivo, encendida");
  assert.strictEqual(isActiveAt(NAVIDAD, { schedule: s }), false);
});

test("un festivo solo afecta a SU fecha", () => {
  const s = { ...diurno, holidays: [{ date: "2026-12-25", enabled: false }] };
  const otroDia = { day: LUNES, hour: 12, minute: 0, year: 2026, month: 11, date: 24 };
  assert.strictEqual(isActiveAt(otroDia, { schedule: s }), true);
});

test("un festivo con horario reducido manda sobre el del día de la semana", () => {
  // Nochebuena: se abre, pero solo por la mañana.
  const s = { ...diurno, holidays: [{ date: "2026-12-24", enabled: true, start: "09:00", end: "14:00" }] };
  const manana = { day: LUNES, hour: 11, minute: 0, year: 2026, month: 11, date: 24 };
  const tarde  = { day: LUNES, hour: 17, minute: 0, year: 2026, month: 11, date: 24 };
  assert.strictEqual(isActiveAt(manana, { schedule: s }), true);
  assert.strictEqual(isActiveAt(tarde, { schedule: s }), false,
    "a las 17:00 el horario normal abriria, pero el festivo manda");
});

test("un festivo abierto sin horas vale para todo el día", () => {
  const s = { ...diurno, holidays: [{ date: "2026-12-25", enabled: true }] };
  const madrugada = { day: LUNES, hour: 3, minute: 0, year: 2026, month: 11, date: 25 };
  assert.strictEqual(isActiveAt(madrugada, { schedule: s }), true);
});

test("un festivo puede abrir un día que normalmente está cerrado", () => {
  // Domingo de rebajas: el domingo no está ni configurado, y aun así se abre.
  const s = { ...diurno, holidays: [{ date: "2026-12-27", enabled: true, start: "10:00", end: "14:00" }] };
  const domingo = { day: 0, hour: 11, minute: 0, year: 2026, month: 11, date: 27 };
  assert.strictEqual(isActiveAt(domingo, { schedule: diurno }), false, "control: domingo cerrado");
  assert.strictEqual(isActiveAt(domingo, { schedule: s }), true);
});

test("con SOLO festivos configurados, el resto de días sigue encendido", () => {
  // Si al configurar unos festivos se apagaran todas las pantallas el resto del
  // año, el modo festivos sería una trampa.
  const s = { holidays: [{ date: "2026-12-25", enabled: false }] };
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 4, minute: 0, date: 15 }, { schedule: s }), true);
  assert.strictEqual(isActiveAt(NAVIDAD, { schedule: s }), false, "y el festivo sigue apagando");
});

test("always_on manda incluso sobre un festivo cerrado", () => {
  const s = { ...diurno, holidays: [{ date: "2026-12-25", enabled: false }] };
  assert.strictEqual(isActiveAt(NAVIDAD, { schedule: s, config: { always_on: true } }), true);
});

test("una lista de festivos vacía o con basura no rompe nada", () => {
  assert.strictEqual(isActiveAt(NAVIDAD, { schedule: { ...diurno, holidays: [] } }), true);
  assert.strictEqual(isActiveAt(NAVIDAD, { schedule: { ...diurno, holidays: [null, {}] } }), true);
});

test("un día de la semana abierto sin horas vale para todo el día", () => {
  // Antes, enabled:true sin start/end dejaba la pantalla APAGADA las 24 horas,
  // porque comparaba contra undefined. Silencioso y desconcertante.
  const s = { lunes: { enabled: true } };
  assert.strictEqual(isActiveAt({ day: LUNES, hour: 3, minute: 0 }, { schedule: s }), true);
});

// ── Corpus compartido con Python ───────────────────────────────────────────
// La misma lógica vive en player.html (decide si pintar) y en server.py
// (decide si avisar de una pantalla caída). Duplicarla es inevitable —son dos
// lenguajes— pero que se separen no. Estos casos los ejecutan las dos suites:
// tests/test_horario_python.py lee este mismo archivo.
const CORPUS = require("./casos-horario.json");

for (const caso of CORPUS.casos) {
  test(`[corpus] ${caso.nombre}`, () => {
    const at = {
      day: caso.cuando.dia, hour: caso.cuando.hora, minute: caso.cuando.minuto,
      year: caso.cuando.anio, month: caso.cuando.mes - 1, date: caso.cuando.dia_mes,
    };
    assert.strictEqual(isActiveAt(at, { schedule: caso.horario }), caso.activa);
  });
}
