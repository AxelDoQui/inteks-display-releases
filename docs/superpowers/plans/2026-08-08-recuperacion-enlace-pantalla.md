# Recuperación del enlace de una pantalla — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un televisor que se apaga y enciende vuelva solo a su contenido, y que cuando pierda su identidad se le pueda devolver desde el panel sin destruir su configuración.

**Architecture:** La identidad de la pantalla pasa a vivir en dos almacenes del navegador (localStorage y una cookie de un año) gestionados por tres funciones repetidas literalmente en las tres páginas. `/pair` deja de pedir código a ciegas: si reconoce una identidad, avisa y devuelve el televisor a su player. En el servidor, `pair-claim` gana un modo `reenlazar` que asigna un código a una pantalla que ya existe sin tocar su playlist, y aparece `/api/screen-unlink` para soltar un dispositivo desde el panel.

**Tech Stack:** Python 3 solo con la biblioteca estándar (`ThreadingHTTPServer`), HTML/CSS/JS a pelo sin paso de compilación, pruebas con `node --test` y scripts de Python que arrancan el servidor de verdad.

## Global Constraints

- **Sin dependencias nuevas.** Ni en el servidor (solo biblioteca estándar) ni en el navegador (nada de librerías externas, no hay bundler).
- **Los identificadores internos no se renombran.** `signalos_screen_id`, `signalos_session`, `X-SignalOS-Token` y `SIGNALOS_DATA` conservan el nombre antiguo a propósito: renombrarlos desenlazaría todas las pantallas ya instaladas. La cookie nueva se llama `signalos_screen` por coherencia con ellos.
- **`/api/pair-request` y `/api/pair-status` siguen antes de la puerta de autenticación** (línea `PUERTA DE CONTROL`, `server.py:884`): una pantalla sin enlazar no tiene sesión. `/api/pair-pending`, `/api/pair-claim` y el nuevo `/api/screen-unlink` van **después**.
- **Retrocompatibilidad de `pair-claim`:** sin campo `modo` se comporta exactamente como hoy. Los tests que ya existen no se modifican.
- **Comentarios y textos de interfaz en español**, como el resto del proyecto.
- **Nada de secretos en git:** `admin.json` y `pin.json` siguen fuera del repositorio y fuera del instalador.
- **Órdenes de prueba:** `npm test` para los tests de Node; `python tests/<archivo>.py` para cada suite de Python.

---

### Task 1: El bloque compartido de identidad

Las tres funciones que leen, guardan y olvidan la identidad de la pantalla, repetidas carácter a carácter en las tres páginas, con un test que impide que se separen en silencio.

**Files:**
- Create: `tests/identidad.test.js`
- Modify: `index.html` (insertar bloque antes del IIFE del router, línea 33)
- Modify: `pair.html` (insertar bloque tras `const elError = ...`, línea 64)
- Modify: `player.html` (insertar bloque antes de `const params=new URLSearchParams`, línea 137)

**Interfaces:**
- Consumes: nada
- Produces: `leerIdentidad() -> string|null`, `guardarIdentidad(sid: string) -> void`, `olvidarIdentidad() -> void`, y la constante `IDENT_KEY = "signalos_screen_id"`. Las tareas 2, 6 y las páginas los usan.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/identidad.test.js`:

```js
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
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test`
Expected: FALLA con `No se encuentra el bloque de identidad en index.html`.

- [ ] **Step 3: Insertar el bloque en `player.html`**

En `player.html`, justo antes de la línea `const params=new URLSearchParams(location.search);` (línea 137), insertar exactamente esto:

```js
// ── Identidad de la pantalla ───────────────────────────────────────────────
// BLOQUE COMPARTIDO: copia literal en index.html, pair.html y player.html.
// Va repetido a propósito y no en un .js aparte: un <script src> obliga a
// hablar con el servidor antes de poder decidir a dónde ir, y con el servidor
// caído el televisor se quedaría en blanco. Cada página decide sola.
//
// Dos almacenes porque hay navegadores de TV que limpian uno al apagarse pero
// no el otro. Solo son más robustos si se olvidan A LA VEZ: si olvidar dejara
// la cookie puesta, una pantalla borrada rebotaría entre /pair y el player sin
// parar. tests/identidad.test.js vigila las dos cosas.
var IDENT_KEY = "signalos_screen_id";
var IDENT_COOKIE = "signalos_screen";
function leerIdentidad(){
  try{ var v = localStorage.getItem(IDENT_KEY); if(v) return v; }catch(e){}
  try{
    var m = document.cookie.match(/(?:^|;\s*)signalos_screen=([^;]*)/);
    if(m && m[1]) return decodeURIComponent(m[1]);
  }catch(e){}
  return null;
}
function guardarIdentidad(sid){
  if(!sid) return;
  try{ localStorage.setItem(IDENT_KEY, sid); }catch(e){}
  try{ document.cookie = IDENT_COOKIE + "=" + encodeURIComponent(sid) +
       ";path=/;max-age=31536000;samesite=lax"; }catch(e){}
}
function olvidarIdentidad(){
  try{ localStorage.removeItem(IDENT_KEY); }catch(e){}
  try{ document.cookie = IDENT_COOKIE + "=;path=/;max-age=0;samesite=lax"; }catch(e){}
}
// ── fin del bloque compartido ──────────────────────────────────────────────
```

Nota para quien implemente: `var` y `function`, no `const` ni funciones flecha. El arnés de pruebas ejecuta el bloque con `vm.runInContext` y ahí `const` **no** se engancha al objeto de contexto, así que el test no podría verlas.

- [ ] **Step 4: Copiar el mismo bloque a `index.html` y `pair.html`**

En `index.html`, dentro del `<script>`, **antes** del `(function(){` de la línea 33.
En `pair.html`, dentro del `<script>`, después de `const elError = document.getElementById("error");` (línea 64).

Copia literal, sin reindentar ni cambiar una coma: el test compara carácter a carácter.

- [ ] **Step 5: Hacer que el router de `index.html` use la identidad compartida**

Insertar el bloque no basta: el router sigue leyendo `localStorage` a pelo y se
perdería el respaldo de la cookie justo en el camino de arranque principal.

Sustituir en `index.html` las líneas 34-35:

```js
  var sid = null;
  try { sid = localStorage.getItem("signalos_screen_id"); } catch(e){}
```

por:

```js
  var sid = leerIdentidad();
```

- [ ] **Step 6: Ejecutar los tests**

Run: `npm test`
Expected: PASAN los 8 tests nuevos de `identidad.test.js` y siguen pasando los 92 anteriores.

- [ ] **Step 7: Commit**

```bash
git add tests/identidad.test.js index.html pair.html player.html
git commit -m "feat: la identidad de la pantalla se guarda en dos almacenes"
```

---

### Task 2: `/pair` reconoce una pantalla ya enlazada

La página de emparejamiento deja de pedir código a ciegas. La decisión se extrae a una función pura para poder probarla sin navegador.

**Files:**
- Create: `tests/pair-reanudar.test.js`
- Modify: `pair.html` (bloque `<script>`, y el HTML del `.container`)

**Interfaces:**
- Consumes: `leerIdentidad()`, `guardarIdentidad()`, `olvidarIdentidad()` de la tarea 1
- Produces: `decidirArranque(identidad, params) -> {accion:"reanudar", screen} | {accion:"pedir", knownAs}`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/pair-reanudar.test.js`:

```js
/**
 * /pair pedía un código SIEMPRE, sin mirar si el dispositivo ya estaba
 * enlazado. Bastaba con que alguien dejara /pair como página de inicio del
 * televisor —cosa que pasa, porque nadie recuerda la URL larga del player—
 * para que cada encendido pidiera un código nuevo.
 *
 * Y no había arreglo posible desde el panel: pair-claim rechazaba el nombre
 * real de esa pantalla por duplicado, así que o te inventabas «Escaparate-2»
 * con la playlist vacía, o borrabas la pantalla buena.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PAIR = path.join(__dirname, "..", "pair.html");
const INICIO = "// ── Decisión de arranque";
const FIN = "// ── fin de la decisión de arranque";

function cargar() {
  const src = fs.readFileSync(PAIR, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra decidirArranque en pair.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { URLSearchParams };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const params = q => new URLSearchParams(q);

test("sin identidad guardada, pide código", () => {
  const d = cargar().decidirArranque(null, params(""));
  assert.strictEqual(d.accion, "pedir");
  assert.strictEqual(d.knownAs, "");
});

test("con identidad guardada, reanuda en vez de pedir código", () => {
  // El caso de todos los días: el TV se enciende y alguien había dejado /pair
  // como página de inicio.
  const d = cargar().decidirArranque("Escaparate", params(""));
  assert.strictEqual(d.accion, "reanudar");
  assert.strictEqual(d.screen, "Escaparate");
});

test("con ?nuevo=1 pide código aunque haya identidad", () => {
  // La vía de escape: reenlazar a propósito un televisor que ya funcionaba.
  const d = cargar().decidirArranque("Escaparate", params("nuevo=1"));
  assert.strictEqual(d.accion, "pedir");
});

test("?era= viaja como known_as para que el panel sugiera el reenlace", () => {
  const d = cargar().decidirArranque(null, params("nuevo=1&era=Escaparate"));
  assert.strictEqual(d.accion, "pedir");
  assert.strictEqual(d.knownAs, "Escaparate");
});

test("si falta ?era= pero queda identidad, se usa esa como sugerencia", () => {
  const d = cargar().decidirArranque("Caja-1", params("nuevo=1"));
  assert.strictEqual(d.knownAs, "Caja-1");
});

test("?era= manda sobre la identidad que quede suelta", () => {
  const d = cargar().decidirArranque("Vieja", params("nuevo=1&era=Escaparate"));
  assert.strictEqual(d.knownAs, "Escaparate");
});

test("?era= sin ?nuevo=1 no impide reanudar", () => {
  // era= es solo una pista para el panel; no es una orden de desenlazar.
  const d = cargar().decidirArranque("Escaparate", params("era=Otra"));
  assert.strictEqual(d.accion, "reanudar");
  assert.strictEqual(d.screen, "Escaparate");
});
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test`
Expected: FALLA con `No se encuentra decidirArranque en pair.html`.

- [ ] **Step 3: Añadir `decidirArranque` a `pair.html`**

Después del bloque de identidad insertado en la tarea 1, añadir:

```js
// ── Decisión de arranque ───────────────────────────────────────────────────
// Antes esta página pedía código siempre. Ahora primero mira si el dispositivo
// ya sabe quién es: si lo sabe, lo devuelve a su contenido en vez de fabricar
// un emparejamiento duplicado.
//
// No se pregunta al servidor si esa pantalla sigue existiendo, y es deliberado:
// el player ya lo resuelve solo —el SSE responde «deleted» y él olvida la
// identidad y vuelve aquí—, así que no hace falta un endpoint público nuevo. Y
// con el servidor caído acabar en el player es MEJOR: muestra su caché en vez
// de un código que no sirve de nada.
function decidirArranque(identidad, params){
  var forzar = params.get("nuevo") === "1";
  var era = params.get("era") || "";
  if(!forzar && identidad) return {accion:"reanudar", screen:identidad};
  return {accion:"pedir", knownAs: era || identidad || ""};
}
// ── fin de la decisión de arranque ─────────────────────────────────────────
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test`
Expected: PASAN los 7 tests de `pair-reanudar.test.js`.

- [ ] **Step 5: Añadir el aviso de reanudación al HTML**

En `pair.html`, dentro de `<div class="container">`, después de `<div class="error" id="error"></div>` (línea 53), añadir:

```html
  <div class="reanudar" id="reanudar">
    <div class="reanudar-txt">Ya enlazada como <strong id="rean-nombre"></strong></div>
    <div class="reanudar-sub">Abriendo su contenido en <span id="rean-seg">6</span> s…</div>
    <button class="reanudar-btn" id="rean-btn">Enlazar de nuevo</button>
  </div>
```

Y en el `<style>`, antes de `.pie`:

```css
/* Aviso cuando la pantalla ya estaba enlazada. El botón es grande y de alto
   contraste porque a veces hay que pulsarlo con el mando del televisor desde
   el otro lado del local. */
.reanudar{display:none;margin-top:2vmin}
.reanudar.visible{display:block}
.reanudar-txt{font-size:clamp(15px,2.6vmin,26px);margin-bottom:1vmin}
.reanudar-sub{font-size:clamp(12px,1.9vmin,18px);color:#7a8ca3;margin-bottom:4vmin}
.reanudar-btn{font-family:inherit;font-size:clamp(14px,2.2vmin,22px);font-weight:600;
  padding:clamp(12px,2vmin,22px) clamp(24px,4vmin,44px);border-radius:12px;
  border:2px solid #FF7F00;background:transparent;color:#FF7F00;cursor:pointer}
.reanudar-btn:focus,.reanudar-btn:hover{background:#FF7F00;color:#07182b;outline:none}
```

- [ ] **Step 6: Conectar la decisión con la página**

En `pair.html`, sustituir la última línea del script, `pedirCodigo();`, por:

```js
// ── Arranque ───────────────────────────────────────────────────────────────
var _params = new URLSearchParams(location.search);
var _decision = decidirArranque(leerIdentidad(), _params);

if(_decision.accion === "reanudar"){
  mostrarReanudacion(_decision.screen);
}else{
  pedirCodigo(_decision.knownAs);
}

function mostrarReanudacion(sid){
  document.querySelector(".code").style.display = "none";
  document.querySelector(".hint").style.display = "none";
  document.querySelector(".subtitle").textContent = "Esta pantalla ya está configurada";
  document.getElementById("rean-nombre").textContent = sid;
  document.getElementById("reanudar").classList.add("visible");

  var seg = 6, cuenta = null;
  var elSeg = document.getElementById("rean-seg");
  var btn = document.getElementById("rean-btn");

  function irAlPlayer(){
    location.replace("/player.html?screen=" + encodeURIComponent(sid));
  }
  // Cualquier tecla o clic para la cuenta atrás. Los mandos de televisor
  // navegan con flechas y acertar con el foco del botón no siempre es fácil;
  // así basta con pulsar cualquier cosa para tener tiempo de decidir.
  function parar(){
    if(cuenta === null) return;
    clearInterval(cuenta); cuenta = null;
    document.querySelector(".reanudar-sub").textContent = "Cuenta atrás detenida";
    btn.focus();
  }
  document.addEventListener("keydown", parar);
  document.addEventListener("click", parar);

  btn.addEventListener("click", function(ev){
    ev.stopPropagation();
    // El orden importa: el nombre tiene que viajar en la URL ANTES de borrarse
    // de los almacenes, o el panel ya no puede sugerir el reenlace.
    var destino = "/pair?nuevo=1&era=" + encodeURIComponent(sid);
    olvidarIdentidad();
    location.replace(destino);
  });

  cuenta = setInterval(function(){
    seg -= 1;
    elSeg.textContent = seg;
    if(seg <= 0){ clearInterval(cuenta); cuenta = null; irAlPlayer(); }
  }, 1000);
}
```

- [ ] **Step 7: Pasar `known_as` en la petición de código y usar `guardarIdentidad`**

En `pair.html`, cambiar la firma y el cuerpo de `pedirCodigo`:

```js
async function pedirCodigo(knownAs){
  elError.style.display = "none";
  elCode.classList.add("cargando");
  elCode.textContent = "····";
  try{
    const r = await fetch("/api/pair-request", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({known_as: knownAs || ""})
    });
    const d = await r.json();
    if(!d.ok || !d.code) throw new Error("respuesta inesperada");
    token = d.token;
    elCode.textContent = d.code;
    elCode.classList.remove("cargando");
    arrancarSondeo();
  }catch(e){
    // Sin servidor no hay código posible. Se reintenta solo: la pantalla puede
    // encenderse antes que el PC, y nadie va a estar delante para recargar.
    fallo("Sin conexión con el servidor. Reintentando…");
    setTimeout(function(){ pedirCodigo(knownAs); }, 5000);
  }
}
```

Y en `comprobar()`, sustituir la línea 112:

```js
      try{ localStorage.setItem("signalos_screen_id", d.screen); }catch(e){}
```

por:

```js
      guardarIdentidad(d.screen);
```

También, en el mismo `comprobar()`, el reintento tras `expired` pasa a llevar la sugerencia:

```js
    if(d.expired){                       // el servidor se reinició y olvidó el token
      clearInterval(sondeo); token = null;
      pedirCodigo(_decision.knownAs);
      return;
    }
```

- [ ] **Step 8: Ejecutar los tests**

Run: `npm test`
Expected: todo en verde.

- [ ] **Step 9: Commit**

```bash
git add tests/pair-reanudar.test.js pair.html
git commit -m "feat: /pair reconoce una pantalla que ya estaba enlazada"
```

---

### Task 3: El servidor acepta `known_as`

Para que el panel pueda decir «este código dice que era Escaparate» y ofrecer el reenlace en un clic.

**Files:**
- Modify: `server.py:151-161` (`pending_new`), `server.py:163-170` (`pending_list`), `server.py:869-871` (endpoint `/api/pair-request`)
- Test: `tests/test_emparejamiento.py`

**Interfaces:**
- Consumes: nada
- Produces: `pending_new(known_as="") -> (code, token)`; `pending_list()` devuelve entradas con la clave adicional `known_as`; `POST /api/pair-request` acepta el cuerpo opcional `{"known_as": str}`

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_emparejamiento.py`, justo antes de la línea `check(req("/api/pair-status", {"token": "inventado"})...` (línea 97), insertar:

```python
        # ── known_as: la pista que permite el reenlace de un clic ──────────
        # Cuando un televisor se desenlaza, recuerda cómo se llamaba y lo manda
        # al pedir código. Es un dato SIN autoridad —lo envía un cliente sin
        # autenticar— y solo sirve para que el panel sugiera; quien decide es el
        # administrador.
        d3 = req("/api/pair-request", {"known_as": "TV-Escaparate"})
        pend = req("/api/pair-pending", tok=TOKEN)["pending"]
        fila = next((x for x in pend if x["code"] == d3["code"]), None)
        check(fila is not None and fila.get("known_as") == "TV-Escaparate",
              "el panel ve de que pantalla venia el codigo")

        d4 = req("/api/pair-request", {})
        fila4 = next((x for x in req("/api/pair-pending", tok=TOKEN)["pending"]
                      if x["code"] == d4["code"]), None)
        check(fila4 is not None and fila4.get("known_as") == "",
              "sin pista, known_as viene vacio y no rompe el panel")
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python tests/test_emparejamiento.py`
Expected: FALLA en `el panel ve de que pantalla venia el codigo`.

- [ ] **Step 3: Implementar en `server.py`**

Sustituir `pending_new` (líneas 151-161) por:

```python
def pending_new(known_as=""):
    """La pantalla pide un código. Devuelve (código, token).

    known_as es el nombre que el dispositivo dice recordar. Es un dato SIN
    autoridad —lo manda un cliente sin autenticar— y solo sirve para que el
    panel sugiera el reenlace. Quien decide es el administrador, y pair-claim
    valida el nombre contra screens.json igual que siempre. Se recorta a 64
    caracteres para que nadie llene la memoria mandando basura.
    """
    with pending_lock:
        _purge_pending()
        usados = {v["code"] for v in pending_screens.values()}
        for _ in range(200):
            code = f"{random.randint(0, 9999):04d}"
            if code not in usados: break
        token = secrets.token_hex(16)
        pending_screens[token] = {"code": code, "created": time.time(),
                                  "claimed_as": None, "known_as": str(known_as)[:64]}
        return code, token
```

En `pending_list` (líneas 163-170), añadir la clave al diccionario:

```python
def pending_list():
    """Códigos a la espera, para que el admin los muestre."""
    with pending_lock:
        _purge_pending()
        return sorted(
            ({"code": v["code"], "waiting_for": int(time.time() - v["created"]),
              "known_as": v.get("known_as", "")}
             for v in pending_screens.values() if not v["claimed_as"]),
            key=lambda x: x["waiting_for"])
```

Y el endpoint (líneas 869-871):

```python
        if path == "/api/pair-request":
            try:
                known_as = str(json.loads(body or "{}").get("known_as", "") or "")
            except Exception:
                known_as = ""          # cuerpo vacío o mal formado: sin pista, y ya está
            code, token = pending_new(known_as)
            jresp(200, {"ok": True, "code": code, "token": token}); return
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python tests/test_emparejamiento.py`
Expected: `TODO OK`.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_emparejamiento.py
git commit -m "feat: el codigo de emparejamiento recuerda de que pantalla venia"
```

---

### Task 4: `pair-claim` distingue crear de reenlazar

El corazón del arreglo: poder asignar un código a una pantalla que ya existe sin tocar su playlist.

**Files:**
- Modify: `server.py:915-937` (endpoint `/api/pair-claim`)
- Test: `tests/test_emparejamiento.py`

**Interfaces:**
- Consumes: `pending_claim(code, name)` (ya existe, sin cambios)
- Produces: `POST /api/pair-claim {code, screen_name, modo}` con `modo` en `"nueva"` (por omisión) o `"reenlazar"`; responde `{ok: True, screen_name, modo}`

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_emparejamiento.py`, después del bloque añadido en la tarea 3, insertar:

```python
        # ── Reenlazar: devolverle su identidad a una pantalla existente ─────
        # Es el caso que dejaba sin salida: el televisor perdió su memoria (o
        # arrancó por /pair) y hay que devolverle SU pantalla, con su playlist,
        # su horario y su rotación intactos.
        cpath = os.path.join(datos, "content.json")
        cont = json.load(open(cpath))
        cont["screens"]["TV-Escaparate"] = {
            "mode": "independent", "rotation": 90,
            "playlist": [{"id": "x1", "type": "text", "title": "HOLA"}],
            "schedule": {"lunes": {"enabled": True, "start": "09:00", "end": "21:00"}},
        }
        json.dump(cont, open(cpath, "w"))

        d5 = req("/api/pair-request", {"known_as": "TV-Escaparate"})
        r5 = req("/api/pair-claim",
                 {"code": d5["code"], "screen_name": "TV-Escaparate", "modo": "reenlazar"},
                 tok=TOKEN)
        check(r5.get("ok"), "se puede reenlazar a una pantalla que ya existe")

        st5 = req("/api/pair-status", {"token": d5["token"]})
        check(st5["claimed"] and st5["screen"] == "TV-Escaparate",
              "y la pantalla recibe su nombre de siempre")

        cont = json.load(open(cpath))["screens"]["TV-Escaparate"]
        check(len(cont.get("playlist", [])) == 1 and cont["playlist"][0]["title"] == "HOLA",
              "reenlazar NO toca la playlist")
        check(cont.get("rotation") == 90, "ni la rotacion")
        check(cont.get("schedule", {}).get("lunes", {}).get("start") == "09:00",
              "ni el horario")

        d6 = req("/api/pair-request", {})
        try:
            req("/api/pair-claim",
                {"code": d6["code"], "screen_name": "No-Existe", "modo": "reenlazar"},
                tok=TOKEN)
            check(False, "reenlazar a una inexistente deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "reenlazar a una pantalla inexistente da error")

        # Retrocompatibilidad: sin modo, se comporta como "nueva"
        try:
            req("/api/pair-claim", {"code": d6["code"], "screen_name": "TV-Escaparate"},
                tok=TOKEN)
            check(False, "sin modo, un nombre duplicado deberia seguir fallando")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "sin modo se sigue comportando como 'nueva'")

        check(req("/api/pair-claim",
                  {"code": d6["code"], "screen_name": "TV-Caja", "modo": "nueva"},
                  tok=TOKEN).get("ok"),
              "crear una pantalla nueva sigue funcionando")
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python tests/test_emparejamiento.py`
Expected: FALLA en `se puede reenlazar a una pantalla que ya existe` (el servidor responde 400 por nombre duplicado).

- [ ] **Step 3: Implementar en `server.py`**

Sustituir el bloque completo del endpoint (líneas 915-937) por:

```python
        # ── El admin pone nombre a una pantalla que está esperando
        #
        # Crear y reenlazar son intenciones opuestas y cada una se protege de su
        # propio error: crear no debe pisar una pantalla que ya existe, y
        # reenlazar no debe inventarse una que no. Antes solo existía "crear", y
        # su comprobación de duplicados dejaba sin salida el caso de un televisor
        # que había perdido su identidad: no se le podía devolver la suya.
        if path == "/api/pair-claim":
            try:
                d = json.loads(body or "{}")
                code = str(d.get("code", "")).strip()
                nombre = str(d.get("screen_name", "")).strip()
                modo = str(d.get("modo", "nueva")).strip().lower()
                if not nombre:
                    jresp(400, {"ok": False, "error": "Ponle un nombre a la pantalla"}); return
                screens = load_json(SCREENS_FILE)
                content = load_json(CONTENT_FILE)
                # Se mira en los DOS sitios: una pantalla configurada que nunca
                # llegó a conectarse vive solo en content.json, y crear encima de
                # ella le borraría la playlist.
                existe = nombre in screens or nombre in content.get("screens", {})
                if modo == "reenlazar":
                    if not existe:
                        jresp(400, {"ok": False,
                                    "error": f"No hay ninguna pantalla llamada '{nombre}'"}); return
                elif existe:
                    jresp(400, {"ok": False,
                                "error": f"Ya existe una pantalla llamada '{nombre}'"}); return
                ok_claim, msg = pending_claim(code, nombre)
                if not ok_claim:
                    jresp(400, {"ok": False, "error": msg}); return
                # Registrarla ya, para que aparezca en el panel sin esperar al SSE
                screens[nombre] = {"id": nombre, "connected": True, "last_seen": time.time()}
                save_json(SCREENS_FILE, screens)
                # setdefault y no asignación: al reenlazar, la configuración que
                # ya estuviera ahí se queda como está. Es todo el sentido del modo.
                content.setdefault("screens", {}).setdefault(
                    nombre, {"mode": "independent", "playlist": []})
                save_json(CONTENT_FILE, content)
                verbo = "reenlazada" if modo == "reenlazar" else "enlazada"
                log(f"  [enlace] pantalla '{nombre}' {verbo} con el código {code}")
                ok({"screen_name": nombre, "modo": modo})
            except Exception as e: err(e)
            return
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python tests/test_emparejamiento.py`
Expected: `TODO OK`, incluidos los checks antiguos de nombre duplicado.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_emparejamiento.py
git commit -m "feat: se puede reenlazar un codigo a una pantalla que ya existe"
```

---

### Task 5: Desenlazar desde el servidor

Soltar el dispositivo de una pantalla sin borrar nada, para poder reenlazar sin ir a tocar el televisor.

**Files:**
- Modify: `server.py:381-388` (añadir `notify_unlink` justo después de `notify_deleted`)
- Modify: `server.py` (endpoint nuevo, después de `/api/screens/delete`, línea 1008)
- Test: `tests/test_emparejamiento.py`

**Interfaces:**
- Consumes: `sse_clients`, `sse_lock`, `load_json`, `save_json`, `log`. **El test depende del de la tarea 4**: reutiliza la variable `cpath` y la pantalla `TV-Escaparate` con playlist y rotación que aquel deja preparadas. No hagas esta tarea antes que la 4.
- Produces: `notify_unlink(screen_id) -> None` (emite `data: unlink:<sid>` por SSE); `POST /api/screen-unlink {screen}` → `{ok: True, screen}`, tras la puerta de autenticación

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_emparejamiento.py`, después del bloque de la tarea 4, insertar:

```python
        # ── Desenlazar: soltar el dispositivo sin borrar la pantalla ────────
        # Es lo contrario de eliminar. La pantalla sigue ahí con todo lo suyo;
        # solo el televisor olvida quién era, para poder reenlazarlo desde el
        # panel sin levantarse a tocarlo.
        r7 = req("/api/screen-unlink", {"screen": "TV-Escaparate"}, tok=TOKEN)
        check(r7.get("ok"), "se puede desenlazar una pantalla")

        cont = json.load(open(cpath))["screens"].get("TV-Escaparate", {})
        check(len(cont.get("playlist", [])) == 1,
              "desenlazar NO borra la playlist")
        check(cont.get("rotation") == 90, "ni la rotacion")
        scr = json.load(open(os.path.join(datos, "screens.json")))
        check("TV-Escaparate" in scr, "y la pantalla sigue en el registro")

        try:
            req("/api/screen-unlink", {"screen": "Fantasma"}, tok=TOKEN)
            check(False, "desenlazar una inexistente deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "desenlazar una pantalla inexistente da error")

        try:
            req("/api/screen-unlink", {"screen": "TV-Escaparate"})
            check(False, "desenlazar sin autenticacion deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 401, "desenlazar exige autenticacion")
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python tests/test_emparejamiento.py`
Expected: FALLA en `se puede desenlazar una pantalla` (404 o excepción: el endpoint no existe).

- [ ] **Step 3: Añadir `notify_unlink` a `server.py`**

Justo después de `notify_deleted` (línea 388), antes de `def load_json`:

```python
def notify_unlink(screen_id):
    """Le dice a la pantalla que olvide quién era, sin borrar su configuración.

    Es lo contrario de notify_deleted: allí la pantalla desaparece; aquí sigue
    existiendo con su playlist, su horario y su rotación, y lo único que se
    suelta es el dispositivo. Sirve para reenlazar un televisor desde el panel
    sin ir a tocarlo con el mando.
    """
    with sse_lock:
        for wfile in list(sse_clients.get(screen_id, [])):
            try:
                wfile.write(f"data: unlink:{screen_id}\n\n".encode())
                wfile.flush()
            except: pass
```

- [ ] **Step 4: Añadir el endpoint a `server.py`**

Después del bloque `/api/screens/delete` (termina en la línea 1008 con `return`), insertar:

```python
        # ── Soltar el dispositivo de una pantalla, sin borrar la pantalla
        if path == "/api/screen-unlink":
            try:
                d = json.loads(body or "{}")
                sid = str(d.get("screen", "")).strip()
                screens = load_json(SCREENS_FILE)
                content = load_json(CONTENT_FILE)
                if not sid or (sid not in screens and sid not in content.get("screens", {})):
                    jresp(400, {"ok": False, "error": "Esa pantalla no existe"}); return
                notify_unlink(sid)
                with sse_lock:
                    sse_clients.pop(sid, None)
                if sid in screens:
                    screens[sid]["connected"] = False
                    save_json(SCREENS_FILE, screens)
                log(f"  [enlace] '{sid}' desenlazada: su dispositivo volvera a pedir codigo")
                ok({"screen": sid})
            except Exception as e: err(e)
            return
```

Comprobación importante: este bloque tiene que quedar **después** de la línea `if path != "/api/pair" and not self.require_auth():` (línea 886). El test de 401 lo verifica.

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `python tests/test_emparejamiento.py`
Expected: `TODO OK`.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_emparejamiento.py
git commit -m "feat: desenlazar una pantalla sin perder su configuracion"
```

---

### Task 6: El player usa la identidad compartida y entiende `unlink`

**Files:**
- Modify: `player.html:142-147` (lectura de identidad), `player.html:293` (mensaje SSE)

**Interfaces:**
- Consumes: `leerIdentidad()`, `guardarIdentidad()`, `olvidarIdentidad()` de la tarea 1; el mensaje SSE `unlink:<sid>` de la tarea 5
- Produces: nada

- [ ] **Step 1: Cambiar la lectura de identidad**

Sustituir las líneas 142-147 de `player.html`:

```js
// Identidad de la pantalla: URL (?screen=) → memoria del dispositivo → si no hay, emparejar.
const _sidParam=params.get("screen");
let _sidStored=null; try{ _sidStored=localStorage.getItem("signalos_screen_id"); }catch(e){}
const SCREEN_ID=_sidParam||_sidStored;
if(!SCREEN_ID && !PREVIEW){ location.replace("/pair"); }   // en previa no hay ?screen=
else if(_sidParam){ try{ localStorage.setItem("signalos_screen_id", _sidParam); }catch(e){} }  // recordar por dispositivo
```

por:

```js
// Identidad de la pantalla: URL (?screen=) → memoria del dispositivo → si no hay, emparejar.
// La URL manda sobre la memoria a propósito: es el remedio para los televisores
// que borran todo al apagarse. Se pega el enlace directo como página de inicio
// y la identidad viaja donde ningún borrado la alcanza.
const _sidParam=params.get("screen");
const SCREEN_ID=_sidParam||leerIdentidad();
if(!SCREEN_ID && !PREVIEW){ location.replace("/pair"); }   // en previa no hay ?screen=
else if(_sidParam){ guardarIdentidad(_sidParam); }         // recordar por dispositivo
```

- [ ] **Step 2: Tratar el mensaje `unlink`**

Sustituir la línea 293 de `player.html`:

```js
    if(e.data.indexOf("deleted")===0){ es.close(); try{localStorage.removeItem("signalos_screen_id");}catch(e2){} location.href="/pair"; return; }
```

por:

```js
    // «deleted» = la pantalla ya no existe. «unlink» = existe pero este
    // dispositivo se suelta de ella para poder reenlazarlo. Para el televisor
    // la reacción es la misma: olvidar quién era y volver a pedir código.
    if(e.data.indexOf("deleted")===0 || e.data.indexOf("unlink")===0){
      es.close();
      // El destino se calcula ANTES de olvidar: si no, el nombre ya no está
      // para mandarlo como pista y el panel no podría sugerir el reenlace.
      // Y el ?nuevo=1 es imprescindible: sin él, /pair podría leer una
      // identidad a medio borrar y devolver el televisor al player.
      const destino="/pair?nuevo=1&era="+encodeURIComponent(SCREEN_ID||"");
      olvidarIdentidad();
      location.href=destino;
      return;
    }
```

- [ ] **Step 3: Ejecutar todos los tests**

Run: `npm test`
Expected: los tests de `player-offline.test.js` siguen pasando. Ojo: su arnés corta el archivo entre `const OFFLINE_AFTER_MS` y `function getDayName()`, y el bloque de identidad va **antes** de ese tramo, así que no lo afecta. Si fallara con `leerIdentidad is not defined`, es que el bloque se insertó en el sitio equivocado.

- [ ] **Step 4: Commit**

```bash
git add player.html
git commit -m "feat: el player olvida su identidad al desenlazarse"
```

---

### Task 7: El panel ofrece reenlazar

**Files:**
- Modify: `admin.html:2578-2635` (`loadPairPending` y `claimPairing`)

**Interfaces:**
- Consumes: `known_as` de `pair-pending` (tarea 3); `modo` de `pair-claim` (tarea 4); los globales `regScreens` y `content` que ya existen en el panel
- Produces: `claimPairing(code, nombre, modo, cont)` — cambia la firma respecto a la actual de tres argumentos

- [ ] **Step 1: Sustituir `loadPairPending`**

Sustituir el cuerpo desde `const firma=...` hasta el cierre de la función (líneas 2598-2619) por:

```js
  // Se repinta solo si cambian los codigos o las pistas, para no borrar lo que
  // se esta escribiendo en el campo de nombre mientras se sondea cada 3 s.
  const firma=pend.map(p=>p.code+":"+(p.known_as||"")).join(",");
  if(cont.dataset.firma===firma) return;
  cont.dataset.firma=firma;

  // Pantallas que ya existen, para poder reenlazar en vez de crear otra.
  const existentes=[...new Set([...Object.keys(regScreens||{}),
                                ...Object.keys((content&&content.screens)||{})])]
                     .filter(n=>n!=="admin").sort();

  cont.innerHTML="";
  pend.forEach(p=>{
    // Si el televisor recordaba su nombre y esa pantalla sigue existiendo, se
    // deja el reenlace ya elegido: un clic y a correr.
    const sugerida=(p.known_as && existentes.includes(p.known_as)) ? p.known_as : "";
    const opciones=['<option value="">— crear una pantalla nueva —</option>']
      .concat(existentes.map(n=>'<option value="'+n+'"'+(n===sugerida?' selected':'')+
                               '>reenlazar a: '+n+'</option>')).join("");
    const pista=sugerida
      ? '<div style="font-size:11px;color:var(--accent);width:100%">'+
        '<i class="fa-solid fa-rotate-left"></i> dice que era «'+sugerida+'»</div>'
      : '';

    const el=document.createElement("div");
    el.style.cssText="display:flex;align-items:center;gap:12px;background:var(--s2);"+
      "border:1px solid var(--b);border-radius:var(--r);padding:12px 14px;margin-bottom:8px;flex-wrap:wrap";
    el.innerHTML='<div style="font-family:monospace;font-size:30px;font-weight:700;'+
      'color:var(--accent);letter-spacing:4px;min-width:120px">'+p.code+'</div>'+
      '<input class="finput" placeholder="Nombre: caja-1, escaparate..." '+
      'style="flex:1;min-width:180px"'+(sugerida?' disabled':'')+'>'+
      '<select class="finput" style="flex:1;min-width:180px">'+opciones+'</select>'+
      '<button class="btn btn-accent"><i class="fa-solid fa-link"></i> Enlazar</button>'+
      pista+
      '<div style="font-size:11px;color:var(--muted);width:100%">esperando desde hace '+
      p.waiting_for+' s</div>';

    const inp=el.querySelector("input"), sel=el.querySelector("select"),
          btn=el.querySelector("button");
    // El desplegable y el campo de texto son excluyentes: o reenlazas a una que
    // existe, o creas una nueva. Dejar los dos activos invita a equivocarse.
    sel.addEventListener("change",()=>{
      inp.disabled=!!sel.value;
      if(sel.value) inp.value="";
    });
    const enlazar=()=> sel.value
      ? claimPairing(p.code, sel.value, "reenlazar", cont)
      : claimPairing(p.code, inp.value, "nueva", cont);
    btn.addEventListener("click", enlazar);
    inp.addEventListener("keydown", e=>{ if(e.key==="Enter") enlazar(); });
    cont.appendChild(el);
  });
}
```

- [ ] **Step 2: Sustituir `claimPairing`**

Sustituir la función completa (líneas 2621-2635) por:

```js
async function claimPairing(code, nombre, modo, cont){
  nombre=(nombre||"").trim();
  if(!nombre){ toast("Ponle un nombre a la pantalla o elige una existente",true); return; }
  // Dos televisores con el mismo tablero es un uso legitimo, pero casi nunca es
  // lo que se pretende: mas vale avisar antes que dejar una pantalla huerfana.
  if(modo==="reenlazar" && (regScreens[nombre]||{}).connected){
    if(!confirm("«"+nombre+"» está conectada ahora mismo.\n\n"+
                "Si continúas quedarán dos dispositivos mostrando lo mismo.\n\n¿Seguir?")) return;
  }
  try{
    const r=await fetch("/api/pair-claim",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({code, screen_name:nombre, modo:modo||"nueva"})});
    const d=await r.json();
    if(!d.ok){ toast(d.error||"No se pudo enlazar",true); return; }
    toast(modo==="reenlazar" ? "«"+nombre+"» recupera su pantalla ✓"
                             : "Pantalla «"+nombre+"» enlazada ✓");
    if(cont) cont.dataset.firma="";        // forzar repintado
    await loadPairPending();
    await loadScreens();
  }catch(e){ toast("Error al enlazar",true); }
}
```

- [ ] **Step 3: Comprobar a mano en el navegador**

1. Arrancar el servidor: `python server.py --port 9000`
2. Abrir `http://localhost:9000/admin.html` y `http://localhost:9000/pair` en otra pestaña.
3. En el panel, sección **Pantallas**: aparece el código con el desplegable «— crear una pantalla nueva —».
4. Escribir un nombre nuevo y pulsar **Enlazar**. La pantalla debe redirigir al player.
5. Volver a `/pair?nuevo=1&era=<ese nombre>` en la otra pestaña. El código nuevo debe salir con la pista *«dice que era …»* y el desplegable ya seleccionado.
6. Un clic en **Enlazar**: debe salir el aviso de pantalla conectada y, al aceptar, reenlazar.

Expected: los seis pasos se comportan como se describe.

- [ ] **Step 4: Commit**

```bash
git add admin.html
git commit -m "feat: el panel permite reenlazar un codigo a una pantalla existente"
```

---

### Task 8: Botones de desenlazar y copiar enlace

**Files:**
- Modify: `admin.html:998-1004` (botonera de `renderScreens`)
- Modify: `admin.html` (dos funciones nuevas, junto a `deleteScreen`)

**Interfaces:**
- Consumes: `POST /api/screen-unlink` (tarea 5); el elemento `#url-<sid>` que ya rellena `renderScreens`
- Produces: `desenlazar(sid)`, `copiarEnlace(sid)`

- [ ] **Step 1: Añadir los botones**

En `admin.html`, dentro de `<div class="sc-actions">` (línea 998), añadir antes del botón de eliminar:

```html
          <button class="btn btn-ghost btn-sm" onclick="copiarEnlace('${sid}')" title="Copiar el enlace directo de esta pantalla"><i class="fa-solid fa-copy"></i></button>
          <button class="btn btn-a4 btn-sm" onclick="desenlazar('${sid}')" title="Soltar el televisor sin borrar la pantalla"><i class="fa-solid fa-link-slash"></i></button>
```

- [ ] **Step 2: Añadir las dos funciones**

En `admin.html`, justo antes de `function addScreenManual(){` (línea 1021):

```js
// Enlace directo: el remedio para los televisores que borran localStorage y las
// cookies al apagarse. Se pega como pagina de inicio y la identidad viaja en la
// URL, donde ningun borrado la alcanza.
async function copiarEnlace(sid){
  const el=document.getElementById("url-"+sid);
  const url=((el&&el.textContent)||"").trim();
  if(!url || url==="—"){ toast("Todavía no se ha calculado el enlace",true); return; }
  try{
    await navigator.clipboard.writeText(url);
    toast("Enlace copiado ✓");
  }catch(e){
    // navigator.clipboard solo existe en contexto seguro. Con el panel abierto
    // por localhost lo hay; si alguien entra por la IP de la red, no. En ese
    // caso al menos se deja el enlace a la vista para copiarlo a mano.
    prompt("Copia este enlace:", url);
  }
}

// Desenlazar NO es eliminar: la pantalla conserva playlist, horario y rotacion,
// y solo el televisor olvida quien era. Es la forma de reenlazar un televisor
// sin ir a tocarlo con el mando.
async function desenlazar(sid){
  if(!confirm("Soltar «"+sid+"» de su televisor.\n\n"+
              "La pantalla NO se borra: conserva su playlist, su horario y su rotación.\n"+
              "El televisor volverá a pedir un código para que lo reenlaces.\n\n¿Continuar?")) return;
  try{
    const r=await fetch("/api/screen-unlink",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({screen:sid})});
    const d=await r.json();
    if(!d.ok){ toast(d.error||"No se pudo desenlazar",true); return; }
    toast("«"+sid+"» desenlazada — pedirá un código nuevo");
    await loadPairPending();
    await loadScreens();
  }catch(e){ toast("Error al desenlazar",true); }
}
```

- [ ] **Step 3: Comprobar a mano en el navegador**

1. Con una pantalla enlazada y su player abierto en otra pestaña, pulsar **Desenlazar** en el panel.
2. La pestaña del player debe irse sola a `/pair?nuevo=1&era=<nombre>` y mostrar un código.
3. El código debe aparecer en el panel con la pista *«dice que era …»*.
4. Reenlazarlo de un clic: la pantalla vuelve al player **con su playlist intacta**.
5. Pulsar el botón de copiar: aparece el aviso «Enlace copiado ✓» y el portapapeles lleva `http://localhost:PUERTO/player.html?screen=…`.

Expected: los cinco pasos se comportan como se describe. Este es el recorrido completo del arreglo, de punta a punta.

- [ ] **Step 4: Commit**

```bash
git add admin.html
git commit -m "feat: botones de desenlazar y copiar enlace directo en el panel"
```

---

### Task 9: Verificación completa y compilación del instalador

**Files:**
- Modify: ninguno salvo que la verificación destape algo
- Verifica: todas las suites y el `.exe`

- [ ] **Step 1: Toda la batería de Node**

Run: `npm test`
Expected: 92 tests anteriores + 8 de identidad + 7 de reanudación, todos en verde.

- [ ] **Step 2: Las tres suites de Python**

Run:
```bash
python tests/test_data_dir.py
python tests/test_fx_update.py
python tests/test_emparejamiento.py
```
Expected: `TODO OK` en las tres.

- [ ] **Step 3: El bucle que hay que descartar a mano**

Ninguna prueba automática cubre esto y es el fallo más peligroso del diseño: si `olvidarIdentidad()` dejara la cookie puesta, una pantalla borrada rebotaría entre `/pair` y el player para siempre.

1. Arrancar el servidor y enlazar una pantalla llamada `Prueba-Bucle`.
2. Con el player abierto, **eliminar** esa pantalla desde el panel (el botón de la papelera, no el de desenlazar).
3. La pestaña del player debe ir a `/pair`, mostrar **un código** y quedarse quieta.

Expected: un código estable. Si en su lugar la página parpadea o va y viene entre `/pair` y el player, `olvidarIdentidad()` no está limpiando los dos almacenes.

- [ ] **Step 4: Comprobar que la cookie sobrevive de verdad**

1. Con una pantalla enlazada y el player abierto, F12 → Application → Local Storage → borrar `signalos_screen_id` (solo esa clave, dejando la cookie).
2. Recargar con F5.

Expected: el player sigue mostrando su contenido; ha recuperado la identidad de la cookie. Es exactamente el caso del televisor que limpia localStorage al apagarse.

- [ ] **Step 5: Compilar el instalador**

Run:
```bash
"C:\Users\axeld\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer/setup.iss
```
Expected: `InTeks_Display_Setup_v1.0.0.exe` generado **sin ningún aviso**.

- [ ] **Step 6: Commit final**

```bash
git add -A
git commit -m "test: verificacion completa de la recuperacion del enlace"
```

---

## Notas para quien implemente

**El orden de las tareas importa.** La 1 produce las funciones que usan la 2 y la 6; la 3, 4 y 5 son independientes entre sí pero la 7 y la 8 dependen de las tres. No adelantes la 7 antes de tener la 3 y la 4 o el panel llamará a endpoints que aún no entienden `modo` ni devuelven `known_as`.

**El fallo que más fácil se cuela** es el del orden de operaciones: calcular el destino con el nombre **antes** de llamar a `olvidarIdentidad()`. Aparece en la tarea 2 (botón «Enlazar de nuevo») y en la tarea 6 (mensaje SSE). Si se invierte, el panel nunca muestra la pista «dice que era…» y el síntoma —una sugerencia que no sale— no apunta a la causa.

**No renombres nada.** `signalos_screen_id` es la clave que tienen guardada todas las pantallas ya instaladas; cambiarla las desenlazaría a todas de golpe.
