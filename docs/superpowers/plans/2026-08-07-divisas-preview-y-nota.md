# Divisas: vista previa por pantalla y mensaje al pie — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el admin muestre una vista previa fiel de cuántas divisas caben en cada pantalla, y permitir un mensaje fijo al pie del módulo.

**Architecture:** El player gana un modo `?preview=1` que renderiza un item inyectado por `postMessage` y devuelve cuántas páginas le salieron. El admin lo incrusta en un iframe dimensionado a los píxeles reales de la pantalla y reducido con `transform:scale()`, de modo que los `clamp()`/`vw`/`vh` se resuelven igual que en el televisor. Las pantallas reportan su geometría por un endpoint nuevo. El mensaje al pie es un hermano flex de las filas, así que la paginación existente lo absorbe sin cambios.

**Tech Stack:** HTML/CSS/JS puro (sin frameworks, sin build), Python stdlib, tests con `node:test` y `vm`.

## Global Constraints

- Sin frameworks JS. Sin paso de build. Todo inline en los `.html`.
- Sin dependencias externas de Python. Solo librería estándar.
- El estilo del código existente es compacto, sin espacios alrededor de operadores. Imítalo.
- No tocar `setupFxPagination()` más allá de lo que indica la Tarea 1. Ya funciona.
- Los campos nuevos son aditivos y opcionales: el contenido existente debe seguir funcionando sin migración.
- Spec de referencia: `docs/superpowers/specs/2026-08-07-divisas-preview-y-nota-design.md`

---

### Task 1: Extraer el agrupamiento de páginas a una función pura

Hoy `setupFxPagination()` mezcla medir el DOM, agrupar filas y gestionar temporizadores. El agrupamiento es lógica pura y no se puede probar. Se extrae sin cambiar el comportamiento.

**Files:**
- Modify: `player.html:509-516` (el bloque de agrupamiento dentro de `setupFxPagination`)
- Create: `tests/fx-pagination.test.js`

**Interfaces:**
- Consumes: nada.
- Produces: `groupRowsIntoPages(heights: number[], avail: number) → number[][]` — recibe las alturas ya medidas y la altura disponible, devuelve los índices de fila de cada página. Definida en `player.html` justo antes de `setupFxPagination()`.

- [ ] **Step 1: Escribir el test que falla**

Crea `tests/fx-pagination.test.js`:

```js
/**
 * Tests del agrupamiento en páginas del módulo de divisas.
 *
 * Mismo arnés que schedule.test.js: extrae la función del propio player.html y
 * la ejecuta en un vm, para no probar una copia que se desincronice.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");

function loadGroupRowsIntoPages() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const from = src.indexOf("function groupRowsIntoPages(");
  const to = src.indexOf("function setupFxPagination(");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error(
      "No se encuentra groupRowsIntoPages() antes de setupFxPagination() en " +
      "player.html. Si se ha renombrado o movido, actualiza este arnés."
    );
  }
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(src.slice(from, to), ctx);
  return ctx.groupRowsIntoPages;
}

const group = loadGroupRowsIntoPages;

test("si todas las filas caben, sale una sola página", () => {
  assert.deepStrictEqual(group()([50, 50, 50], 300), [[0, 1, 2]]);
});

test("las filas que desbordan pasan a la página siguiente", () => {
  assert.deepStrictEqual(group()([50, 50, 50, 50], 120), [[0, 1], [2, 3]]);
});

test("con muy poco alto cabe una fila por página", () => {
  assert.deepStrictEqual(group()([50, 50, 50, 50], 80), [[0], [1], [2], [3]]);
});

test("menos alto disponible produce más páginas (efecto del pie)", () => {
  const alturas = [40, 40, 40, 40, 40];
  assert.deepStrictEqual(group()(alturas, 200), [[0, 1, 2, 3, 4]]);
  assert.deepStrictEqual(group()(alturas, 150), [[0, 1, 2], [3, 4]]);
});

test("una fila más alta que el espacio disponible se coloca igualmente", () => {
  assert.deepStrictEqual(group()([200], 100), [[0]]);
});

test("sin filas no hay páginas", () => {
  assert.deepStrictEqual(group()([], 300), []);
});
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `npm test`
Expected: FAIL. El arnés lanza `No se encuentra groupRowsIntoPages()...` porque la función todavía no existe.

- [ ] **Step 3: Extraer la función**

En `player.html`, **justo antes** de la línea `function setupFxPagination(slide, perPageMs, onDone){`, inserta:

```js
// Agrupa filas en páginas según la altura disponible. Pura a propósito: recibe
// las alturas ya medidas, para poder probarla sin DOM (tests/fx-pagination.test.js).
// Una fila más alta que `avail` se coloca igualmente en su propia página: el
// guardo `used>0` evita el bucle infinito y las páginas vacías.
function groupRowsIntoPages(heights, avail){
  const pages=[]; let page=[]; let used=0;
  heights.forEach((h,i)=>{
    if(used>0 && used+h>avail){ pages.push(page); page=[]; used=0; }
    page.push(i); used+=h;
  });
  if(page.length) pages.push(page);
  return pages;
}
```

Después, dentro de `setupFxPagination()`, sustituye este bloque:

```js
  // Agrupar filas en páginas según la altura disponible (medición real del DOM)
  const pages=[]; let page=[]; let used=0;
  rows.forEach(r=>{
    const h=r.offsetHeight;
    if(used>0 && used+h>avail){ pages.push(page); page=[]; used=0; }
    page.push(r); used+=h;
  });
  if(page.length) pages.push(page);
```

por:

```js
  // Agrupar filas en páginas según la altura disponible (medición real del DOM)
  const pages=groupRowsIntoPages(rows.map(r=>r.offsetHeight), avail).map(idxs=>idxs.map(i=>rows[i]));
```

- [ ] **Step 4: Ejecutar los tests y verificar que pasan**

Run: `npm test`
Expected: PASS. 18 tests en total (12 de horario + 6 nuevos), 0 fallos.

- [ ] **Step 5: Commit**

```bash
git add player.html tests/fx-pagination.test.js
git commit -m "refactor: extraer groupRowsIntoPages de setupFxPagination

La lógica de agrupamiento era pura pero estaba enterrada entre la medición
del DOM y los temporizadores, así que no se podía probar. Sin cambio de
comportamiento: se conserva el guardo used>0 que coloca una fila más alta
que el espacio disponible en lugar de descartarla."
```

---

### Task 2: Mensaje al pie, de punta a punta

Deliverable independiente: al terminar esta tarea el mensaje ya funciona en pantalla, aunque todavía no exista la vista previa.

**Files:**
- Modify: `player.html:32` (añadir regla CSS tras `.mod-fx-rows`)
- Modify: `player.html:268-277` (`buildFxSlide`, la plantilla `innerHTML`)
- Modify: `admin.html:304` (formulario, tras el campo Duración)
- Modify: `admin.html:1719` (`saveFxModule`)
- Modify: `admin.html:1746` (`editFxModule`)

**Interfaces:**
- Consumes: nada de la Tarea 1.
- Produces: el campo `footer_note` (string, por defecto `""`) en los items de tipo `fx`; el elemento `<div class="mod-fx-note">` dentro de `.mod-fx`; el input `#fx-note` en el admin.

- [ ] **Step 1: Añadir la regla CSS en el player**

En `player.html`, justo después de la línea que define `.mod-fx-rows{...}`, añade:

```css
.mod-fx-note{flex-shrink:0;max-height:18%;overflow:hidden;padding:1.5vh 4vw 2.5vh;border-top:1px solid rgba(255,255,255,.12);font-size:clamp(11px,1.6vw,22px);line-height:1.35;opacity:.75}
```

`flex-shrink:0` junto al `flex:1;min-height:0` de `.mod-fx-rows` hace que el pie
robe alto a las filas automáticamente. `max-height:18%` evita que un mensaje
largo ahogue las cotizaciones.

- [ ] **Step 2: Renderizar el pie en `buildFxSlide`**

En `player.html`, dentro de `buildFxSlide(item)`, justo antes de `div.innerHTML=`, añade:

```js
  const noteHtml=item.footer_note?`<div class="mod-fx-note">${item.footer_note}</div>`:"";
```

y cambia la última línea de la plantilla, de:

```js
    <div class="mod-fx-rows">${rows}</div>`;
```

a:

```js
    <div class="mod-fx-rows">${rows}</div>
    ${noteHtml}`;
```

Si `footer_note` está vacío no se emite el `div`, así que no ocupa alto.

- [ ] **Step 3: Añadir el campo en el formulario del admin**

En `admin.html`, justo después del `div` que contiene `id="fx-dur"`, añade:

```html
    <div class="fg" style="margin-bottom:14px"><label class="flabel">Mensaje al pie (opcional)</label><input class="finput" id="fx-note" placeholder="Ej: Tipos sujetos a variación sin previo aviso"></div>
```

- [ ] **Step 4: Guardar y recuperar el campo**

En `saveFxModule()`, dentro del objeto `data`, añade al final (antes del cierre `}`):

```js
,footer_note:document.getElementById("fx-note").value.trim()
```

En `editFxModule(id)`, después de la línea `document.getElementById("fx-dur").value=item.duration||15;`, añade:

```js
  document.getElementById("fx-note").value=item.footer_note||"";
```

- [ ] **Step 5: Verificar a mano en el navegador**

No hay test automático aquí: es marcado y el arnés de `vm` no monta DOM. Montar
uno para tres líneas de plantilla no compensa. La consecuencia real del pie
—que caben menos filas por página— **sí** está cubierta por el test
"menos alto disponible produce más páginas" de la Tarea 1.

```
python server.py
```

1. Admin → Divisas. Crea un módulo con 8 divisas y el mensaje
   "Tipos sujetos a variación sin previo aviso". Guarda y asígnalo a una pantalla.
2. Abre `http://localhost/player.html?screen=PC`.
3. Comprueba: el mensaje aparece abajo con una línea separadora; se ve en
   **todas** las páginas al rotar; el indicador `1 / 2` sigue funcionando.
4. Edita el módulo y vacía el mensaje. Confirma que el pie desaparece por
   completo y que vuelven a caber más filas por página.

- [ ] **Step 6: Commit**

```bash
git add player.html admin.html
git commit -m "feat: mensaje fijo al pie del módulo de divisas

Campo footer_note opcional. Se renderiza como hermano flex de .mod-fx-rows,
así que le resta alto y setupFxPagination recalcula las páginas solo, sin
cambios en la paginación."
```

---

### Task 3: Las pantallas reportan su geometría

**Files:**
- Modify: `server.py:647` (nuevo bloque en `do_POST`, tras los helpers `ok`/`err`/`jresp`)
- Modify: `player.html` (función nueva + llamada en el arranque y en el `resize` existente)
- Create: `tests/test_screen_info.py`

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces: `POST /api/screen-info` con cuerpo `{screen, w, h, dpr}`, que escribe `screens[sid]["viewport"] = {w, h, dpr, orientation}` en `screens.json`. La Tarea 5 lee ese `viewport` desde `GET /api/screens`.

- [ ] **Step 1: Escribir el test que falla**

Crea `tests/test_screen_info.py`:

```python
"""
Comprueba que POST /api/screen-info guarda la geometría en screens.json.

Arranca el servidor en un directorio temporal para no tocar los datos reales.
Ejecutar:  python tests/test_screen_info.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8096


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=5))


def main():
    work = tempfile.mkdtemp(prefix="signalos_screeninfo_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)

    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
    failed = 0
    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arrancó")
            return 1

        # Pantalla horizontal
        post(base + "/api/screen-info",
             {"screen": "TV", "w": 1920, "h": 1080, "dpr": 1})
        v = json.load(open(os.path.join(work, "screens.json")))["TV"]["viewport"]
        ok = v["w"] == 1920 and v["h"] == 1080 and v["orientation"] == "landscape"
        print(f"  {'ok  ' if ok else 'FALLO'} horizontal -> {v}")
        failed += not ok

        # Pantalla vertical
        post(base + "/api/screen-info",
             {"screen": "Tablet", "w": 800, "h": 1280, "dpr": 2})
        v = json.load(open(os.path.join(work, "screens.json")))["Tablet"]["viewport"]
        ok = v["orientation"] == "portrait" and v["dpr"] == 2
        print(f"  {'ok  ' if ok else 'FALLO'} vertical   -> {v}")
        failed += not ok

        # Sin identificador de pantalla -> 400, y no debe crear entradas basura
        try:
            post(base + "/api/screen-info", {"w": 100, "h": 100})
            print("  FALLO sin screen deberia dar 400")
            failed += 1
        except urllib.error.HTTPError as e:
            ok = e.code == 400
            print(f"  {'ok  ' if ok else 'FALLO'} sin screen -> {e.code}")
            failed += not ok

        # Reportar dos veces actualiza en vez de duplicar
        post(base + "/api/screen-info",
             {"screen": "TV", "w": 1280, "h": 720, "dpr": 1})
        screens = json.load(open(os.path.join(work, "screens.json")))
        ok = screens["TV"]["viewport"]["w"] == 1280 and len(screens) == 2
        print(f"  {'ok  ' if ok else 'FALLO'} actualiza sin duplicar")
        failed += not ok
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)

    print("TODO OK" if failed == 0 else f"{failed} FALLO(S)")
    return 1 if failed else 0


sys.exit(main())
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `python tests/test_screen_info.py`
Expected: FAIL. El endpoint no existe todavía, así que `urlopen` lanza `HTTPError 404` en la primera llamada.

- [ ] **Step 3: Implementar el endpoint**

En `server.py`, dentro de `do_POST`, inmediatamente después de la definición de `jresp` y antes del bloque `if path == "/api/login":`, inserta:

```python
        # ── API: la pantalla informa de su tamaño real. Lo usa la vista previa
        #    del admin para dimensionar el iframe con los píxeles de verdad.
        if path == "/api/screen-info":
            try:
                d = json.loads(body or "{}")
                sid = (d.get("screen") or "").strip()
                if not sid:
                    jresp(400, {"ok": False, "error": "falta screen"}); return
                w = int(d.get("w") or 0); h = int(d.get("h") or 0)
                screens = load_json(SCREENS_FILE)
                if sid not in screens:
                    screens[sid] = {"id": sid, "connected": False, "last_seen": time.time()}
                screens[sid]["viewport"] = {
                    "w": w, "h": h,
                    "dpr": float(d.get("dpr") or 1),
                    "orientation": "portrait" if h > w else "landscape",
                }
                save_json(SCREENS_FILE, screens)
                ok()
            except Exception as e: err(e)
            return
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `python tests/test_screen_info.py`
Expected: `TODO OK`, con las cuatro comprobaciones en `ok`.

- [ ] **Step 5: Hacer que el player reporte**

En `player.html`, después de la función `applyRotation(deg)`, añade:

```js
// Informar al servidor del tamaño real de esta pantalla, para que la vista
// previa del admin pueda dimensionar su iframe con los píxeles de verdad.
function reportScreenInfo(){
  if(!SCREEN_ID) return;
  fetch("/api/screen-info",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({screen:SCREEN_ID,w:window.innerWidth,h:window.innerHeight,
                         dpr:window.devicePixelRatio||1})}).catch(()=>{});
}
```

Cambia la línea de arranque:

```js
if(SCREEN_ID){ connectSSE();loadPlaylist(); }   // sin identidad ya se redirigió a /pair
```

por:

```js
if(SCREEN_ID){ connectSSE();loadPlaylist();reportScreenInfo(); }   // sin identidad ya se redirigió a /pair
```

Y dentro del listener de `resize` que ya existe, añade la llamada junto al re-render:

```js
window.addEventListener("resize",()=>{
  clearTimeout(resizeTimer);
  resizeTimer=setTimeout(()=>{ if(playlist.length) showSlide(current); reportScreenInfo(); }, 400);
});
```

El antirrebote de 400 ms del listener existente ya cubre el requisito de no
inundar el servidor al redimensionar.

- [ ] **Step 6: Verificar a mano**

```
python server.py
```

Abre `http://localhost/player.html?screen=PC`, espera dos segundos y comprueba:

```bash
python -c "import json;print(json.load(open('screens.json'))['PC'].get('viewport'))"
```

Debe imprimir el `viewport` con el tamaño de tu ventana.

- [ ] **Step 7: Commit**

```bash
git add server.py player.html tests/test_screen_info.py
git commit -m "feat: las pantallas reportan su geometría en /api/screen-info

Endpoint propio en vez de colgarlo del SSE: es una unidad con un solo
propósito y se puede probar aislada. Primer test de la API en Python."
```

---

### Task 4: Modo vista previa en el player

**Files:**
- Modify: `player.html` (constante `PREVIEW`, guarda del redirect a `/pair`, `isScreenActive`, arranque, `setupFxPagination`)

**Interfaces:**
- Consumes: `reportScreenInfo()` de la Tarea 3; `groupRowsIntoPages()` de la Tarea 1 (indirectamente).
- Produces: la URL `player.html?preview=1`, que acepta `{type:"preview-item", item, rotation}` por `postMessage` y emite `{type:"preview-ready"}` al cargar y `{type:"preview-pages", pages, rowsFirstPage}` tras paginar. La Tarea 5 consume ambos mensajes.

- [ ] **Step 1: Declarar el modo y proteger el redirect**

En `player.html`, después de `const params=new URLSearchParams(location.search);`, añade:

```js
// Modo vista previa: el admin incrusta el player en un iframe. No debe
// conectarse por SSE, ni registrarse como pantalla, ni aplicar el horario,
// o ensuciaría screens.json marcando pantallas como conectadas.
const PREVIEW=params.get("preview")==="1";
```

Cambia:

```js
if(!SCREEN_ID){ location.replace("/pair"); }
```

por:

```js
if(!SCREEN_ID && !PREVIEW){ location.replace("/pair"); }
```

Esto es imprescindible: en preview no hay `?screen=`, así que sin la guarda el
iframe se iría a `/pair` inmediatamente.

Protege también las dos líneas que escriben en el DOM de espera, que fallarían
con `SCREEN_ID` nulo. Cambia:

```js
document.getElementById("sid-display").textContent=SCREEN_ID;
document.getElementById("url-hint").textContent=location.host+"/player.html?screen="+SCREEN_ID;
```

por:

```js
if(SCREEN_ID){
  document.getElementById("sid-display").textContent=SCREEN_ID;
  document.getElementById("url-hint").textContent=location.host+"/player.html?screen="+SCREEN_ID;
}
if(PREVIEW) document.getElementById("waiting").style.display="none";
```

- [ ] **Step 2: Desactivar el horario en preview**

En `isScreenActive()`, añade como **primera** línea del cuerpo:

```js
  if(PREVIEW) return true;                                       // la previa siempre muestra contenido
```

Sin esto, previsualizar fuera del horario de la pantalla mostraría el standby en negro.

- [ ] **Step 3: Recibir el item y responder con las páginas**

Sustituye la línea de arranque de la Tarea 3:

```js
if(SCREEN_ID){ connectSSE();loadPlaylist();reportScreenInfo(); }   // sin identidad ya se redirigió a /pair
```

por:

```js
if(PREVIEW){
  // El admin inyecta el módulo que está editando; así se ve antes de guardar.
  window.addEventListener("message",(e)=>{
    const m=e.data||{};
    if(m.type!=="preview-item"||!m.item) return;
    applyRotation(m.rotation||0);
    playlist=[m.item]; rebuildSlides(); showSlide(0);
  });
  parent.postMessage({type:"preview-ready"},"*");
} else if(SCREEN_ID){ connectSSE();loadPlaylist();reportScreenInfo(); }
```

Y cambia el intervalo de recarga para que no corra en preview:

```js
setInterval(()=>{ if(SCREEN_ID) loadPlaylist(); },15000);
```

por:

```js
setInterval(()=>{ if(SCREEN_ID && !PREVIEW) loadPlaylist(); },15000);
```

- [ ] **Step 4: Informar del número de páginas**

En `setupFxPagination()` hay **tres** puntos donde queda decidido el número de páginas. Añade el aviso en los tres.

Tras `if(rows.length<=1 || avail<=0){`, dentro del bloque, antes de `startProgress`:

```js
    if(PREVIEW) parent.postMessage({type:"preview-pages",pages:1,rowsFirstPage:rows.length},"*");
```

Tras `if(pages.length<=1){`, dentro del bloque, antes de `startProgress`:

```js
    if(PREVIEW) parent.postMessage({type:"preview-pages",pages:1,rowsFirstPage:rows.length},"*");
```

Justo después de `let pi=0;` (caso de varias páginas):

```js
  if(PREVIEW) parent.postMessage({type:"preview-pages",pages:pages.length,rowsFirstPage:pages[0].length},"*");
```

- [ ] **Step 5: Verificar a mano**

```
python server.py
```

Abre `http://localhost/player.html?preview=1` directamente. Debe quedarse en
negro sin redirigir a `/pair` y sin registrar ninguna pantalla. Confirma que
`screens.json` no ha ganado entradas nuevas:

```bash
python -c "import json;print(list(json.load(open('screens.json')).keys()))"
```

- [ ] **Step 6: Commit**

```bash
git add player.html
git commit -m "feat: modo vista previa del player (?preview=1)

Renderiza un item inyectado por postMessage y devuelve cuántas páginas le
salieron. Suprime SSE, registro de pantalla y comprobación de horario para
no ensuciar screens.json al incrustarlo en el admin."
```

---

### Task 5: Panel de vista previa en el admin

**Files:**
- Modify: `admin.html` (tarjeta nueva tras el formulario de divisas, y las funciones que la alimentan)

**Interfaces:**
- Consumes: `viewport` de `GET /api/screens` (Tarea 3); los mensajes `preview-ready` y `preview-pages`, y la URL `?preview=1` (Tarea 4); el campo `footer_note` (Tarea 2).
- Produces: nada que consuman tareas posteriores.

- [ ] **Step 1: Añadir la tarjeta al formulario**

En `admin.html`, inmediatamente después del `div` que contiene `id="fx-note"` (Tarea 2), añade:

```html
    <div class="fg" style="margin-bottom:14px">
      <label class="flabel">Vista previa en pantalla</label>
      <select class="finput" id="fx-prev-screen" onchange="renderFxPreview()"></select>
    </div>
    <div id="fx-prev-stage" style="position:relative;overflow:hidden;border:1px solid var(--b);border-radius:var(--r);background:#000"></div>
    <div id="fx-prev-info" style="font-size:12px;color:var(--muted);margin-top:8px"></div>
```

- [ ] **Step 2: Poblar el selector de pantallas**

Añade estas funciones en `admin.html`, junto a las demás de divisas (después de `renderFxSaved`):

```js
// ── Vista previa de divisas ────────────────────────────────────────────────
let fxPrevReady=false;

async function loadFxPreviewScreens(){
  const sel=document.getElementById("fx-prev-screen");
  if(!sel) return;
  let screens={};
  try{ screens=await (await fetch("/api/screens")).json(); }catch(e){}
  const cfgs=content.screens||{};
  sel.innerHTML="";
  const ids=Object.keys(screens);
  if(!ids.length){
    sel.innerHTML='<option data-w="1920" data-h="1080" data-rot="0">Sin pantallas — se asume 1920×1080</option>';
  }else{
    ids.forEach(id=>{
      const vp=screens[id].viewport;
      const rot=(cfgs[id]&&cfgs[id].rotation)||0;
      const label=vp?`${id} — ${vp.w}×${vp.h}`:`${id} — sin datos, se asume 1920×1080`;
      const o=document.createElement("option");
      o.textContent=label;
      o.dataset.w=vp?vp.w:1920; o.dataset.h=vp?vp.h:1080; o.dataset.rot=rot;
      sel.appendChild(o);
    });
  }
  renderFxPreview();
}
```

- [ ] **Step 3: Construir el borrador y dibujar el iframe**

Añade a continuación:

```js
// El item tal y como está AHORA en el formulario, sin guardar.
function fxDraftItem(){
  return {type:"fx",
    title:document.getElementById("fx-title").value||"Tipos de cambio",
    base_currency:document.getElementById("fx-base").value||"EUR",
    rows:[...fxRows],
    bg:document.getElementById("fx-bg").value,
    color:document.getElementById("fx-color").value,
    logo:fxLogo||"",
    footer_note:document.getElementById("fx-note").value.trim(),
    duration:9999};
  // duration alto A PROPÓSITO: la previa se queda en la página 1 en lugar de
  // rotar. El contador ya dice cuántas páginas hay, y una previa que se mueve
  // sola mientras escribes distrae. No lo "arregles" bajándolo.
}

function renderFxPreview(){
  const sel=document.getElementById("fx-prev-screen");
  const stage=document.getElementById("fx-prev-stage");
  if(!sel||!stage||!sel.selectedOptions.length) return;
  const opt=sel.selectedOptions[0];
  let w=parseInt(opt.dataset.w)||1920, h=parseInt(opt.dataset.h)||1080;
  const rot=parseInt(opt.dataset.rot)||0;
  if(rot===90||rot===270){ const t=w; w=h; h=t; }   // la pantalla está girada

  // Clave de la fidelidad: el iframe mide los píxeles REALES de la pantalla y
  // se encoge visualmente. Así clamp()/vw/vh se resuelven igual que en el TV.
  const f=Math.min(1, (stage.clientWidth||640)/w);
  stage.style.height=(h*f)+"px";
  let fr=document.getElementById("fx-prev-frame");
  if(!fr){
    fr=document.createElement("iframe");
    fr.id="fx-prev-frame"; fr.src="/player.html?preview=1";
    fr.style.cssText="position:absolute;top:0;left:0;border:0;transform-origin:top left";
    fxPrevReady=false;
    // Si el player no llega a responder, decirlo en vez de dejar un recuadro
    // negro que parezca un módulo mal configurado.
    setTimeout(()=>{
      if(fxPrevReady) return;
      const info=document.getElementById("fx-prev-info");
      if(info) info.textContent="No se pudo cargar la vista previa. ¿Está el servidor sirviendo /player.html?";
    },5000);
    fr.addEventListener("error",()=>{
      const info=document.getElementById("fx-prev-info");
      if(info) info.textContent="No se pudo cargar la vista previa.";
    });
    stage.appendChild(fr);
  }
  fr.style.width=w+"px"; fr.style.height=h+"px";
  fr.style.transform=`scale(${f})`;
  // rotation:0 a propósito. El iframe YA tiene el ancho y alto intercambiados
  // arriba, así que rotar además el contenido lo giraría dos veces.
  if(fxPrevReady) fr.contentWindow.postMessage({type:"preview-item",item:fxDraftItem(),rotation:0},"*");
}

window.addEventListener("message",(e)=>{
  const m=e.data||{};
  if(m.type==="preview-ready"){ fxPrevReady=true; renderFxPreview(); return; }
  if(m.type==="preview-pages"){
    const info=document.getElementById("fx-prev-info");
    if(info) info.textContent=m.pages>1
      ? `${m.pages} páginas · ${m.rowsFirstPage} filas en la primera`
      : `Cabe en una sola página (${m.rowsFirstPage} filas)`;
  }
});

// Refrescar la previa mientras se edita
["fx-title","fx-base","fx-bg","fx-color","fx-note"].forEach(id=>{
  const el=document.getElementById(id);
  if(el) el.addEventListener("input",()=>renderFxPreview());
});
window.addEventListener("resize",()=>renderFxPreview());
```

**Nota para quien implemente:** `renderFxRows()` ya se llama cada vez que se
añade, borra o edita una fila de divisa. Añade `renderFxPreview();` como última
línea de `renderFxRows()` para que la previa siga esos cambios.

- [ ] **Step 4: Cargar el selector al entrar en la sección**

En `admin.html`, dentro de `showPage(id)`, junto a la línea que ya existe
`if(id==="packages"){ ... }`, añade:

```js
  if(id==="fx"){ loadFxPreviewScreens(); }
```

- [ ] **Step 5: Verificar a mano**

```
python server.py
```

1. Abre una pantalla real primero (`/player.html?screen=PC`) para que reporte su geometría.
2. Admin → Divisas. El selector debe mostrar `PC — 1920×1080` (o tu tamaño real).
3. Añade divisas de una en una: la previa se actualiza y el contador pasa de
   "Cabe en una sola página" a "2 páginas · N filas en la primera".
4. Escribe el mensaje al pie: el contador debe **bajar** el número de filas de
   la primera página. Es la comprobación central del diseño.
5. Confirma que `screens.json` no ha ganado ninguna entrada por el iframe.

- [ ] **Step 6: Commit**

```bash
git add admin.html
git commit -m "feat: vista previa de divisas por pantalla en el admin

Incrusta el player real en un iframe dimensionado a los píxeles de la
pantalla elegida y reducido con transform:scale, para que clamp()/vw/vh se
resuelvan igual que en el televisor. Cero lógica de maquetación duplicada:
el renderizador real dice cuántas páginas salen."
```

---

## Verificación final

- [ ] `npm test` → 18 tests, 0 fallos
- [ ] `python tests/test_screen_info.py` → `TODO OK`
- [ ] `python -m py_compile server.py` → sin salida
- [ ] Recorrido manual completo del Paso 5 de la Tarea 5
- [ ] Actualizar `CLAUDE_CODE_PROMPT.md`: añadir `POST /api/screen-info` a la lista de endpoints, `footer_note` y `viewport` a la tabla de datos, y `?preview=1` a la descripción del player
