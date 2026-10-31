/**
 * Duplicar una pantalla.
 *
 * Montar la segunda caja de una tienda significaba rehacer a mano la
 * playlist, el horario, la rotacion y la transicion. La copia de seguridad
 * clona una tienda entera; esto es el grano fino.
 *
 * Lo delicado es que NO se copia: lo que ata una pantalla a otra. Clonar el
 * emparejamiento de un videowall dejaria dos pantallas diciendo que son la
 * mitad izquierda de la misma pared.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Duplicar una pantalla";
const FIN = "// ── fin del clonado";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el bloque de clonado en admin.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { JSON, Object, Array };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const completa = () => ({
  mode: "independent",
  rotation: 90,
  transition: "slide",
  transition_ms: 600,
  standby_image: "/uploads/cerrado.png",
  always_on: false,
  schedule: { lunes: { enabled: true, start: "09:00", end: "21:00" },
              holidays: [{ date: "2026-12-25", enabled: false }] },
  playlist: [{ id: "it_1", type: "image", src: "/uploads/a.png", duration: 8 },
             { type: "package", pkg_id: "pkg_1" }],
});

test("se copia la playlist entera, paquetes incluidos", () => {
  const c = cargar().clonarConfigPantalla(completa());
  assert.strictEqual(c.playlist.length, 2);
  assert.strictEqual(c.playlist[0].id, "it_1");
  assert.strictEqual(c.playlist[1].pkg_id, "pkg_1",
    "la referencia al paquete se mantiene: sigue siendo un grupo vivo");
});

test("se copian horario, rotacion y transicion", () => {
  const c = cargar().clonarConfigPantalla(completa());
  assert.strictEqual(c.rotation, 90);
  assert.strictEqual(c.transition, "slide");
  assert.strictEqual(c.transition_ms, 600);
  assert.strictEqual(c.schedule.lunes.start, "09:00");
  assert.strictEqual(c.schedule.holidays[0].date, "2026-12-25",
    "los festivos tambien viajan");
  assert.strictEqual(c.standby_image, "/uploads/cerrado.png");
});

test("la copia es profunda: tocar una no cambia la otra", () => {
  // Sin copia profunda, editar la playlist de la nueva editaria la original.
  // Es el fallo mas facil de cometer aqui y el mas dificil de ver luego.
  const original = completa();
  const c = cargar().clonarConfigPantalla(original);
  c.playlist[0].duration = 99;
  c.schedule.lunes.start = "07:00";
  assert.strictEqual(original.playlist[0].duration, 8);
  assert.strictEqual(original.schedule.lunes.start, "09:00");
});

test("un videowall se clona como pantalla independiente", () => {
  // Copiar mode:"wall" con su partner dejaria dos pantallas diciendo que son
  // la mitad izquierda de la misma pared.
  const c = cargar().clonarConfigPantalla({
    mode: "wall", wall_pos: "left", partner: "Caja-2", playlist: [],
  });
  assert.strictEqual(c.mode, "independent");
  assert.strictEqual(c.partner, undefined);
  assert.strictEqual(c.wall_pos, undefined);
});

test("una pantalla vacia se clona sin reventar", () => {
  const c = cargar().clonarConfigPantalla({});
  assert.deepStrictEqual(JSON.parse(JSON.stringify(c.playlist)), []);
  assert.strictEqual(c.mode, "independent");
});

test("no se arrastra el estado de conexion", () => {
  // connected y last_seen describen a un televisor concreto, no a una
  // configuracion. Copiarlos haria aparecer la nueva como si ya estuviera en
  // linea sin que nadie la haya enchufado.
  const c = cargar().clonarConfigPantalla({ connected: true, last_seen: 123, playlist: [] });
  assert.strictEqual(c.connected, undefined);
  assert.strictEqual(c.last_seen, undefined);
});

test("el nombre para mostrar no se copia a la pantalla nueva", () => {
  const c = cargar().clonarConfigPantalla({ label: "Entrada", playlist: [] });
  assert.strictEqual(c.label, undefined);
});
