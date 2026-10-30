# Editor de playlist más fácil Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que añadir y ordenar contenido en la playlist de una pantalla sea rápido: filas compactas, selector con búsqueda/filtros y selección múltiple, ajustes plegables.

**Architecture:** Solo `admin.html`. Un bloque de funciones puras testeable en Node y la reescritura de `renderPlList`, `renderPlLib` y el HTML del modal `#pl-modal`.

**Tech Stack:** HTML/JS vanilla, `node --test`.

Spec: `docs/superpowers/specs/2026-10-30-editor-playlist-design.md`.

## Global Constraints

- Todo en español; solo panel: NO tocar `server.py`, `player.html` ni el formato de la playlist (entradas `{...item, duration, desde?, hasta?, priority?}` y `{type:"package", pkg_id}`; guardado y semántica de `savePlModal`, `addToPl`, `rmFromPl`, `updDur`, `updVigencia`, `togglePriority`, `moverPlItem`, `moverEnLista` intactos o equivalentes).
- Ids de contenido en HTML nunca dentro de `onclick="…('${id}')"`: handlers por JS. Nombres con `esc()`. (`sid` también va por JS/closure, no en atributos.)
- Reutilizar `filtrarOrdenar`, `listasDeOrganizacion`, `normalizarTexto`, `libInfo`, `esc`, `toast`.
- Los tests existentes (`node --test tests/*.test.js`, 314) deben seguir en verde.
- Comprobación visual en el navegador integrado con servidor temporal (puerto 8130, contraseña de prueba en el alta local, datos sembrados con varias imágenes, vídeo, módulo fx, un paquete, carpetas y etiquetas; ids con comilla simple); parar el servidor, borrar el temporal y dejar el viewport en desktop. Comprobar también ancho de móvil (375) y que el modal no desborda.
- Commits acaban con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; no commitear `.superpowers/`. No subir versión ni publicar; viñeta en la entrada nueva `## 1.0.51 — sin publicar` del `CHANGELOG.md`.

---

### Task 1: Lógica pura + selector de contenido

**Files:**
- Modify: `admin.html` (bloque puro nuevo `// ── Editor de playlist` … `// ── fin del editor de playlist` justo antes de `function openPlModal`; HTML de `#plm-lib` y su cabecera; `renderPlLib`; CSS)
- Test: `tests/editor-playlist.test.js`

**Interfaces:**
- Produces (bloque puro): `resumenPlaylist(pl, items) -> {n, segundos, videosSinDuracion, texto}` (texto: «8 elementos · 1 min 34 s por vuelta», «1 elemento · 8 s por vuelta», «Sin contenido»; si `videosSinDuracion>0` añade « + vídeos»; paquetes cuentan como 1 elemento y suman la duración de sus contenidos existentes si `items`/paquetes los permiten — si no hay datos, solo cuentan como elemento); `idsEnPlaylist(pl) -> Set<string>` (ids de entradas directas, no paquetes); `insertarEn(lista, nuevos, posicion) -> Array` (inmutable; posición fuera de rango o no numérica → al final); `ajustesDistintosDeDefecto(cfg) -> boolean` (true si `priority_every` ≠ 4 y se usa, `safe_margin` > 0, o hay `priority` en algún elemento).
- Produces (estado): `plSel=new Set()` (ids marcados en el selector), `plFiltro={texto:"",tipo:"todos",carpeta:"all",etiquetas:[]}`.
- Produces: `addVariosToPl(sid, ids, posicion?)` que añade copias `{...item, duration:item.duration||8}` en el orden de `ids` usando `insertarEn` y llama a `renderPlList` y `renderPlLib`.

- [ ] **Step 1: Tests que fallan** `tests/editor-playlist.test.js` (carga por marcadores, como `tests/libreria-filtro.test.js`): `resumenPlaylist` (vacía; 1 imagen de 8 s; 3 imágenes 8+8+15 = «3 elementos · 31 s por vuelta»; 8 imágenes de 12 s = «8 elementos · 1 min 36 s por vuelta»; con un vídeo sin `duration` → termina en « + vídeos»); `idsEnPlaylist` (ignora paquetes); `insertarEn` (inicio, medio, final, fuera de rango, no muta); `ajustesDistintosDeDefecto`.
- [ ] **Step 2:** `node --test tests/editor-playlist.test.js` falla.
- [ ] **Step 3: Implementar** el bloque puro y el selector: cabecera del selector con buscador, desplegable de carpeta, chips de etiquetas y filtro de tipo (construidos como en la Librería, con `listasDeOrganizacion(content.items)`); `renderPlLib(sid)` usa `filtrarOrdenar(content.items,libInfo,{...plFiltro, orden:"nombre"})`, rejilla `repeat(auto-fill,minmax(120px,1fr))` con `max-height` generoso y scroll propio; cada miniatura con casilla (handler por JS), marca «✓ ya está» si `idsEnPlaylist` la contiene, clic en la miniatura = `addVariosToPl(sid,[id])`; barra «Añadir N» / «Quitar marca» (visible solo con selección; `N` cuenta solo ids visibles tras el filtro); miniatura `draggable` que, al soltarse sobre la lista, inserta en la posición. `plSel` y `plFiltro` se reinician al abrir el modal (`openPlModal`).
- [ ] **Step 4:** `node --test tests/*.test.js` en verde; comprobación visual del selector.
- [ ] **Step 5: Commit** `feat: selector de contenido del editor de playlist con búsqueda y selección múltiple`.

---

### Task 2: Filas compactas, panel «⋯», ajustes plegables y pie

**Files:**
- Modify: `admin.html` (`renderPlList`, HTML del modal `#pl-modal`, CSS `.pl-item`/`.pl-fechas`…, `CHANGELOG.md`)

**Interfaces:**
- Consumes: `resumenPlaylist`, `ajustesDistintosDeDefecto`, `insertarEn` (Task 1), las funciones de playlist existentes.

- [ ] **Step 1: Implementar** (sin cambios de comportamiento de guardado):
  - `renderPlList`: fila compacta de ~56 px según el spec (asa, miniatura 48×27, nombre en una línea con `esc`, insignia de tipo, duración editable/«auto», estrella, «⋯»). El panel «⋯» (estado en un `Set` de índices o ids abiertos, no persistente) contiene fechas, subir/bajar y quitar; se abre solo si el elemento tiene `desde`/`hasta` y muestra un punto en «⋯» cuando hay fechas. «fuera de fechas» sigue marcándose (opacidad y etiqueta). Paquetes: fila compacta con editar y quitar. Todos los handlers por JS con closures (nada de `sid` ni índices dentro de atributos `onclick`).
  - Línea de inserción: al arrastrar sobre una fila se pinta una línea arriba o abajo según la mitad de la fila donde está el puntero, y al soltar se mueve (o se inserta si viene del selector, usando `insertarEn`) exactamente ahí. Quitar la línea en `dragleave`/`dragend`.
  - Pie fijo bajo la lista con `resumenPlaylist(pl, content.items).texto`, actualizado en cada `renderPlList` (incluidos cambios de duración).
  - Ajustes: fila única Transición + ms + Orden aleatorio + botón «Más ajustes» que despliega prioridad ⭐ (visible solo con aleatorio, como hoy), margen de seguridad y el texto explicativo; plegado por defecto salvo `ajustesDistintosDeDefecto(cfg)` (calcular en `openPlModal`). Los ids de inputs (`plm-trans`, `plm-trans-ms`, `plm-shuffle`, `plm-priority-every`, `plm-safe-margin`) NO cambian, para que `savePlModal`/`openPlModal` sigan igual.
  - Layout del modal: dos columnas equilibradas (lista `minmax(0,1fr)` y selector `minmax(0,1.2fr)`), una columna en ancho < 760 px; altura de las listas con scroll propio para que el pie y los botones Guardar/Cancelar queden siempre visibles.
- [ ] **Step 2: Comprobar en navegador** (reglas de Global Constraints): añadir con clic, añadir 3 marcados con «Añadir 3», arrastrar del selector a medio de la lista y ver la línea, reordenar arrastrando y con subir/bajar del «⋯», editar duración y ver cambiar el total, fechas puestas abren el «⋯», quitar, paquete, «Más ajustes», Guardar y reabrir conserva todo, ancho 375.
- [ ] **Step 3:** `node --test tests/*.test.js` en verde.
- [ ] **Step 4: Commit** `feat: editor de playlist con filas compactas, total por vuelta y ajustes plegables`.
