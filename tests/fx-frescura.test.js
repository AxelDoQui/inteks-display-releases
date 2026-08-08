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

test("se enseña la fecha de las TASAS, no la de hoy", () => {
  // El fallo de fondo: unas tasas del día 5 salían con la fecha del día 8.
  const c = cargar();
  const hace3dias = new Date(AHORA - 3 * 24 * HORA);
  const esperado = String(hace3dias.getDate()).padStart(2, "0") + "/" +
                   String(hace3dias.getMonth() + 1).padStart(2, "0") + "/" +
                   hace3dias.getFullYear();
  assert.strictEqual(c.fechaTasas({ updated_at: selloHace(72) }, AHORA), esperado);
});

test("sin sello se cae a la fecha de hoy, como antes", () => {
  const c = cargar();
  const hoy = new Date(AHORA);
  const esperado = String(hoy.getDate()).padStart(2, "0") + "/" +
                   String(hoy.getMonth() + 1).padStart(2, "0") + "/" +
                   hoy.getFullYear();
  assert.strictEqual(c.fechaTasas({}, AHORA), esperado);
});

test("la fecha lleva siempre dos dígitos en día y mes", () => {
  const c = cargar();
  const enero = Date.UTC(2026, 0, 3, 10, 0, 0);
  assert.match(c.fechaTasas({ updated_at: enero / 1000 }, AHORA), /^0\d\/01\/2026$/);
});
