/**
 * Que diapositivas se mantienen cargadas en memoria.
 *
 * El reproductor monta TODAS las diapositivas en el DOM. Con 4 contenidos da
 * igual; con 50 no: las que no se ven estan en opacity:0, que se sigue
 * pintando, asi que el navegador decodifica las 50 imagenes. Una imagen 1080p
 * descomprimida ocupa ~8 MB, y una caja Android de 1-2 GB no aguanta eso: el
 * sistema mata la aplicacion y la pantalla se queda en negro.
 *
 * La solucion es tener cargadas solo unas pocas: la actual, la que acaba de
 * salir -que sigue animandose- y las siguientes, para que la proxima este lista
 * ANTES de que le toque y no haya parpadeo negro al cambiar.
 *
 * Se calcula sobre el ORDEN de reproduccion y no sobre los indices de la
 * playlist: con el orden aleatorio, la siguiente no es la de al lado.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Ventana de diapositivas";
const FIN = "// ── fin de la ventana";

const plano = (x) => JSON.parse(JSON.stringify(x));

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra el bloque "${INICIO}" .. "${FIN}" en player.html`);
  }
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const orden = (n) => Array.from({ length: n }, (_, i) => i);

test("se queda la actual, la anterior y la siguiente", () => {
  const c = cargar();
  assert.deepStrictEqual(plano(c.ventanaSlides(orden(50), 10, 1)), [9, 10, 11]);
});

test("la anterior cuenta porque todavia se esta yendo", () => {
  // La transicion dura hasta un segundo: si se descarga la que sale, se ve
  // desaparecer de golpe en mitad del fundido.
  const c = cargar();
  assert.ok(plano(c.ventanaSlides(orden(50), 10, 1)).includes(9));
});

test("al principio y al final la ventana da la vuelta", () => {
  // El ciclo es circular: despues de la ultima viene la primera, y esa tiene
  // que estar cargada antes de que le toque.
  const c = cargar();
  assert.deepStrictEqual(plano(c.ventanaSlides(orden(50), 0, 1)), [0, 1, 49]);
  assert.deepStrictEqual(plano(c.ventanaSlides(orden(50), 49, 1)), [0, 48, 49]);
});

test("manda el orden de reproduccion, no el de la playlist", () => {
  // Con el orden aleatorio la siguiente no es la de al lado. Cargar por
  // cercania de indice traeria la diapositiva equivocada.
  const c = cargar();
  assert.deepStrictEqual(plano(c.ventanaSlides([7, 2, 9, 4], 1, 1)), [2, 7, 9]);
});

test("con menos contenidos que ventana, se quedan todos y sin repetir", () => {
  // Es el caso de hoy en casi todas las tiendas: tres o cuatro contenidos.
  // No puede devolver duplicados ni ponerse a dar vueltas.
  const c = cargar();
  assert.deepStrictEqual(plano(c.ventanaSlides(orden(3), 0, 2)), [0, 1, 2]);
  assert.deepStrictEqual(plano(c.ventanaSlides(orden(2), 1, 5)), [0, 1]);
  assert.deepStrictEqual(plano(c.ventanaSlides(orden(1), 0, 3)), [0]);
});

test("una playlist vacia no carga nada", () => {
  const c = cargar();
  assert.deepStrictEqual(plano(c.ventanaSlides([], 0, 2)), []);
});

test("una posicion fuera de rango no rompe la reproduccion", () => {
  // posOrden puede quedar apuntando fuera un instante al cambiar la playlist.
  // Antes de dejar la pantalla en negro, mas vale cargar algo.
  const c = cargar();
  const v = plano(c.ventanaSlides(orden(4), 99, 1));
  assert.ok(v.length > 0 && v.every(i => i >= 0 && i < 4));
});
