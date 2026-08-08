/**
 * La identidad de una pantalla vive en dos almacenes del navegador a la vez:
 * localStorage y una cookie de un año. Hay navegadores de televisor que limpian
 * uno al apagarse pero no el otro, y perder la identidad significa que el TV
 * arranca pidiendo un código en lugar de mostrar el escaparate.
 *
 * El bloque de funciones está REPETIDO en index.html, pair.html y player.html.
 * No está en un .js aparte a propósito: un <script src> obliga a hablar con el
 * servidor antes de poder decidir a dónde ir, y con el servidor caído el
 * televisor se quedaría en blanco. Cada página tiene que decidir sola.
 *
 * Este test es el precio de esa duplicación: exige que las tres copias sean
 * idénticas. Si falla, copia el bloque bueno a las otras dos.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.join(__dirname, "..");
const PAGINAS = ["index.html", "pair.html", "player.html"];
const INICIO = "// ── Identidad de la pantalla";
const FIN = "// ── fin del bloque compartido";

function bloque(archivo) {
  const src = fs.readFileSync(path.join(ROOT, archivo), "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error(`No se encuentra el bloque de identidad en ${archivo} ` +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  return src.slice(a, b);
}

// Almacenes de mentira, para poder mirar dentro de cada uno por separado.
function stubStorage(inicial) {
  const store = { ...(inicial || {}) };
  return {
    _store: store,
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; },
  };
}

function stubDocument(inicial) {
  const jar = new Map(Object.entries(inicial || {}));
  return {
    _jar: jar,
    get cookie() {
      return [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
    },
    set cookie(str) {
      const trozos = str.split(";");
      const i = trozos[0].indexOf("=");
      const k = trozos[0].slice(0, i).trim();
      const v = trozos[0].slice(i + 1).trim();
      const edad = trozos.slice(1).map(s => s.trim().toLowerCase())
                         .find(s => s.startsWith("max-age="));
      if (edad && parseInt(edad.slice(8), 10) <= 0) jar.delete(k);
      else jar.set(k, v);
    },
  };
}

function cargar(ls, doc) {
  const ctx = { localStorage: ls, document: doc, decodeURIComponent, encodeURIComponent };
  vm.createContext(ctx);
  vm.runInContext(bloque("player.html"), ctx);
  return ctx;
}

test("las tres páginas llevan el mismo bloque, carácter a carácter", () => {
  const ref = bloque(PAGINAS[0]);
  for (const p of PAGINAS.slice(1)) {
    assert.strictEqual(bloque(p), ref,
      `el bloque de identidad de ${p} difiere del de ${PAGINAS[0]}`);
  }
});

test("guardar escribe en los DOS almacenes", () => {
  const ls = stubStorage(), doc = stubDocument();
  cargar(ls, doc).guardarIdentidad("Escaparate");
  assert.strictEqual(ls._store["signalos_screen_id"], "Escaparate");
  assert.strictEqual(doc._jar.get("signalos_screen"), "Escaparate");
});

test("leer recupera de localStorage", () => {
  const c = cargar(stubStorage({ "signalos_screen_id": "Caja-1" }), stubDocument());
  assert.strictEqual(c.leerIdentidad(), "Caja-1");
});

test("leer recupera de la cookie cuando localStorage está vacío", () => {
  // Este es el caso que motiva todo: el televisor limpió localStorage al
  // apagarse, pero la cookie sobrevivió.
  const c = cargar(stubStorage(), stubDocument({ "signalos_screen": "Caja-1" }));
  assert.strictEqual(c.leerIdentidad(), "Caja-1");
});

test("sin nada guardado, leer devuelve null", () => {
  assert.strictEqual(cargar(stubStorage(), stubDocument()).leerIdentidad(), null);
});

test("olvidar limpia los DOS almacenes", () => {
  // Si solo limpiara localStorage, una pantalla borrada entraría en bucle:
  // /pair leería la cookie, iría al player, el SSE diría «deleted», y vuelta.
  const ls = stubStorage(), doc = stubDocument();
  const c = cargar(ls, doc);
  c.guardarIdentidad("Escaparate");
  c.olvidarIdentidad();
  assert.strictEqual(ls._store["signalos_screen_id"], undefined, "queda en localStorage");
  assert.strictEqual(doc._jar.has("signalos_screen"), false, "queda la cookie");
  assert.strictEqual(c.leerIdentidad(), null);
});

test("los nombres con espacios y acentos sobreviven al viaje por la cookie", () => {
  const doc = stubDocument();
  const c = cargar(stubStorage(), doc);
  c.guardarIdentidad("TV Salón");
  assert.strictEqual(cargar(stubStorage(), doc).leerIdentidad(), "TV Salón");
});

test("guardar una identidad vacía no hace nada", () => {
  const ls = stubStorage({ "signalos_screen_id": "Caja-1" });
  cargar(ls, stubDocument()).guardarIdentidad("");
  assert.strictEqual(ls._store["signalos_screen_id"], "Caja-1",
    "una llamada con cadena vacía no debe borrar la identidad buena");
});
