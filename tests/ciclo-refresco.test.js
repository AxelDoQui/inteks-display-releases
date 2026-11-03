/**
 * El refresco periodico no puede mover el puntero de reproduccion.
 *
 * El player pregunta al servidor por su playlist cada 15 segundos. Ese refresco
 * llamaba a rehacerOrden() SIEMPRE -para enterarse de que alguien habia
 * activado el orden aleatorio sin cambiar el contenido- y rehacerOrden pone
 * posOrden a cero. Con pases de 10 segundos, cada refresco devolvia el puntero
 * al principio y el siguiente avance saltaba otra vez al segundo elemento: la
 * pantalla se quedaba atascada mostrando siempre el mismo, y los demas no
 * aparecian nunca.
 *
 * Detectado en una tienda con 2 imagenes y 2 tableros de divisas intercalados:
 * solo se veia uno de los tableros. Y como un tablero de dos paginas dura el
 * doble (cada pagina dura lo que dure el item), parecia ademas que "duraba mas
 * de lo puesto".
 *
 * Se cargan los bloques reales de player.html en un vm, con lo que toca el DOM
 * sustituido por muñones.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

// Los arrays creados dentro del vm son de otro realm: deepStrictEqual los
// rechaza aunque tengan el mismo contenido. Se pasan por JSON.
const plano = (x) => JSON.parse(JSON.stringify(x));

function bloque(src, inicio, fin) {
  const a = src.indexOf(inicio);
  const b = src.indexOf(fin, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra el bloque "${inicio}" .. "${fin}" en player.html`);
  }
  return src.slice(a, b);
}

// `nItems`: cuantos contenidos tiene la playlist. showSlide queda sustituido por
// un registrador: lo que importa no es como se pinta, sino QUE indice toca.
function cargar(nItems) {
  const src = fs.readFileSync(PLAYER, "utf8");
  const mostrados = [];
  const ctx = {
    Math,
    playlist: new Array(nItems).fill({}),
    screenConfig: { shuffle: false },
    timer: null,                    // next() lo limpia antes de avanzar
    clearTimeout: () => {},
    wallSigue: () => false,         // sin videowall, next() avanza como siempre
    showSlide: (i) => mostrados.push(i),
    mostrados,
  };
  vm.createContext(ctx);
  vm.runInContext(bloque(src, "// ── Orden de reproduccion", "// ── fin del orden"), ctx);
  vm.runInContext(bloque(src, "// ── Ciclo de reproduccion", "// ── fin del ciclo"), ctx);
  return ctx;
}

test("un refresco sin cambios no mueve el puntero de reproduccion", () => {
  // Esta es la tienda: 2 imagenes y 2 tableros, y un refresco cada 15 s que cae
  // en medio del ciclo. La lista tiene que seguir avanzando 0,1,2,3.
  const c = cargar(4);
  c.rehacerOrden();
  c.showSlide(c.orden[0]);          // arranque, como hace loadPlaylist

  c.next();
  c.refrescarOrden(false, false);   // el refresco de los 15 s: nada ha cambiado
  c.next();
  c.refrescarOrden(false, false);
  c.next();

  assert.deepStrictEqual(plano(c.mostrados), [0, 1, 2, 3],
    "con refrescos por medio la playlist se quedaba atascada repitiendo el segundo");
});

test("si cambia el contenido, el ciclo si empieza de nuevo", () => {
  // Contenido nuevo es contenido nuevo: se rehace el orden y se empieza por el
  // principio. Lo contrario dejaria el puntero apuntando a un item que ya no es.
  const c = cargar(4);
  c.rehacerOrden();
  c.next(); c.next();               // vamos por el tercero
  c.refrescarOrden(true, false);    // el panel publico otra playlist
  c.next();
  assert.strictEqual(c.mostrados[c.mostrados.length - 1], 1,
    "tras un cambio real, el ciclo arranca desde el principio");
});

test("si el usuario activa el orden aleatorio, se rehace aunque no cambie el contenido", () => {
  // Es el caso por el que se rehacia siempre. Se conserva, pero solo cuando de
  // verdad ha cambiado el ajuste.
  const c = cargar(4);
  c.rehacerOrden();
  c.next(); c.next();
  const antes = c.posOrden;
  c.refrescarOrden(false, true);
  assert.notStrictEqual(c.posOrden, antes, "el puntero vuelve al principio");
  assert.strictEqual(c.posOrden, 0);
});

test("si aun no hay orden, el refresco lo crea", () => {
  // Arranque desde cache con el servidor caido: el orden puede estar vacio
  // cuando llega la primera respuesta buena. Sin esto, next() no tendria por
  // donde ir y la pantalla se quedaria clavada en la primera.
  const c = cargar(3);
  assert.deepStrictEqual(plano(c.orden), []);
  c.refrescarOrden(false, false);
  assert.deepStrictEqual(plano(c.orden), [0, 1, 2]);
});
