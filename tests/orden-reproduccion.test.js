/**
 * Orden de reproduccion: en fila o al azar.
 *
 * Una pantalla de tienda repite el mismo ciclo todo el dia. Con pocos
 * contenidos, el orden fijo hace que el cliente que espera su turno vea
 * exactamente la misma secuencia tres veces seguidas.
 *
 * Lo delicado no es barajar -eso es Fisher-Yates- sino el empalme entre una
 * vuelta y la siguiente: si la ultima de una vuelta es la primera de la
 * siguiente, el mismo cartel sale dos veces seguidas y parece que se ha
 * colgado. Por eso ordenReproduccion recibe cual fue el ultimo.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Orden de reproduccion";
const FIN = "// ── fin del orden";

// random devuelve siempre lo mismo para que el barajado sea predecible y se
// pueda afirmar algo concreto en vez de "sale una permutacion cualquiera".
function cargar(random) {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el bloque de orden en player.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { Math: { floor: Math.floor, random: random || Math.random } };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const plano = c => JSON.parse(JSON.stringify(c));

// ── En fila ────────────────────────────────────────────────────────────────

test("sin aleatorio, el orden es el que puso el usuario", () => {
  const c = cargar();
  assert.deepStrictEqual(plano(c.ordenReproduccion(4, false, -1)), [0, 1, 2, 3]);
});

test("sin aleatorio, el ultimo reproducido da igual", () => {
  // El orden lo decide el usuario arrastrando en la playlist; nada lo altera.
  const c = cargar();
  assert.deepStrictEqual(plano(c.ordenReproduccion(3, false, 0)), [0, 1, 2]);
});

// ── Al azar ────────────────────────────────────────────────────────────────

test("al azar salen todos, una sola vez cada uno", () => {
  // Barajar no puede perder ni duplicar contenidos: se veria como una
  // diapositiva que desaparece del ciclo sin motivo.
  const c = cargar();
  const o = plano(c.ordenReproduccion(6, true, -1));
  assert.strictEqual(o.length, 6);
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2, 3, 4, 5]);
});

test("al azar de verdad cambia el orden", () => {
  const c = cargar(() => 0);          // barajado determinista
  assert.notDeepStrictEqual(plano(c.ordenReproduccion(3, true, -1)), [0, 1, 2]);
});

test("el mismo contenido no sale dos veces seguidas al cambiar de vuelta", () => {
  // Con random()=0 la baraja de 3 da [1,2,0]. Si la vuelta anterior acabo en 1,
  // el 1 abriria la siguiente: dos veces seguidas.
  const c = cargar(() => 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(3, true, -1)), [1, 2, 0],
    "control: sin ultimo, la baraja empieza por 1");
  const o = plano(c.ordenReproduccion(3, true, 1));
  assert.notStrictEqual(o[0], 1, "no puede repetir el ultimo de la vuelta anterior");
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2],
    "y sigue habiendo los tres");
});

// ── Casos limite ───────────────────────────────────────────────────────────

test("con un solo contenido no hay nada que evitar", () => {
  // Repetirlo es inevitable: es el unico que hay. No puede quedarse en bucle
  // intentando que no se repita.
  const c = cargar(() => 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(1, true, 0)), [0]);
});

test("una playlist vacia no da orden ninguno", () => {
  const c = cargar();
  assert.deepStrictEqual(plano(c.ordenReproduccion(0, true, -1)), []);
  assert.deepStrictEqual(plano(c.ordenReproduccion(0, false, -1)), []);
});

test("dos contenidos al azar siempre alternan", () => {
  // Con dos, evitar la repeticion obliga a alternar. Es lo esperable.
  const c = cargar(() => 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(2, true, 1))[0], 0);
  assert.deepStrictEqual(plano(c.ordenReproduccion(2, true, 0))[0], 1);
});

// ── Prioridad (p.ej. el tablero de divisas cada X pases) ────────────────────

test("sin prioritarios, se comporta exactamente igual que antes", () => {
  const c = cargar(() => 0);
  assert.deepStrictEqual(
    plano(c.ordenReproduccion(6, true, -1)),
    plano(c.ordenReproduccion(6, true, -1, [], 4)),
    "pasar cada=4 sin prioritarios no debe cambiar nada"
  );
});

test("un prioritario sale cada 4 pases, aunque para eso repita mas que el resto", () => {
  // 8 contenidos, el indice 5 marcado. Con solo UN prioritario y una vuelta
  // larga, cumplir "cada 4" exige que ese mismo indice vuelva a salir dentro
  // de la misma vuelta -es justo lo que "prioritario" quiere decir: el resto
  // no se repite, este si, tantas veces como haga falta para su cadencia.
  // random()=0 hace el barajado determinista: se comprueba la CADENCIA, no
  // una permutacion concreta.
  const c = cargar(() => 0);
  const o = plano(c.ordenReproduccion(8, true, -1, [5], 4));
  const normales = o.filter(v => v !== 5);
  assert.deepStrictEqual([...normales].sort((x, y) => x - y), [0, 1, 2, 3, 4, 6, 7],
    "los siete no-prioritarios salen todos, una sola vez cada uno");
  const posiciones = o.reduce((a, v, i) => { if (v === 5) a.push(i + 1); return a; }, []);
  assert.deepStrictEqual(posiciones, [4, 8], "el prioritario cae en la posicion 4 y la 8: cadencia de 4");
});

test("con dos prioritarios, se turnan en vez de amontonarse", () => {
  const c = cargar(() => 0);
  const o = plano(c.ordenReproduccion(9, true, -1, [3, 7], 4));
  assert.strictEqual(o.length, 9);
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2, 3, 4, 5, 6, 7, 8]);
  const huecos = [o[3], o[7]];
  assert.deepStrictEqual([...huecos].sort(), [3, 7], "los dos prioritarios ocupan los huecos de cadencia");
});

test("mas prioritarios que huecos: los que sobran igual aparecen", () => {
  // Prioritario significa "aparece seguro", no "se descarta si no cupo".
  const c = cargar(() => 0);
  const o = plano(c.ordenReproduccion(5, true, -1, [0, 1, 2, 3], 4));
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2, 3, 4]);
});

test("todos son prioritarios: no hay huecos que repartir, simplemente se barajan", () => {
  const c = cargar(() => 0);
  const o = plano(c.ordenReproduccion(3, true, -1, [0, 1, 2], 4));
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2]);
});

test("cada < 2 no tiene sentido y se ignora: cae al barajado normal", () => {
  const c = cargar(() => 0);
  assert.deepStrictEqual(
    plano(c.ordenReproduccion(5, true, -1, [2], 1)),
    plano(c.ordenReproduccion(5, true, -1, [], 1))
  );
});

test("el prioritario tambien respeta el empalme entre vueltas", () => {
  const c = cargar(() => 0);
  const o = plano(c.ordenReproduccion(6, true, 3, [5], 4));  // 'ultimo'=3 no puede abrir
  assert.notStrictEqual(o[0], 3);
  assert.deepStrictEqual([...o].sort((x, y) => x - y), [0, 1, 2, 3, 4, 5]);
});
