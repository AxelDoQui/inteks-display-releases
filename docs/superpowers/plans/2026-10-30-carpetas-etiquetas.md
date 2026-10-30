# Carpetas y etiquetas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Organizar la Librería con una carpeta por archivo y varias etiquetas, con filtros, ficha y acciones en bloque.

**Architecture:** Campos opcionales `folder`/`tags` en cada item de `content.json`; ruta `POST /api/organize` atómica; `filtrarOrdenar` ampliada; ficha, barra de selección y barra de filtros del panel.

**Tech Stack:** Python stdlib (`server.py`), HTML/JS vanilla (`admin.html`), tests Python con servidor real y `node --test`.

Spec: `docs/superpowers/specs/2026-10-30-carpetas-etiquetas-design.md`.

## Global Constraints

- Todo en español; todo por IP local; sin dependencias nuevas.
- Ruta nueva con auth (no meterla en `POST_PUBLICOS`); escritura solo con `contenido_en_edicion()`.
- Error de validación o no-cambio NO guarda ni sube `rev` (excepción dentro del `with`, patrón `ArchivoNoExiste` / `NadaQueAnadir` de `server.py`).
- Límites: carpeta 1–40 car.; etiqueta 1–30 car.; máx. 10 etiquetas por archivo; `ids` 1–200.
- Equivalencia de nombres: sin mayúsculas ni acentos (misma lógica que `normalizarTexto` del panel); si existe una equivalente en otro item, se reutiliza su grafía.
- Ids en HTML: nunca dentro de `onclick="…('${id}')"`; handlers por JS. Nombres con `esc()`.
- Puerto de test Python: 8126 (y 8127 si hace falta servidor de navegador). Commits acaban con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; no commitear `.superpowers/`.

---

### Task 1: Servidor — `/api/organize`

**Files:**
- Modify: `server.py` (junto a `/api/send-to-screens`)
- Test: `tests/test_organizar.py`

**Interfaces:**
- Produces: `POST /api/organize` `{ids, folder?, addTags?, removeTags?}` → 200 `{"ok": true, "changed": int}` (items realmente modificados); 400 `{"ok": false, "error": "Petición no válida"}` (formas/lista vacía/sin ninguna acción), `"Carpeta no válida (1 a 40 caracteres)"`, `"Etiqueta no válida (1 a 30 caracteres)"`, `"Máximo 10 etiquetas por archivo"`; 404 `{"ok": false, "error": "No existe el archivo X"}`.

- [ ] **Step 1: Test que falla** `tests/test_organizar.py` (esqueleto de `tests/test_mandar_pantallas.py`, puerto 8126; sembrar 3 items en `content.json` y uno ya con `folder:"Verano"`, `tags:["Oferta"]`). Comprobaciones: (1) `{ids:[A,B], folder:"Tienda"}` → `changed 2` y ambos con `folder == "Tienda"`; (2) `addTags:["rebajas","Nuevo"]` en A → tags `["rebajas","Nuevo"]`; añadir `"REBAJAS"` después no duplica y `changed == 0`; (3) equivalencia: `folder:"verano"` sobre B reutiliza `"Verano"` del item sembrado; `addTags:["oferta"]` reutiliza `"Oferta"`; (4) `folder:null` quita la clave `folder`; (5) `removeTags:["nuevo"]` quita sin importar mayúsculas; (6) no-cambio (misma carpeta) → 200, `changed 0`, `rev` igual; (7) id inexistente → 404 y rev igual y nada modificado; (8) carpeta de 41 car., etiqueta de 31, 11 etiquetas, `ids:[]`, petición sin ninguna acción, `folder:5` → 400 con rev igual; (9) sin token → 401.
- [ ] **Step 2:** `py tests/test_organizar.py` falla.
- [ ] **Step 3: Implementar** (validar forma y límites antes del `with`; dentro, comprobar ids → 404 por excepción; calcular `changed` comparando antes/después por item; si 0, salir por excepción sin guardar; `notify_all()` si >0). Función auxiliar `_clave_nombre(s)` (minúsculas + sin diacríticos con `unicodedata`) y un mapa de grafías existentes construido de todos los items.
- [ ] **Step 4:** `py tests/test_organizar.py` OK; siguen OK `tests/test_mandar_pantallas.py`, `tests/test_libreria_info.py`, `tests/test_borrar_archivo.py`.
- [ ] **Step 5: Commit** `feat: carpetas y etiquetas, ruta organize`.

---

### Task 2: Panel — filtros, ficha y acciones en bloque

**Files:**
- Modify: `admin.html` (`filtrarOrdenar` y su test; HTML de la barra `.lib-bar`; `renderLibrary`; `abrirFicha`; barra `#lib-selbar`; diálogo pequeño reutilizable); `CHANGELOG.md` (entrada 1.0.50: añadir carpetas y etiquetas a la existente, sin publicar)
- Test: `tests/organizar.test.js` (y no romper `tests/libreria-filtro.test.js`)

**Interfaces:**
- Consumes: `POST /api/organize` (Task 1), `filtrarOrdenar`, `normalizarTexto`, `esc`, `toast`, `loadAll`, `libSel`, el patrón de la ficha y del diálogo `#mp-dlg` de la pieza 3.
- Produces: `filtrarOrdenar(items, info, {texto, tipo, orden, carpeta, etiquetas})` — `carpeta`: `undefined|"todas"` (sin filtro), `"__sin__"` (items sin carpeta) o nombre (comparación con `normalizarTexto`); `etiquetas`: lista (el item debe tener todas, comparación con `normalizarTexto`). `texto` también busca en carpeta y etiquetas. Función pura `listasDeOrganizacion(items) -> {carpetas: [..], etiquetas: [..]}` (únicas por `normalizarTexto`, ordenadas con `localeCompare("es")`), dentro del mismo bloque puro de marcadores.

- [ ] **Step 1: Tests que fallan** `tests/organizar.test.js` (carga por marcadores `// ── Librería: filtrar y ordenar`…`// ── fin de filtrar y ordenar`, como `tests/libreria-filtro.test.js`): filtro por carpeta (nombre, `"__sin__"`, `"todas"`, sin acentos), por una y por dos etiquetas (AND), texto que encuentra por carpeta y por etiqueta, `listasDeOrganizacion` sin duplicados y orden `es`.
- [ ] **Step 2:** `node --test tests/organizar.test.js` falla.
- [ ] **Step 3: Implementar** el bloque puro y la interfaz: desplegable `#lib-carpeta` y fila de chips `#lib-tags` en la barra (estado en `libFiltro.carpeta`, `libFiltro.etiquetas`; se reconstruyen en cada `renderLibrary` conservando la selección y descartando elementos que ya no existan); carpeta en la miniatura bajo el nombre; ficha con «Carpeta» (desplegable con existentes, «Sin carpeta», «Nueva carpeta…» que pide el nombre en el campo/`prompt`) y «Etiquetas» (chips con ✕ y campo + Enter); la barra de selección gana «Poner en carpeta…» y «Añadir etiqueta…» (diálogos pequeños reutilizando el estilo de `#mp-dlg`). Todas las acciones llaman a `/api/organize`, muestran el error del servidor en un toast y tras éxito hacen `await loadAll()`.
- [ ] **Step 4: Comprobar en navegador** (servidor temporal puerto 8127, contraseña de prueba creada en el alta local del servidor temporal, ids con comilla simple, carpeta con `&`): crear carpeta desde la ficha, asignar en bloque a 2 seleccionados, añadir etiqueta, filtrar por carpeta y por etiqueta, quitar etiqueta con ✕, «Sin carpeta». Parar servidor, borrar temporal, viewport a desktop.
- [ ] **Step 5:** `node --test tests/*.test.js` y los Python de librería/mandar/organizar en verde.
- [ ] **Step 6: Commit** `feat: carpetas y etiquetas en la Librería`.
