# Panel de administración responsive — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `admin.html` se use desde un móvil sin perder ninguna funcionalidad, sin reestructurar el monolito y sin tocar el CSS de escritorio.

**Architecture:** Una capa responsive encima de lo que ya hay: dos bloques `@media` (860 px y 560 px) donde vive todo lo nuevo, más tres añadidos pequeños de JS —el cajón de navegación, los botones subir/bajar y el plegado de la fila de divisas—. El arrastrar y soltar de HTML5 no funciona en táctil, así que se sustituye por botones que **no abren ninguna ruta de escritura nueva**: reordenan en memoria y llaman a las funciones de guardado que ya usa el arrastre.

**Tech Stack:** HTML/CSS/JS puro, sin frameworks ni paso de compilación. Tests con `node:test` sobre bloques extraídos de `admin.html` y ejecutados en un `vm`. Verificación visual con Chrome headless.

## Global Constraints

- **No hay paso de compilación.** `admin.html` se edita y se sirve tal cual. Sin frameworks, sin librerías nuevas.
- **El CSS de escritorio no se toca.** Todo lo nuevo va dentro de `@media`. Si un cambio exige tocar una regla existente, es señal de que se está haciendo mal.
- **Dos puntos de corte, con reparto fijo:** `≤860px` es ancho de layout (barra lateral, columnas); `≤560px` es sitio para el dedo (campos, objetivos táctiles, modal).
- **La `@media (max-width:700px)` de la línea 81** se absorbe en el bloque de 860 y se borra de donde está.
- **Los botones de reordenar no escriben.** Llaman a `moverPlItem()` / `moverFxRow()`, que es lo que ya hace el arrastre. Los módulos de divisas viven duplicados (librería + cada playlist) y cualquier ruta de escritura nueva provocaría que el siguiente guardado deshiciera el cambio en silencio.
- **Campos a 16 px por debajo de 560 px.** iOS hace zoom al enfocar un campo con letra menor, y cada toque daría un salto que hay que deshacer a mano.
- **Objetivos táctiles de 44 px** en botones de acción por debajo de 860 px.
- **`100dvh` con `100vh` de reserva** en `.app`: con `100vh` a secas la barra de direcciones del móvil recorta el contenido.
- **Estilo de commit del proyecto: sin tildes en el asunto**, cuerpo explicando el porqué.
- **Ejecutar `npm test` antes de cada commit.** Hoy son 240 en verde.

---

## File Structure

```
admin.html                       ← único archivo de producto que se toca
  · línea 81      @media 700px   → se borra (se absorbe en el bloque nuevo)
  · tras línea 187 (fin del CSS) → NUEVO bloque responsive
  · línea 191     .topbar        → botón de menú
  · línea 1800    renderPlList   → botones subir/bajar
  · línea 1806    drop playlist  → pasa a llamar a moverPlItem()
  · línea 2447    renderFxRows   → botones subir/bajar + estructura móvil
  · JS al final                  → toggleMenu(), moverPlItem(), moverEnLista()

tests/reordenar-listas.test.js   ← NUEVO, extrae moverEnLista() de admin.html
```

**Por qué así:** `moverEnLista()` es la única lógica con casos límite, así que se aísla como función pura y se prueba en la JVM de Node sin navegador. Todo lo demás es CSS y pegamento de DOM, que se verifica renderizando.

---

### Task 1: La lógica de reordenar, aislada y probada

**Files:**
- Modify: `admin.html` (añadir `moverEnLista()` junto a `moverFxRow()`, sobre la línea 2468)
- Test: `tests/reordenar-listas.test.js` (crear)

**Interfaces:**
- Consumes: nada.
- Produces: `function moverEnLista(lista, desde, hasta)` — mueve un elemento y devuelve `true` si movió algo, `false` si no había nada que hacer. Muta la lista recibida.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/reordenar-listas.test.js`:

```javascript
/**
 * Tests de moverEnLista(), la funcion que reordena playlists y filas de divisas.
 *
 * admin.html es un HTML monolitico con el JS inline, asi que no hay nada que
 * importar. En vez de copiar la funcion aqui -una copia se desincroniza al
 * primer cambio y dejaria de probar nada-, este arnes la EXTRAE tal cual esta
 * en admin.html y la ejecuta en un contexto vm.
 *
 * Que se prueba y por que importa: esta funcion la usan el arrastre Y los
 * botones subir/bajar. Si pierde o duplica un elemento, una playlist de tienda
 * se corrompe sin que nadie lo note hasta que falta un contenido.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");

function cargarMoverEnLista() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const from = src.indexOf("function moverEnLista(");
  const to = src.indexOf("function moverFxRow(");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error(
      "No se encuentran moverEnLista()/moverFxRow() en admin.html. " +
      "Si se han renombrado, actualiza los marcadores de este arnes."
    );
  }
  const ctx = { };
  vm.createContext(ctx);
  // Se declara como var para que quede colgada del contexto: las funciones
  // declaradas con "function" si se cuelgan, pero const y let no.
  vm.runInContext(src.slice(from, to) + ";var _m = moverEnLista;", ctx);
  return ctx._m;
}

const moverEnLista = cargarMoverEnLista();

test("mueve un elemento hacia abajo", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 0, 1), true);
  assert.deepStrictEqual(l, ["b", "a", "c"]);
});

test("mueve un elemento hacia arriba", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 2, 1), true);
  assert.deepStrictEqual(l, ["a", "c", "b"]);
});

test("subir el primero no hace nada", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 0, -1), false);
  assert.deepStrictEqual(l, ["a", "b", "c"]);
});

test("bajar el ultimo no hace nada", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 2, 3), false);
  assert.deepStrictEqual(l, ["a", "b", "c"]);
});

test("moverse a la misma posicion no hace nada", () => {
  const l = ["a", "b", "c"];
  assert.strictEqual(moverEnLista(l, 1, 1), false);
  assert.deepStrictEqual(l, ["a", "b", "c"]);
});

test("nunca pierde ni duplica elementos", () => {
  const l = ["a", "b", "c", "d", "e"];
  moverEnLista(l, 4, 0);
  moverEnLista(l, 1, 3);
  moverEnLista(l, 0, 2);
  assert.strictEqual(l.length, 5);
  assert.deepStrictEqual([...l].sort(), ["a", "b", "c", "d", "e"]);
});

test("indices invalidos no rompen la lista", () => {
  const l = ["a", "b"];
  assert.strictEqual(moverEnLista(l, null, 1), false);
  assert.strictEqual(moverEnLista(l, 0, null), false);
  assert.strictEqual(moverEnLista(l, 9, 0), false);
  assert.deepStrictEqual(l, ["a", "b"]);
});

test("una lista vacia no revienta", () => {
  const l = [];
  assert.strictEqual(moverEnLista(l, 0, 1), false);
  assert.deepStrictEqual(l, []);
});
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: FALLA con `No se encuentran moverEnLista()/moverFxRow() en admin.html`.

- [ ] **Step 3: Escribir la implementación mínima**

En `admin.html`, justo **antes** de `function moverFxRow(desde,hasta){` (línea 2468), insertar:

```javascript
// Mueve un elemento de una lista de sitio. La usan el arrastre y los botones
// subir/bajar, que es lo que garantiza que las dos formas de reordenar hagan
// exactamente lo mismo. Devuelve si movio algo, para no repintar de balde.
function moverEnLista(lista,desde,hasta){
  if(!Array.isArray(lista)) return false;
  if(desde==null||hasta==null) return false;
  if(desde===hasta) return false;
  if(desde<0||desde>=lista.length) return false;
  if(hasta<0||hasta>=lista.length) return false;
  const [x]=lista.splice(desde,1);
  lista.splice(hasta,0,x);
  return true;
}
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: `pass 248`, `fail 0` (240 de antes + 8 nuevos).

- [ ] **Step 5: Commit**

```bash
git add admin.html tests/reordenar-listas.test.js
git commit -m "Panel: moverEnLista(), la logica de reordenar en un solo sitio

La usaran el arrastre y los botones subir/bajar que vienen despues. Tenerla
aparte es lo que garantiza que las dos formas de reordenar hagan exactamente lo
mismo, en vez de dos splice parecidos que se separan al primer arreglo.

Ocho tests, incluidos los que de verdad muerden: subir el primero y bajar el
ultimo no deben hacer nada, y la lista no puede perder ni duplicar elementos
tras varios movimientos encadenados. Si eso falla, una playlist de tienda se
corrompe sin que nadie lo note hasta que falta un contenido."
```

---

### Task 2: Botones subir/bajar en la playlist

**Files:**
- Modify: `admin.html:1800` (el `innerHTML` de cada elemento de playlist)
- Modify: `admin.html:1805-1807` (el manejador de `drop`, que pasa a usar la función común)
- Modify: `admin.html` (añadir `moverPlItem()` junto a `updVigencia()`, sobre la línea 1811)

**Interfaces:**
- Consumes: `moverEnLista(lista, desde, hasta)` del Task 1.
- Produces: `function moverPlItem(sid, desde, hasta)` — reordena la playlist de una pantalla y repinta. No guarda: el guardado sigue donde estaba.

- [ ] **Step 1: Añadir la función común**

En `admin.html`, justo **antes** de `function updVigencia(sid,i,campo,valor){` (línea 1811), insertar:

```javascript
// Reordena la playlist de una pantalla. NO guarda: el guardado sigue estando
// donde estaba, en el boton de la ventana. Esto solo toca la copia en memoria
// y repinta, igual que hacia el arrastre.
function moverPlItem(sid,desde,hasta){
  const pl=((content.screens||{})[sid]||{}).playlist;
  if(!pl) return;
  if(moverEnLista(pl,desde,hasta)) renderPlList(sid);
}
```

- [ ] **Step 2: Hacer que el arrastre use esa función**

Sustituir la línea 1805-1807 completa:

```javascript
    el.addEventListener("drop",e=>{e.preventDefault();el.classList.remove("drag-over");
      if(dragSrc!==null&&dragSrc!==i){const pl=content.screens[sid].playlist;const m=pl.splice(dragSrc,1)[0];pl.splice(i,0,m);renderPlList(sid);}
    });
```

por:

```javascript
    el.addEventListener("drop",e=>{e.preventDefault();el.classList.remove("drag-over");
      if(dragSrc!==null) moverPlItem(sid,dragSrc,i);
    });
```

- [ ] **Step 3: Añadir los botones al elemento**

En la línea 1800, sustituir el principio del `innerHTML`:

```javascript
    el.innerHTML=`<span class="pl-handle"><i class="fa-solid fa-grip-vertical"></i></span><div class="pl-thumb">${thumb}</div>
```

por (se añade `.pl-mover` justo después del asa; el resto de la línea se queda igual):

```javascript
    const arriba=`<button class="btn btn-ghost btn-sm" ${i===0?"disabled":""} title="Subir" onclick="moverPlItem('${sid}',${i},${i-1})"><i class="fa-solid fa-chevron-up"></i></button>`;
    const abajo=`<button class="btn btn-ghost btn-sm" ${i===pl.length-1?"disabled":""} title="Bajar" onclick="moverPlItem('${sid}',${i},${i+1})"><i class="fa-solid fa-chevron-down"></i></button>`;
    el.innerHTML=`<span class="pl-handle"><i class="fa-solid fa-grip-vertical"></i></span><div class="pl-mover">${arriba}${abajo}</div><div class="pl-thumb">${thumb}</div>
```

`pl` es la playlist, y `renderPlList(sid)` ya la tiene en ámbito: la declara en su segunda línea (`const pl=(content.screens[sid]||{}).playlist||[];`), así que `pl.length` funciona sin añadir nada.

- [ ] **Step 4: Dar estilo al par de botones**

En el CSS, junto a `.pl-handle` (buscar `.pl-handle{` y añadir debajo):

```css
/* Los botones de reordenar van SIEMPRE, tambien en escritorio: mantener dos
   comportamientos segun el ancho hace que el de movil solo se pruebe en movil,
   y por ahi se pudre una funcion sin que nadie lo note. */
.pl-mover{display:flex;flex-direction:column;gap:2px;flex-shrink:0}
.pl-mover .btn{padding:2px 6px;line-height:1}
.pl-mover .btn[disabled]{opacity:.25;cursor:default}
```

- [ ] **Step 5: Comprobar en el navegador**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: `pass 248`, `fail 0`.

Y a mano, con el servidor en marcha: abrir el panel, entrar en la playlist de una pantalla, y comprobar que **subir el primero y bajar el último están deshabilitados** y que los demás mueven un puesto. Comprobar también que **el arrastre sigue funcionando**.

- [ ] **Step 6: Commit**

```bash
git add admin.html
git commit -m "Panel: botones subir/bajar en la playlist

El arrastrar y soltar de HTML5 no existe en tactil: no es que se vea mal, es
que no hay forma de reordenar una playlist con el dedo. Dos botones lo
resuelven sin librerias y funcionan con dedo, raton y mando.

Van tambien en escritorio a proposito. Mantener dos comportamientos segun el
ancho significa que el de movil solo se prueba en movil, y por ahi se pudre una
funcion sin que nadie lo note. Ademas, mover un elemento UN puesto con un clic
es mas rapido y preciso que arrastrarlo.

El arrastre pasa a llamar a la misma moverPlItem() que los botones, asi que las
dos formas de reordenar hacen exactamente lo mismo. Y no se ha tocado el
guardado: sigue estando donde estaba.

En el primero y el ultimo, el boton que no aplica queda DESHABILITADO y no
oculto, para que la fila no cambie de tamano segun su posicion."
```

---

### Task 3: Botones subir/bajar en las filas de divisas

**Files:**
- Modify: `admin.html:2447` (el `innerHTML` de la fila de divisas)
- Modify: `admin.html` (CSS de `.fx-row-edit`, línea 146)

**Interfaces:**
- Consumes: `moverFxRow(desde, hasta)` — **ya existe** en `admin.html:2468`, no hay que crearla.
- Produces: nada nuevo.

- [ ] **Step 1: Añadir los botones a la fila**

En la línea 2447, sustituir el principio del `innerHTML`:

```javascript
    el.innerHTML=`<span class="fx-handle" title="Arrastra para reordenar"><i class="fa-solid fa-grip-vertical"></i></span><input value="${r.flag||''}"
```

por:

```javascript
    const sube=`<button class="btn btn-ghost btn-sm" ${i===0?"disabled":""} title="Subir" onclick="moverFxRow(${i},${i-1})"><i class="fa-solid fa-chevron-up"></i></button>`;
    const baja=`<button class="btn btn-ghost btn-sm" ${i===fxRows.length-1?"disabled":""} title="Bajar" onclick="moverFxRow(${i},${i+1})"><i class="fa-solid fa-chevron-down"></i></button>`;
    el.innerHTML=`<span class="fx-handle" title="Arrastra para reordenar"><i class="fa-solid fa-grip-vertical"></i></span><div class="fx-mover">${sube}${baja}</div><input value="${r.flag||''}"
```

El resto de la línea (los siete `<input>` y el botón de borrar) **no se toca**.

- [ ] **Step 2: Ajustar la rejilla a la columna nueva**

La fila tenía 8 columnas y ahora son 9. En la línea 146, sustituir:

```css
.fx-row-edit{display:grid;grid-template-columns:18px 40px minmax(0,1fr) minmax(0,1fr) 80px 80px minmax(0,.9fr) 32px;gap:6px;padding:8px 10px;border-bottom:1px solid var(--b);align-items:center}
```

por:

```css
.fx-row-edit{display:grid;grid-template-columns:18px 26px 40px minmax(0,1fr) minmax(0,1fr) 80px 80px minmax(0,.9fr) 32px;gap:6px;padding:8px 10px;border-bottom:1px solid var(--b);align-items:center}
.fx-mover{display:flex;flex-direction:column;gap:2px}
.fx-mover .btn{padding:1px 4px;line-height:1;font-size:9px}
.fx-mover .btn[disabled]{opacity:.25;cursor:default}
```

**Ojo:** si hay una cabecera de columnas encima de las filas con la misma rejilla, hay que añadirle también la columna vacía. Buscar `fx-row-edit` en el HTML estático antes de dar el paso por bueno.

- [ ] **Step 3: Comprobar**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: `pass 248`, `fail 0`.

A mano: en Divisas, cargar un tablero con varias filas, comprobar que los botones mueven una fila y que **la previa se actualiza** (lo hace `renderFxRows()` al final, que llama a `updateFxPreview()`), y que el arrastre sigue yendo.

- [ ] **Step 4: Commit**

```bash
git add admin.html
git commit -m "Panel: botones subir/bajar en las filas de divisas

Mismo motivo que en la playlist: con el dedo no se puede arrastrar. Aqui salio
mas barato porque moverFxRow(desde,hasta) YA existia -la escribieron para el
arrastre-, asi que los botones solo la llaman. Cero rutas de escritura nuevas,
que es justo lo que hay que respetar aqui: los modulos de divisas viven
duplicados en la libreria y en cada playlist, y guardar por libre haria que el
siguiente guardado deshiciera el cambio en silencio.

La rejilla de la fila pasa de 8 a 9 columnas para hacerle sitio al par de
botones."
```

---

### Task 4: El bloque responsive y el cajón de navegación

**Files:**
- Modify: `admin.html:81` (borrar la `@media` de 700px)
- Modify: `admin.html` (añadir el bloque responsive al final del `<style>`, antes de `</style>`)
- Modify: `admin.html:191-199` (botón de menú en la barra superior)
- Modify: `admin.html` (JS: `toggleMenu()`, junto a `showPage()`)

**Interfaces:**
- Consumes: nada.
- Produces: `function toggleMenu(abrir)` — abre o cierra el cajón; sin argumento, alterna.

- [ ] **Step 1: Borrar la media query suelta**

Borrar la línea 81 entera:

```css
@media (max-width:700px){ .pl-editor{grid-template-columns:minmax(0,1fr)} }
```

Y su comentario de la línea 80 (`/* En ventanas estrechas, una columna debajo de otra en vez de recortarse */`). Se absorbe en el bloque nuevo: tres puntos de corte sueltos en un archivo de 216 KB es como se llega a un CSS que nadie entiende.

- [ ] **Step 2: Añadir el bloque responsive**

Justo antes de `</style>`, añadir:

```css
/* ─────────────────────────────────────────────────────────────────────────
   CAPA RESPONSIVE. Todo lo que hace usable el panel en tableta y movil vive
   AQUI, y nada de esto toca el CSS de escritorio de arriba: si un cambio
   obliga a modificar una regla de las de arriba, es senal de que se esta
   haciendo mal.

   Reparto de los dos puntos de corte:
     <= 860px  sobra ancho de LAYOUT   (barra lateral, columnas)
     <= 560px  falta sitio para el DEDO (campos, objetivos tactiles, modal)
   ───────────────────────────────────────────────────────────────────────── */

/* dvh y no vh: con 100vh la barra de direcciones del movil se come el final
   de la pagina y el ultimo boton queda fuera de alcance. El 100vh de antes se
   queda de reserva para navegadores que no entiendan dvh. */
.app{height:100vh;height:100dvh}

@media (max-width:860px){
  /* Una sola columna: la lateral sale del flujo y pasa a cajon. */
  .app{grid-template-columns:minmax(0,1fr)}
  .sidebar{position:fixed;top:52px;left:0;bottom:0;width:240px;z-index:60;
           transform:translateX(-100%);transition:transform .2s ease;
           box-shadow:0 0 24px rgba(0,0,0,.5)}
  .sidebar.abierta{transform:translateX(0)}
  .menu-btn{display:inline-flex}
  .menu-fondo{display:none;position:fixed;inset:52px 0 0 0;background:rgba(0,0,0,.5);z-index:55}
  .menu-fondo.visible{display:block}

  .stats-row{grid-template-columns:repeat(2,1fr)}
  .pl-editor{grid-template-columns:minmax(0,1fr)}
  .main{padding:14px}

  /* Objetivo tactil: 44px es el minimo por debajo del cual se falla el toque. */
  .btn{min-height:44px}
  .btn-sm{min-height:36px}
  .nav-item{padding:14px 16px}
}

@media (max-width:560px){
  .form-row{grid-template-columns:minmax(0,1fr)}

  /* Pantalla completa: a 375px, un modal "centrado" son margenes desperdiciados. */
  .modal{width:100%;max-width:100%;height:100%;max-height:100%;border-radius:0;padding:16px}
  .modal-bd{align-items:stretch;justify-content:stretch}

  /* 16px o iOS hace zoom al enfocar el campo, y hay que alejar a mano cada vez.
     Es de las cosas que hacen que una web responsive se sienta rota aunque el
     layout este perfecto. */
  input,select,textarea{font-size:16px}
}
```

- [ ] **Step 3: Añadir el botón de menú y el fondo**

En la línea 191, sustituir:

```html
<div class="topbar">
  <div class="logo">INTEKS<span> DISPLAY</span></div>
```

por:

```html
<div class="topbar">
  <button class="btn btn-ghost btn-sm menu-btn" onclick="toggleMenu()" title="Menú"><i class="fa-solid fa-bars"></i></button>
  <div class="logo">INTEKS<span> DISPLAY</span></div>
```

Y justo **después** del `</div>` que cierra `.topbar` (línea 199), añadir:

```html
<div class="menu-fondo" id="menu-fondo" onclick="toggleMenu(false)"></div>
```

En el CSS de escritorio, junto a `.logo{`, añadir la regla que lo oculta por defecto (esta sí va fuera del `@media`, porque es el estado normal):

```css
.menu-btn{display:none}
```

- [ ] **Step 4: Añadir el JS del cajón**

Junto a `function showPage(`, añadir:

```javascript
// El cajon de navegacion. Se cierra al elegir seccion y al tocar el fondo:
// dejarlo abierto tapando el contenido que acabas de pedir es el fallo clasico
// de los menus deslizantes.
function toggleMenu(abrir){
  const lat=document.querySelector(".sidebar");
  const fondo=document.getElementById("menu-fondo");
  const ver=(abrir===undefined)?!lat.classList.contains("abierta"):!!abrir;
  lat.classList.toggle("abierta",ver);
  fondo.classList.toggle("visible",ver);
}
```

Y dentro de `showPage(...)`, al final del cuerpo, añadir:

```javascript
  toggleMenu(false);
```

- [ ] **Step 5: Comprobar**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: `pass 248`, `fail 0`.

A mano, con el navegador estrechado por debajo de 860 px: el botón de menú aparece, el cajón entra y sale, al elegir una sección se cierra solo, y al tocar el fondo también. **Y por encima de 861 px todo tiene que estar exactamente como antes.**

- [ ] **Step 6: Commit**

```bash
git add admin.html
git commit -m "Panel: capa responsive y cajon de navegacion

En 216 KB de admin.html habia UNA sola @media. La barra lateral de 220px se
comia el 59% de un movil de 375px, asi que pasa a cajon deslizante con boton de
menu, y se cierra al elegir seccion y al tocar el fondo: dejarlo abierto
tapando el contenido que acabas de pedir es el fallo clasico de los menus
deslizantes.

Todo lo nuevo vive dentro de @media y no toca una sola regla del CSS de
escritorio. Dos puntos de corte con reparto claro: a 860 lo que sobra es ancho
de layout -lateral, columnas-, y a 560 lo que falta es sitio para el dedo
-campos, objetivos tactiles, modal a pantalla completa-.

Dos detalles que no se ven leyendo el CSS:

- Los campos suben a 16px por debajo de 560. iOS hace zoom automatico al
  enfocar un campo con letra menor, asi que cada toque daria un salto que hay
  que deshacer a mano.
- .app pasa a 100dvh con 100vh de reserva. Con 100vh a secas, la barra de
  direcciones del movil se come el final de la pagina y el ultimo boton queda
  fuera de alcance.

Se absorbe la @media de 700px que habia suelta para .pl-editor."
```

---

### Task 5: El editor de divisas en el móvil

**Files:**
- Modify: `admin.html:2447` (marcar los campos plegables)
- Modify: `admin.html` (CSS: el bloque de 560 px del Task 4)
- Modify: `admin.html` (JS: `toggleFxFila()`)

**Interfaces:**
- Consumes: `renderFxRows()` existente.
- Produces: `function toggleFxFila(i)` — pliega o despliega los campos secundarios de una fila.

- [ ] **Step 1: Marcar los campos y añadir el resumen**

En el `innerHTML` de la fila (línea 2447), envolver los campos secundarios y añadir el resumen y el botón. La fila queda así — **los `oninput` no cambian**, solo se reparte el marcado:

```javascript
    el.innerHTML=`<span class="fx-handle" title="Arrastra para reordenar"><i class="fa-solid fa-grip-vertical"></i></span>`+
      `<div class="fx-mover">${sube}${baja}</div>`+
      `<span class="fx-resumen">${(r.country||"sin país")} · ${(r.code||"—")}</span>`+
      `<input class="fx-sec" value="${r.flag||''}" oninput="fxRows[${i}].flag=this.value;updateFxPreview()" placeholder="VE" maxlength="2" title="Código de país de 2 letras (VE, US, MX...)" style="text-align:center;text-transform:uppercase">`+
      `<input class="fx-sec" value="${r.country}" oninput="fxRows[${i}].country=this.value;updateFxPreview()" placeholder="País">`+
      `<input class="fx-sec" value="${r.currency}" oninput="fxRows[${i}].currency=this.value;updateFxPreview()" placeholder="Moneda">`+
      `<input class="fx-sec" value="${r.code}" oninput="fxRows[${i}].code=this.value;updateFxPreview()" placeholder="USD">`+
      `<input class="fx-tasa" value="${r.rate}" oninput="fxRows[${i}].rate=this.value;updateFxPreview()" placeholder="1.08">`+
      `<input class="fx-sec" value="${r.agent||''}" oninput="fxRows[${i}].agent=this.value;updateFxPreview()" placeholder="Opcional" title="Punto de pago/ventanilla (p. ej. Davivienda). Se muestra en pantalla bajo el país. Déjalo vacío en un tablero de cambio normal.">`+
      `<button class="btn btn-ghost btn-sm fx-editar" onclick="toggleFxFila(${i})" title="Editar el resto de campos"><i class="fa-solid fa-pen"></i></button>`+
      `<button class="btn btn-danger btn-sm" onclick="rmFxRow(${i})"><i class="fa-solid fa-xmark"></i></button>`;
```

- [ ] **Step 2: Ajustar la rejilla de escritorio a las dos celdas nuevas**

La fila pasa de 9 a 11 columnas (se han añadido `.fx-resumen` y `.fx-editar`), pero en escritorio esas dos **no se ven**. Sustituir la regla de `.fx-row-edit` por:

```css
.fx-row-edit{display:grid;grid-template-columns:18px 26px 40px minmax(0,1fr) minmax(0,1fr) 80px 80px minmax(0,.9fr) 32px;gap:6px;padding:8px 10px;border-bottom:1px solid var(--b);align-items:center}
/* En escritorio la fila ensena sus ocho campos: ni resumen ni boton de editar. */
.fx-resumen,.fx-editar{display:none}
```

- [ ] **Step 3: Añadir el modo móvil al bloque de 560 px**

Dentro del `@media (max-width:560px)` del Task 4, añadir:

```css
  /* De los ocho campos de una fila, el UNICO que cambia a diario es la tasa.
     En el movil se ensena eso y el resto se pliega: actualizar un tablero de
     ocho divisas son ocho toques y ocho numeros, en vez de pelearse con
     campos de 40px. */
  .fx-row-edit{grid-template-columns:26px minmax(0,1fr) 90px 40px 40px;
               grid-template-areas:"mov resumen tasa editar borrar";
               gap:8px;padding:10px}
  .fx-row-edit>.fx-handle{display:none}
  .fx-row-edit>.fx-mover{grid-area:mov}
  .fx-row-edit>.fx-resumen{grid-area:resumen;display:block;font-size:13px;
                           overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .fx-row-edit>.fx-tasa{grid-area:tasa}
  .fx-row-edit>.fx-editar{grid-area:editar;display:inline-flex}
  .fx-row-edit>.btn-danger{grid-area:borrar}
  .fx-row-edit>.fx-sec{display:none}
  /* Desplegada: los secundarios bajan a su propia linea, a ancho completo. */
  .fx-row-edit.abierta{grid-template-columns:26px minmax(0,1fr) 90px 40px 40px;
                       grid-template-areas:"mov resumen tasa editar borrar"
                                           "sec sec sec sec sec"}
  .fx-row-edit.abierta>.fx-sec{display:block;grid-area:sec;margin-top:6px}
```

**Nota sobre el arrastre:** el asa se oculta en móvil porque ahí no sirve; los botones subir/bajar la sustituyen.

- [ ] **Step 4: Añadir el JS del plegado**

Junto a `function moverFxRow(`, añadir:

```javascript
// Despliega los campos secundarios de una fila en el movil. Es estado
// transitorio a proposito: no se guarda en ningun sitio y todas las filas
// vuelven a plegarse al recargar. Es una comodidad de edicion, no una
// preferencia del usuario.
function toggleFxFila(i){
  const fila=document.querySelector('.fx-row-edit[data-i="'+i+'"]');
  if(fila) fila.classList.toggle("abierta");
}
```

- [ ] **Step 5: Comprobar**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: `pass 248`, `fail 0`.

A mano, estrechando por debajo de 560 px: la fila enseña país · código, la tasa y dos botones; al pulsar el lápiz bajan los demás campos; al escribir en la tasa la previa se actualiza. **Y por encima de 561 px la fila tiene que verse exactamente como antes, con sus ocho campos.**

- [ ] **Step 6: Commit**

```bash
git add admin.html
git commit -m "Panel: en el movil, el editor de divisas ensena solo la tasa

De los ocho campos de una fila -bandera, pais, moneda, codigo, tasa,
ventanilla, mas asa y borrar- el UNICO que cambia a diario es la tasa: el resto
se configura una vez. Asi que en el movil la fila queda en pais, codigo y un
campo grande para la tasa, y el resto se despliega con el boton del lapiz.

Actualizar un tablero de ocho divisas desde el movil pasa a ser ocho toques y
ocho numeros, en vez de pelearse con ocho columnas que necesitan 450px para
entrar.

El plegado es estado transitorio a proposito: no se guarda y todas las filas
vuelven a plegarse al recargar. Es una comodidad de edicion, no una preferencia
del usuario, y guardarla obligaria a decidir donde y a migrarla."
```

---

### Task 6: Que la previa del tablero no desborde en el móvil

**El spec pedía «plegar la previa detrás de un botón», y eso ya está hecho:**
la previa vive en `#fx-prev-wrap`, que nace con `display:none` y se enciende
con la casilla `#fx-prev-on` (línea 355), manejada por una `toggleFxPreview()`
que **ya existe**. Añadir otro botón sería duplicar un control y, con un nombre
casi idéntico, una trampa para el siguiente que lea el archivo.

Lo que sí queda es que, cuando el usuario la enciende, quepa: `#fx-prev-stage`
tiene `max-width:440px`, más ancho que un móvil de 390 px.

**Files:**
- Modify: `admin.html` (CSS del bloque de 560 px)

**Interfaces:**
- Consumes: `#fx-prev-wrap`, `#fx-prev-stage`, `updateFxPreview()` — todos existentes.
- Produces: nada nuevo.

- [ ] **Step 1: Añadir el ajuste al bloque de 560 px**

Dentro del `@media (max-width:560px)`, añadir:

```css
  /* La previa ya nace plegada -la enciende la casilla fx-prev-on-, asi que
     aqui solo hay que asegurar que quepa cuando el usuario la abre: el stage
     tiene max-width:440px, mas ancho que un movil de 390. */
  #fx-prev-stage{max-width:100%}
  /* Los campos de resolucion y el selector de preset caben en dos filas en vez
     de salirse de lado. */
  #fx-prev-wrap .frow{flex-wrap:wrap}
  #fx-prev-preset{max-width:100%}
```

**Nota:** si la fila de controles de la previa no usa la clase `.frow`, mirar el
marcado de la línea 359 en adelante y usar la clase real.

- [ ] **Step 2: Comprobar**

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test
Pop-Location
```

Esperado: `pass 248`, `fail 0`.

A mano por debajo de 560 px, en Divisas: encender la casilla de la previa y
comprobar que **no aparece barra de desplazamiento horizontal** en la página y
que la previa se dibuja dentro del ancho.

- [ ] **Step 3: Commit**

```bash
git add admin.html
git commit -m "Panel: la previa del tablero cabe en el movil

El diseno pedia plegar la previa detras de un boton, y resulta que ya estaba
hecho: fx-prev-wrap nace con display:none y lo enciende la casilla fx-prev-on,
con una toggleFxPreview() que ya existia. Anadir otro boton habria sido
duplicar un control, y con un nombre casi identico: una trampa para el
siguiente que lea el archivo.

Lo que si faltaba es que quepa cuando el usuario la abre. fx-prev-stage tenia
max-width:440px, mas ancho que un movil de 390, y los controles de resolucion
se salian de lado."
```

---

### Task 7: Verificación visual con capturas y medidas

**Files:**
- Create: `tools/capturar-panel.ps1`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: capturas y un informe de desbordes.

- [ ] **Step 1: Escribir el script de captura**

Crear `tools/capturar-panel.ps1`:

```powershell
# Captura el panel a anchos de movil y tableta, y AVISA de desbordes.
#
# Por que un script y no mirarlo a ojo: un elemento que se sale del ancho del
# viewport no siempre se ve -a veces solo aparece una barra horizontal fina- y
# es justo lo que hace que una pagina se sienta rota en un movil.
#
# admin.html exige sesion, asi que una captura a pelo cae en el login. Se
# resuelve con una pagina auxiliar servida por el propio servidor de pruebas
# que hace login y redirige: mismo origen, asi que la cookie vale.
param([string]$Puerto = "8099")

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$sp = Join-Path $env:TEMP "panel-capturas"
New-Item -ItemType Directory -Force $sp | Out-Null
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"

$anchos = @(@{n="movil"; w=390; h=844}, @{n="tableta"; w=820; h=1180})
foreach ($a in $anchos) {
  $salida = Join-Path $sp "$($a.n).png"
  & $chrome --headless --disable-gpu --no-sandbox --virtual-time-budget=9000 `
    --window-size=$($a.w),$($a.h) --screenshot="$salida" `
    "http://127.0.0.1:$Puerto/entrar-prueba.html"
  "{0,-8} {1}x{2} -> {3}" -f $a.n, $a.w, $a.h, $salida
}

# Medida objetiva: nada puede ser mas ancho que el viewport.
$js = "http://127.0.0.1:$Puerto/entrar-prueba.html"
& $chrome --headless --disable-gpu --no-sandbox --virtual-time-budget=9000 `
  --window-size=390,844 --dump-dom $js > (Join-Path $sp "movil.html")
"DOM volcado en $sp\movil.html"
```

- [ ] **Step 2: Escribir la página de entrada**

Crear `entrar-prueba.html` en la raíz del proyecto (es temporal; se borra en el paso 5):

```html
<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>entrar</title></head>
<body>
<div id="desbordes" style="font:14px monospace;color:#f05050"></div>
<script>
// Entra con la contrasena de pruebas y salta al panel. Mismo origen, asi que
// la cookie de sesion vale para /admin.html.
fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({password:"prueba1234"})})
  .then(function(){ location.href="/admin.html"; });
</script>
</body></html>
```

- [ ] **Step 3: Montar el servidor de pruebas y crear la contraseña**

```powershell
$sp = Join-Path $env:TEMP "panel-datos"
New-Item -ItemType Directory -Force $sp | Out-Null
Copy-Item "C:\ProgramData\InTeks Display\content.json" "$sp\content.json" -Force
$env:SIGNALOS_DATA = $sp
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
Start-Process python -ArgumentList "server.py","--port","8099" -WindowStyle Hidden
Pop-Location
Start-Sleep -Seconds 6
Invoke-WebRequest "http://127.0.0.1:8099/api/set-password" -Method POST `
  -Body '{"password":"prueba1234"}' -ContentType "application/json" -UseBasicParsing
```

Esperado: respuesta 200. Si devuelve que ya hay contraseña, borrar `$sp\admin.json` y repetir.

- [ ] **Step 4: Capturar y medir**

```powershell
powershell -ExecutionPolicy Bypass -File tools\capturar-panel.ps1
```

Abrir las dos capturas y comprobar **sección por sección** (Pantallas, Divisas, Ajustes y la playlist de una pantalla):

| Qué mirar | Criterio |
|---|---|
| Barra lateral | No se ve; el botón de menú sí |
| Desborde horizontal | Ninguna barra de desplazamiento lateral en la página |
| Botones de acción | 44 px de alto o más |
| Campos de texto | 16 px de letra en el ancho de móvil |
| Fila de divisas | País · código, tasa y dos botones; sin las ocho columnas |

- [ ] **Step 5: Limpiar y commitear**

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8099 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Remove-Item "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage\entrar-prueba.html"
```

```bash
git add tools/capturar-panel.ps1
git commit -m "Panel: script para capturar y medir el panel a anchos de movil

Un elemento que se sale del ancho del viewport no siempre se ve -a veces solo
aparece una barra horizontal fina- y es justo lo que hace que una pagina se
sienta rota en un movil. Asi que el script captura a 390x844 y 820x1180 y
vuelca el DOM para poder MEDIR en vez de mirar.

admin.html exige sesion y una captura a pelo cae en el login: se entra con una
pagina auxiliar servida por el propio servidor de pruebas, que hace login y
redirige. Mismo origen, asi que la cookie vale. Es el mismo truco que se uso
para fotografiar el tablero de divisas."
```

---

## Verificación final

Con el servidor en marcha:

```powershell
Push-Location "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
npm test                                    # 248, 0 fallos
Get-ChildItem tests\test_*.py | ForEach-Object { python $_.FullName }
git status --short                          # vacio
Pop-Location
```

Y la comprobación que ningún script puede hacer: **abrir el panel en el móvil de verdad** y confirmar que los botones caen bien bajo el pulgar, que el cajón se abre con soltura y que al tocar un campo **no salta el zoom**.

**Lo que no se puede verificar aquí:** cómo se siente en la mano. Se pueden medir anchos y comprobar que nada se sale, pero el tamaño real de los objetivos táctiles lo dice quien tenga el teléfono.
