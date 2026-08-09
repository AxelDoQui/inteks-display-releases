/**
 * Transiciones entre diapositivas.
 *
 * Ya habia una -un fundido de 1 s, en el CSS de .slide- pero no se podia
 * elegir ni ajustar. Esto anade tipo y duracion por pantalla: un escaparate y
 * una pantalla de caja piden ritmos distintos.
 *
 * Solo se animan opacity y transform. Son las dos unicas propiedades que la
 * GPU compone sin repintar; cualquier otra cosa da tirones en un Android TV
 * barato, que es el hardware donde esto acaba corriendo. Un fundido a saltos
 * queda peor que no tener transicion.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Transiciones entre diapositivas";
const FIN = "// ── fin de las transiciones";

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el bloque de transiciones en player.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { parseFloat, isNaN, Math, String };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b) + "\n;__max = TRANS_MS_MAX;", ctx);
  return ctx;
}

// ── Que tipo de transicion ─────────────────────────────────────────────────

test("sin configurar, se mantiene el fundido de siempre", () => {
  // Importa: las pantallas que ya funcionan no deben cambiar de aspecto solas.
  const c = cargar();
  assert.strictEqual(c.claseTransicion(null), "tr-fade");
  assert.strictEqual(c.claseTransicion({}), "tr-fade");
});

test("se reconocen los cuatro tipos", () => {
  const c = cargar();
  assert.strictEqual(c.claseTransicion({ transition: "fade" }), "tr-fade");
  assert.strictEqual(c.claseTransicion({ transition: "slide" }), "tr-slide");
  assert.strictEqual(c.claseTransicion({ transition: "zoom" }), "tr-zoom");
  assert.strictEqual(c.claseTransicion({ transition: "none" }), "tr-none");
});

test("un tipo desconocido cae al fundido en vez de dejar la pantalla rara", () => {
  // Puede llegar de una copia de seguridad de otra version, o de un JSON tocado
  // a mano. Nunca puede acabar en una pantalla que no transiciona ni se ve.
  const c = cargar();
  assert.strictEqual(c.claseTransicion({ transition: "explosion" }), "tr-fade");
  assert.strictEqual(c.claseTransicion({ transition: 42 }), "tr-fade");
});

// ── Cuanto dura ────────────────────────────────────────────────────────────

test("sin configurar dura un segundo, como hasta ahora", () => {
  const c = cargar();
  assert.strictEqual(c.duracionTransicion(null), 1000);
  assert.strictEqual(c.duracionTransicion({}), 1000);
});

test("la duracion se puede ajustar", () => {
  const c = cargar();
  assert.strictEqual(c.duracionTransicion({ transition_ms: 400 }), 400);
});

test("el corte seco no dura nada, se configure lo que se configure", () => {
  const c = cargar();
  assert.strictEqual(
    c.duracionTransicion({ transition: "none", transition_ms: 900 }), 0);
});

test("una duracion absurda se recorta", () => {
  // Una transicion de 30 s con diapositivas de 8 s dejaria la pantalla en un
  // fundido permanente, sin llegar a mostrar nada del todo.
  const c = cargar();
  assert.strictEqual(c.duracionTransicion({ transition_ms: 99999 }), c.__max);
  assert.strictEqual(c.duracionTransicion({ transition_ms: -5 }), 0);
});

test("una duracion que no es un numero no rompe el pase", () => {
  const c = cargar();
  assert.strictEqual(c.duracionTransicion({ transition_ms: "hola" }), 1000);
  assert.strictEqual(c.duracionTransicion({ transition_ms: null }), 1000);
});

test("una duracion en texto si vale: el JSON puede traerla asi", () => {
  const c = cargar();
  assert.strictEqual(c.duracionTransicion({ transition_ms: "600" }), 600);
});

test("el tope esta por debajo de la diapositiva mas corta razonable", () => {
  // Las duraciones de contenido empiezan en 1 s (min del formulario). El tope
  // de transicion tiene que dejar ver algo entre transicion y transicion.
  assert.ok(cargar().__max <= 3000);
});
