/**
 * Frescura de las tasas.
 *
 * El tablero mostraba SIEMPRE la fecha de hoy, sacada del reloj del navegador.
 * Unas tasas de hace tres días se veían con la fecha de hoy al lado: el propio
 * tablero certificaba que estaban recién puestas. Si un cliente reclama, esa
 * fecha juega en contra de la casa de cambio.
 *
 * Ahora se muestra la fecha de las TASAS (el sello `updated_at`, que ya escribía
 * el servidor y no leía nadie), y si llevan demasiado tiempo sin tocarse aparece
 * un punto discreto para que el personal lo note al pasar.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Frescura de las tasas";
const FIN = "// ── fin de la frescura";

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el bloque de frescura en player.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { Date, parseFloat, isNaN, String };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b) + "\n;__def = STALE_HORAS_POR_DEFECTO;", ctx);
  return ctx;
}

const HORA = 3600 * 1000;
const AHORA = Date.UTC(2026, 7, 8, 12, 0, 0);     // 8 de agosto de 2026, 12:00
const selloHace = h => (AHORA - h * HORA) / 1000; // updated_at va en segundos

// ── Cuándo se consideran caducadas ─────────────────────────────────────────

test("el umbral por defecto es un día", () => {
  assert.strictEqual(cargar().__def, 24);
});

test("recién actualizadas no están caducadas", () => {
  const c = cargar();
  assert.strictEqual(c.tasasCaducadas({ updated_at: selloHace(0) }, AHORA), false);
  assert.strictEqual(c.tasasCaducadas({ updated_at: selloHace(23) }, AHORA), false);
});

test("pasado el día sí lo están", () => {
  const c = cargar();
  assert.strictEqual(c.tasasCaducadas({ updated_at: selloHace(25) }, AHORA), true);
  assert.strictEqual(c.tasasCaducadas({ updated_at: selloHace(72) }, AHORA), true);
});

test("el umbral se puede ajustar por módulo", () => {
  // Un tablero de remesas que se revisa dos veces al día quiere avisar antes.
  const c = cargar();
  const mod = h => ({ updated_at: selloHace(h), stale_hours: 6 });
  assert.strictEqual(c.tasasCaducadas(mod(5), AHORA), false);
  assert.strictEqual(c.tasasCaducadas(mod(7), AHORA), true);
});

test("con umbral 0 el aviso queda desactivado", () => {
  const c = cargar();
  assert.strictEqual(
    c.tasasCaducadas({ updated_at: selloHace(500), stale_hours: 0 }, AHORA), false);
});

test("sin sello no se acusa a nadie", () => {
  // Los módulos creados antes de esto no tienen updated_at. Marcarlos todos de
  // golpe seria ruido puro: el sello aparece en cuanto se guarden una vez.
  const c = cargar();
  assert.strictEqual(c.tasasCaducadas({}, AHORA), false);
  assert.strictEqual(c.tasasCaducadas({ updated_at: 0 }, AHORA), false);
  assert.strictEqual(c.tasasCaducadas({ updated_at: "" }, AHORA), false);
});

test("un sello que llega como texto también vale", () => {
  // JSON round-trip: el sello puede venir como cadena y no debe romper nada.
  const c = cargar();
  assert.strictEqual(
    c.tasasCaducadas({ updated_at: String(selloHace(30)) }, AHORA), true);
});

test("un módulo indefinido no rompe el render", () => {
  assert.strictEqual(cargar().tasasCaducadas(undefined, AHORA), false);
});

// ── Qué fecha se enseña en el tablero ──────────────────────────────────────

// Formato esperado: "08/08/2026 14:30". La hora la pidió él: un tablero de
// divisas se actualiza varias veces al día, y saber que las tasas son de esta
// mañana o de hace diez minutos cambia lo que el empleado le dice al cliente.
function selloLegible(ms) {
  const d = new Date(ms);
  return String(d.getDate()).padStart(2, "0") + "/" +
         String(d.getMonth() + 1).padStart(2, "0") + "/" +
         d.getFullYear() + " " +
         String(d.getHours()).padStart(2, "0") + ":" +
         String(d.getMinutes()).padStart(2, "0");
}

test("se enseña la fecha de las TASAS, no la de hoy", () => {
  // El fallo de fondo: unas tasas del día 5 salían con la fecha del día 8.
  const c = cargar();
  assert.strictEqual(c.fechaTasas({ updated_at: selloHace(72) }, AHORA),
                     selloLegible(AHORA - 3 * 24 * HORA));
});

test("sin sello se cae a la fecha de hoy, como antes", () => {
  const c = cargar();
  assert.strictEqual(c.fechaTasas({}, AHORA), selloLegible(AHORA));
});

test("se enseña también la hora a la que se actualizaron", () => {
  // Con solo la fecha, unas tasas puestas a las 9:00 y otras a las 19:00 se
  // ven idénticas en pantalla.
  const c = cargar();
  const manana = new Date(2026, 7, 8, 9, 5, 0).getTime();
  const tarde = new Date(2026, 7, 8, 19, 45, 0).getTime();
  assert.strictEqual(c.fechaTasas({ updated_at: manana / 1000 }, AHORA), "08/08/2026 09:05");
  assert.strictEqual(c.fechaTasas({ updated_at: tarde / 1000 }, AHORA), "08/08/2026 19:45");
});

test("día, mes, hora y minuto llevan siempre dos dígitos", () => {
  // "3/1/2026 9:5" se lee mal de lejos y descoloca la cabecera al cambiar de
  // ancho según la hora.
  const c = cargar();
  const enero = new Date(2026, 0, 3, 9, 5, 0).getTime();
  assert.match(c.fechaTasas({ updated_at: enero / 1000 }, AHORA),
               /^03\/01\/2026 09:05$/);
});
