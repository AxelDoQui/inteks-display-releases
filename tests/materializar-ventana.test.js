/**
 * Cargar y soltar el medio de cada diapositiva segun la ventana.
 *
 * ventanaSlides() decide QUE diapositivas se quedan cargadas
 * (tests/ventana-slides.test.js). Esto prueba la otra mitad: que de verdad se
 * les pone el src a las que entran y se les quita a las que salen. Si esta
 * parte falla, una tienda se queda con la pantalla en negro o con la caja sin
 * memoria, que son justo los dos extremos que se quieren evitar.
 *
 * El bloque real de player.html se ejecuta en un vm contra un DOM de mentira:
 * el navegador de verdad no hace falta para comprobar que se pone y se quita un
 * atributo.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

function bloque(src, inicio, fin) {
  const a = src.indexOf(inicio);
  const b = src.indexOf(fin, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra el bloque "${inicio}" .. "${fin}" en player.html`);
  }
  return src.slice(a, b);
}

function medio(tag, src) {
  return {
    tagName: tag,
    preload: tag === "VIDEO" ? "none" : undefined,
    dataset: { medio: src },
    _at: {},
    getAttribute(k) { return k in this._at ? this._at[k] : null; },
    setAttribute(k, v) { this._at[k] = v; },
    hasAttribute(k) { return k in this._at; },
    removeAttribute(k) { delete this._at[k]; },
    load() { this.soltado = (this.soltado || 0) + 1; },
  };
}

// `tipos`: un elemento por diapositiva, "img" o "video".
function cargar(tipos, posOrden, locales) {
  const src = fs.readFileSync(PLAYER, "utf8");
  const medios = tipos.map((t, i) =>
    medio(t === "video" ? "VIDEO" : "IMG", `/uploads/${i}.${t === "video" ? "mp4" : "png"}`));
  const slides = medios.map((m, i) => ({
    dataset: { i: String(i) },
    querySelector: () => m,
  }));
  const ctx = {
    Math,
    document: { querySelectorAll: () => slides },
    orden: tipos.map((_, i) => i),
    posOrden,
    playlist: tipos.map(() => ({})),
    mediosLocales: locales || {},
    urlDeMedio: (s, l) => (l && l[s]) || s,
    parseInt,
    medios,
  };
  vm.createContext(ctx);
  vm.runInContext(bloque(src, "// ── Ventana de diapositivas", "// ── fin de la ventana"), ctx);
  vm.runInContext(bloque(src, "// ── Materializar la ventana", "// ── fin de materializar"), ctx);
  return ctx;
}

test("las diapositivas cercanas reciben su medio y las lejanas no", () => {
  const c = cargar(new Array(50).fill("img"), 10);
  c.materializarVentana();
  const conSrc = c.medios.map((m, i) => (m.hasAttribute("src") ? i : -1)).filter(i => i >= 0);
  // Radio 2: la anterior, la actual y las dos siguientes.
  assert.deepStrictEqual(JSON.parse(JSON.stringify(conSrc)), [8, 9, 10, 11, 12]);
  assert.strictEqual(conSrc.length, 5, "con 50 contenidos solo 5 imagenes cargadas");
});

test("al avanzar, lo que queda atras se suelta", () => {
  // Es la mitad que de verdad libera memoria: sin esto, la ventana solo
  // retrasaria el problema unas cuantas diapositivas.
  const c = cargar(new Array(50).fill("img"), 10);
  c.materializarVentana();
  assert.ok(c.medios[8].hasAttribute("src"), "control: la 8 estaba cargada");
  c.posOrden = 20;
  c.materializarVentana();
  assert.ok(!c.medios[8].hasAttribute("src"), "la 8 ya esta lejos: se suelta");
  assert.ok(c.medios[20].hasAttribute("src"), "y la nueva actual esta cargada");
});

test("un video lejano suelta el bufer y deja de precargar", () => {
  const tipos = new Array(20).fill("video");
  const c = cargar(tipos, 2);
  c.materializarVentana();
  const v = c.medios[2];
  assert.strictEqual(v.preload, "auto", "el que toca se adelanta");
  c.posOrden = 12;
  c.materializarVentana();
  assert.strictEqual(v.preload, "none");
  assert.ok(!v.hasAttribute("src"));
  assert.ok(v.soltado >= 1, "hay que llamar a load() o el navegador conserva lo bufereado");
});

test("si llega la copia local, la diapositiva pasa a usarla sin rehacer nada", () => {
  // sincronizarMedios ya no reconstruye el DOM entero: solo repasa la ventana.
  const c = cargar(new Array(6).fill("img"), 0);
  c.materializarVentana();
  assert.strictEqual(c.medios[0].getAttribute("src"), "/uploads/0.png");
  c.mediosLocales["/uploads/0.png"] = "blob:local-0";
  c.materializarVentana();
  assert.strictEqual(c.medios[0].getAttribute("src"), "blob:local-0");
});

test("con pocos contenidos se cargan todos, como antes", () => {
  // Las tiendas de hoy tienen tres o cuatro. El cambio no puede empeorar ese
  // caso descargando y recargando sin parar.
  const c = cargar(["img", "img", "img"], 1);
  c.materializarVentana();
  assert.ok(c.medios.every(m => m.hasAttribute("src")));
});
