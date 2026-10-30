# Mandar a pantallas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mandar uno o varios archivos de la Librería a una o varias pantallas de una vez.

**Architecture:** Ruta nueva `POST /api/send-to-screens` atómica bajo `contenido_en_edicion()`; en el panel, selección múltiple en la cuadrícula, botón en la ficha y un diálogo con la lista de pantallas.

**Tech Stack:** Python stdlib (`server.py`), HTML/JS vanilla (`admin.html`), tests Python con servidor real y `node --test`.

Spec: `docs/superpowers/specs/2026-10-30-mandar-a-pantallas-design.md`.

## Global Constraints

- Todo en español; todo por IP local; sin dependencias nuevas.
- Ruta nueva con auth (no meterla en `POST_PUBLICOS`). Escritura solo con `contenido_en_edicion()`.
- Un error de validación NO guarda nada ni sube `rev` (lanzar excepción dentro del `with`, nunca `return`; ver patrón `RevConflicto` cerca de `contenido_en_edicion`; o validar antes de abrir el `with`).
- Entradas añadidas a la playlist: `{**item, "duration": d}` (copia del item de la Librería, como `addToPl` del panel); duración por defecto 8.
- Ids en HTML: nunca dentro de `onclick="…('${id}')"`; asignar handlers por JS. Nombres con `esc()`.
- Puertos de test: 8124 (Python). Commits terminan con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

---

### Task 1: Servidor — `/api/send-to-screens`

**Files:**
- Modify: `server.py` (en `do_POST`, junto a `/api/rename`)
- Test: `tests/test_mandar_pantallas.py`

**Interfaces:**
- Produces: `POST /api/send-to-screens` `{ids, screens, duration?}` → 200 `{"ok": true, "added": int, "skipped": int}`; 400 `{"ok": false, "error": "Elige al menos un archivo y una pantalla"}` (listas vacías/no listas/demasiado largas) o `{"ok": false, "error": "Duración no válida (1 a 3600 s)"}`; 404 `{"ok": false, "error": "No existe el archivo X"}` / `"No existe la pantalla X"`.

- [ ] **Step 1: Test que falla.** Crear `tests/test_mandar_pantallas.py` con el esqueleto de `tests/test_libreria_info.py` (puerto 8124, sembrar `content.json` con 2 imágenes y 1 vídeo en `items`, `screens.json` con `s1`,`s2`,`s3` con nombres, y `content["screens"]` con `s1` que ya tiene la imagen A en su playlist y SIN entrada para `s3`). Comprobaciones:
  1. `{ids:[A,B], screens:[s1,s2]}` → 200, `added == 3`, `skipped == 1`; `GET /api/content`: `s1.playlist` tiene A una sola vez y B al final; `s2.playlist == [A,B]` (por `id`), cada entrada con `duration == 8` y copia de campos del item (`name`, `src`, `type`).
  2. `duration: 15` → las nuevas entradas llevan 15.
  3. Pantalla `s3` sin entrada en content → se crea con `mode == "independent"`.
  4. Segundo envío igual → `added == 0`.
  5. Pantalla inexistente → 404 y `rev` de content.json igual al anterior (leer `rev` por `GET /api/content` antes y después).
  6. Id inexistente → 404 y `rev` igual.
  7. `ids: []`, `screens: "s1"`, 201 ids → 400; `duration: 0` y `duration: "x"` → 400.
  8. Sin token → 401.
- [ ] **Step 2:** `py tests/test_mandar_pantallas.py` → falla (404 en la ruta).
- [ ] **Step 3: Implementar** la ruta, validando todo antes de escribir y comprobando pantallas contra `load_json(SCREENS_FILE)` y archivos contra `content["items"]` dentro del `with` (si algo no existe, lanzar una excepción propia dentro del `with` para que no se guarde, y responder 404 en su `except`). `notify_all()` solo si `added > 0`. Orden de validación: forma de listas → duración → ids → pantallas.
- [ ] **Step 4:** `py tests/test_mandar_pantallas.py` OK; `py tests/test_libreria_info.py` y `py tests/test_borrar_archivo.py` siguen OK.
- [ ] **Step 5: Commit** `feat: mandar archivos a varias pantallas de una vez`.

---

### Task 2: Panel — selección, diálogo y envío

**Files:**
- Modify: `admin.html` (CSS `.lib-*`; `renderLibrary`; `abrirFicha`; bloque nuevo; `index` del diálogo; `CHANGELOG.md` entrada 1.0.50 «sin publicar»)
- Test: `tests/mandar-pantallas.test.js`

**Interfaces:**
- Consumes: `POST /api/send-to-screens` (Task 1); `regScreens` (mapa id→{name,…}), `content.items`, `libInfo`, `esc`, `toast`, `loadAll`.
- Produces (bloque puro entre `// ── Mandar a pantallas` y `// ── fin de mandar a pantallas`, testeable en Node): `mensajeEnvio(r) -> string` (`{added:3,skipped:1}` → `"Añadido en 3 sitios · 1 ya lo tenía"`; `{added:1,skipped:0}` → `"Añadido en 1 sitio"`; `{added:0,skipped:2}` → `"No se añadió nada: ya lo tenían"`) y `duracionValida(v) -> number|null` (1–3600, acepta cadenas numéricas, null si no).

- [ ] **Step 1: Test que falla** `tests/mandar-pantallas.test.js` (carga por marcadores como `tests/libreria-filtro.test.js`) con los casos de arriba más `duracionValida("15") === 15`, `("0") === null`, `("x") === null`, `(3601) === null`.
- [ ] **Step 2:** `node --test tests/mandar-pantallas.test.js` falla.
- [ ] **Step 3: Implementar** el bloque puro y la interfaz:
  - `let libSel=new Set()`. En `renderLibrary`, cada tarjeta lleva una casilla `<input type="checkbox" class="lib-chk">` arriba a la izquierda, visible al pasar el ratón o si hay selección; marcar/desmarcar actualiza `libSel` (handler por JS) sin abrir la ficha (`stopPropagation`). Los ids que ya no existen se quitan de `libSel` al renderizar.
  - Barra `#lib-selbar` sobre la cuadrícula (oculta si `libSel.size===0`): «N seleccionados», botón «Mandar a pantallas» (abre el diálogo con esos ids) y «Quitar selección».
  - Botón «Mandar a pantallas» en `abrirFicha` (abre el diálogo con ese id).
  - Diálogo `#mp-dlg` (overlay centrado, z-index sobre la ficha): título «Mandar N archivo(s) a pantallas», lista de pantallas de `regScreens` con casilla y nombre (`esc`), enlace «Marcar todas», campo «Duración por imagen (s)» (8), botones Cancelar / Mandar. Sin pantallas registradas: texto «Todavía no hay pantallas conectadas» y solo Cancelar. Mandar deshabilitado si no hay ninguna marcada. Al enviar: `duracionValida`; si es null, toast de error; POST; si `!ok` toast con `error` del servidor y el diálogo sigue abierto; si ok: cierra, `libSel.clear()`, `await loadAll()`, `toast(mensajeEnvio(r))`.
  - `loadAll` ya refresca la ficha y `libInfo`: no tocar.
- [ ] **Step 4: Comprobar en el navegador** con servidor temporal (puerto 8125) y datos sembrados, ids con comilla simple incluidos: marcar 2, mandar a 2 pantallas, ver «Añadido en 4 sitios» y que la insignia «en uso» sube; repetir y ver «No se añadió nada». Parar servidor, borrar temporal, viewport a desktop.
- [ ] **Step 5:** `node --test tests/*.test.js` y los tres tests Python de librería en verde. Entrada 1.0.50 en `CHANGELOG.md` (no subir versión ni publicar).
- [ ] **Step 6: Commit** `feat: seleccionar archivos en la Librería y mandarlos a pantallas`.
