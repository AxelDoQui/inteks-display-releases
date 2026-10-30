# Librería más útil Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la Librería tenga buscador, filtro, orden, datos por archivo, ficha lateral con «dónde se usa», renombrar y borrar con aviso.

**Architecture:** El servidor calcula tamaño, fecha y usos (`GET /api/library-info`), renombra (`POST /api/rename`) y al borrar limpia playlists y paquetes. El panel (`admin.html`) tiene una función pura `filtrarOrdenar` (testable en Node con el método de marcadores) y una ficha lateral.

**Tech Stack:** Python stdlib (`server.py`), HTML/JS vanilla (`admin.html`), tests Python con servidor real y `node --test`.

Spec: `docs/superpowers/specs/2026-10-30-libreria-util-design.md`.

## Global Constraints

- Todo en español (textos de UI, comentarios, mensajes de commit).
- Todo por IP local: sin nube, sin web, sin dependencias nuevas.
- Rutas nuevas exigen sesión o token (`self.require_auth()` en GET; el POST ya pasa por la autenticación general salvo `POST_PUBLICOS`: no añadir ahí).
- Escrituras de `content.json` solo con `contenido_en_edicion()`.
- Renombrar cambia solo `name` (1–120 caracteres tras `strip`), nunca el archivo en disco.
- Borrar: se quita el id de `content["screens"][*]["playlist"]` y de `content["packages"][*]["itemIds"]`.
- Cada test usa su puerto propio: usar 8121 y 8122 (8107–8120 ya están ocupados).
- Commits terminan con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

---

### Task 1: Servidor — información, renombrar y borrar limpiando

**Files:**
- Modify: `server.py` (helper `usos_de_items` junto a `expandir_paquetes` ~línea 890; GET `/api/library-info` justo antes de `/api/screens` ~línea 2017; POST `/api/rename` y cambio en `/api/delete` ~línea 2773)
- Test: `tests/test_libreria_info.py`

**Interfaces:**
- Produces: `usos_de_items(content, registro_pantallas) -> {item_id: [{"kind": "screen"|"package", "id": str, "name": str}]}`.
- Produces: `GET /api/library-info` → `{item_id: {"uses": [...], "size": int?, "created": int?}}` (`size`/`created` solo si el item tiene `src` y el archivo existe; `created` = mtime en segundos).
- Produces: `POST /api/rename` `{id, name}` → `{"ok": true}`; 400 `{"ok": false, "error": "Nombre no válido (1 a 120 caracteres)"}`; 404 `{"ok": false, "error": "No existe ese archivo"}`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_libreria_info.py` (mismo esqueleto que `tests/test_borrar_archivo.py`: copiar `peticion`, `comprobar`, arranque del servidor; puerto 8121). Sembrar los datos escribiendo ficheros ANTES de arrancar el servidor:

```python
PORT = 8121
# dentro de main(), tras copiar los archivos y escribir admin.json:
up = os.path.join(work, "uploads"); os.makedirs(up, exist_ok=True)
open(os.path.join(up, "0001_a.png"), "wb").write(PNG)
open(os.path.join(up, "0002_b.png"), "wb").write(PNG + b"\x00" * 100)
json.dump({"items": [
    {"id": "0001_a.png", "type": "image", "name": "a.png", "src": "/uploads/0001_a.png"},
    {"id": "0002_b.png", "type": "image", "name": "b.png", "src": "/uploads/0002_b.png"},
    {"id": "fx1", "type": "fx", "name": "Divisas"}],
  "screens": {"s1": {"mode": "independent", "playlist": [{"id": "0001_a.png", "duration": 10}]}},
  "packages": [{"id": "p1", "name": "Escaparate", "itemIds": ["0001_a.png", "fx1"]}],
  "rev": 0}, open(os.path.join(work, "content.json"), "w"))
json.dump({"s1": {"name": "Tienda Centro"}}, open(os.path.join(work, "screens.json"), "w"))
```

Comprobaciones (cada una con `comprobar(...)`):
1. `GET /api/library-info` → 200; `info["0001_a.png"]["size"] == len(PNG)`; `info["0002_b.png"]["size"] == len(PNG)+100`; `created` es int > 0; `fx1` no tiene `size`.
2. Usos de `0001_a.png`: contiene `{"kind":"screen","id":"s1","name":"Tienda Centro"}` y `{"kind":"package","id":"p1","name":"Escaparate"}`; `0002_b.png` tiene `uses == []`.
3. `GET /api/library-info` sin token → 401 (usar `http.client` sin cabecera de token).
4. `POST /api/rename {"id":"0002_b.png","name":"  Cartel nuevo  "}` → 200; luego `GET /api/content` muestra `name == "Cartel nuevo"` y el archivo `uploads/0002_b.png` sigue existiendo.
5. `rename` con `name: "   "` → 400; con 121 caracteres → 400; con id inexistente → 404.
6. `POST /api/delete {"id":"0001_a.png"}` → 200; en `GET /api/content`: la playlist de `s1` es `[]` y `packages[0].itemIds == ["fx1"]`; el archivo ya no está en `uploads/`.

Cabeceras de las peticiones POST: `{"Content-Type": "application/json"}` (el token lo añade `peticion`).

- [ ] **Step 2: Ejecutarlo y ver que falla**

Run: `py tests/test_libreria_info.py`
Expected: FALLO en las comprobaciones 1–6 (404 en las rutas nuevas).

- [ ] **Step 3: Implementar el helper**

En `server.py`, junto a `expandir_paquetes`:

```python
def usos_de_items(content, registro_pantallas):
    """Dónde se usa cada contenido: {id: [{"kind", "id", "name"}]}.

    Una pantalla usa un contenido si está directo en su playlist; un paquete,
    si está en sus itemIds. Las pantallas que usan un paquete no se cuentan
    aquí: el paquete ya sale en la lista.
    """
    usos = {}
    def anotar(item_id, kind, ident, nombre):
        lista = usos.setdefault(item_id, [])
        if not any(u["kind"] == kind and u["id"] == ident for u in lista):
            lista.append({"kind": kind, "id": ident, "name": nombre})
    for sid, scr in (content.get("screens") or {}).items():
        reg = registro_pantallas.get(sid) if isinstance(registro_pantallas, dict) else None
        nombre = (reg or {}).get("name") or sid if isinstance(reg, dict) or reg is None else sid
        for p in scr.get("playlist", []):
            if isinstance(p, dict) and p.get("type") != "package" and p.get("id"):
                anotar(p["id"], "screen", sid, nombre)
    for pkg in content.get("packages", []):
        for item_id in pkg.get("itemIds", []):
            anotar(item_id, "package", pkg.get("id", ""), pkg.get("name") or pkg.get("id", ""))
    return usos
```

(Simplificar la línea de `nombre` a: `nombre = (reg.get("name") if isinstance(reg, dict) else None) or sid`.)

- [ ] **Step 4: Implementar las rutas**

GET, antes de `if path == "/api/screens":` (mismo estilo de respuesta que esa ruta):

```python
        # ── API: datos de la Librería (tamaño, fecha y dónde se usa cada archivo)
        if path == "/api/library-info":
            if not self.require_auth(): return
            content = load_json(CONTENT_FILE)
            usos = usos_de_items(content, load_json(SCREENS_FILE))
            salida = {}
            for it in content.get("items", []):
                iid = it.get("id")
                if not iid: continue
                dato = {"uses": usos.get(iid, [])}
                if it.get("src"):
                    try:
                        st = os.stat(os.path.join(UPLOAD_DIR, os.path.basename(str(iid))))
                        dato["size"] = st.st_size
                        dato["created"] = int(st.st_mtime)
                    except OSError: pass
                salida[iid] = dato
            body = json.dumps(salida).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return
```

POST, antes de `/api/delete`:

```python
        # ── Renombrar un contenido (solo el nombre que se ve)
        if path == "/api/rename":
            try:
                d = json.loads(body)
                item_id = d["id"]
                nombre = str(d.get("name", "")).strip()
                if not nombre or len(nombre) > 120:
                    jresp(400, {"ok": False, "error": "Nombre no válido (1 a 120 caracteres)"}); return
                encontrado = False
                with contenido_en_edicion() as content:
                    for it in content.get("items", []):
                        if it.get("id") == item_id:
                            it["name"] = nombre; encontrado = True; break
                if not encontrado:
                    jresp(404, {"ok": False, "error": "No existe ese archivo"}); return
                notify_all()
                ok()
            except Exception as e: err(e)
            return
```

En `/api/delete`, tras el bucle de playlists añadir:

```python
                    # Y de los paquetes: un paquete con un id que ya no existe
                    # se reproduciría saltándose huecos.
                    for pkg in content.get("packages", []):
                        pkg["itemIds"] = [i for i in pkg.get("itemIds", []) if i != item_id]
```

Comprobar que `jresp` existe en `do_POST` (se usa en `/api/config`); si no, usar el patrón de respuesta que use `err`.

- [ ] **Step 5: Ejecutar los tests**

Run: `py tests/test_libreria_info.py` → todo `ok`, termina con `OK test_libreria_info`.
Run: `py tests/test_borrar_archivo.py` y `py tests/test_subida_raw.py` → siguen en OK.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_libreria_info.py
git commit -m "feat: library-info, rename y borrado que limpia paquetes

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Panel — lógica pura de filtro y orden

**Files:**
- Modify: `admin.html` (bloque nuevo justo antes de `function renderLibrary(){` ~línea 1949)
- Test: `tests/libreria-filtro.test.js`

**Interfaces:**
- Produces (globales del bloque): `filtrarOrdenar(items, info, {texto, tipo, orden}) -> items[]` y `formatoTamano(bytes) -> string`.
  - `tipo`: `"todos" | "image" | "video" | "otros"` (`otros` = ni image ni video).
  - `orden`: `"nuevos" | "nombre" | "tamano" | "usados"`.
  - `info` = respuesta de `/api/library-info` (puede ser `{}`).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/libreria-filtro.test.js` con la misma carga por marcadores que `tests/subida-archivos.test.js` (`INICIO = "// ── Librería: filtrar y ordenar"`, `FIN = "// ── fin de filtrar y ordenar"`, contexto `{ String, Array, Object, Math, Number }`). Datos:

```js
const items = [
  { id: "a", type: "image", name: "Cartel Verano.png" },
  { id: "b", type: "video", name: "spot.mp4" },
  { id: "c", type: "fx", name: "Divisas" },
  { id: "d", type: "image", name: "árbol.jpg" },
];
const info = {
  a: { size: 500, created: 100, uses: [{}, {}] },
  b: { size: 9000, created: 300, uses: [] },
  d: { size: 20, created: 200, uses: [{}] },
};
```

Casos (`node:test` + `assert.deepStrictEqual` sobre los ids): texto `"verano"` → `["a"]`; texto con mayúsculas/acentos `"ARBOL"` → `["d"]`; tipo `video` → `["b"]`; tipo `otros` → `["c"]`; orden `nuevos` → `["b","d","a","c"]` (sin fecha al final); orden `nombre` → `["d","a","c","b"]` según `localeCompare("es")`... **calcular el orden esperado con `localeCompare` de `es` sin acentos**: `árbol` < `Cartel` < `Divisas` < `spot` → `["d","a","c","b"]`; orden `tamano` → `["b","a","d","c"]`; orden `usados` → `["a","d","c","b"]` (empate entre `c` y `b` por nombre: «Divisas» antes que «spot»). `formatoTamano(0)` → `"0 B"`, `(1536)` → `"1,5 KB"`, `(48*1024*1024)` → `"48 MB"`, `(undefined)` → `""`.

- [ ] **Step 2: Ejecutarlo y ver que falla**

Run: `node --test tests/libreria-filtro.test.js`
Expected: FAIL («No se encuentra el bloque…»).

- [ ] **Step 3: Implementar el bloque**

```js
// ── Librería: filtrar y ordenar
function normalizarTexto(s){
  return String(s||"").normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase();
}
function formatoTamano(b){
  if(typeof b!=="number"||!isFinite(b)) return "";
  if(b<1024) return b+" B";
  const u=["KB","MB","GB"]; let v=b/1024, i=0;
  while(v>=1024&&i<u.length-1){v/=1024;i++;}
  const t=(v>=10||Math.abs(v-Math.round(v))<0.05)?String(Math.round(v)):v.toFixed(1).replace(".",",");
  return t+" "+u[i];
}
function filtrarOrdenar(items,info,opc){
  const o=opc||{}, texto=normalizarTexto(o.texto), tipo=o.tipo||"todos", orden=o.orden||"nuevos";
  const dato=id=>(info&&info[id])||{};
  let r=(items||[]).filter(it=>{
    if(texto&&normalizarTexto(it.name).indexOf(texto)===-1) return false;
    if(tipo==="image"||tipo==="video") return it.type===tipo;
    if(tipo==="otros") return it.type!=="image"&&it.type!=="video";
    return true;
  });
  const porNombre=(a,b)=>normalizarTexto(a.name).localeCompare(normalizarTexto(b.name),"es");
  const num=(v)=>typeof v==="number"?v:-1;
  r=r.slice().sort((a,b)=>{
    let d=0;
    if(orden==="nuevos") d=num(dato(b.id).created)-num(dato(a.id).created);
    else if(orden==="tamano") d=num(dato(b.id).size)-num(dato(a.id).size);
    else if(orden==="usados") d=((dato(b.id).uses||[]).length)-((dato(a.id).uses||[]).length);
    return d!==0?d:porNombre(a,b);
  });
  return r;
}
// ── fin de filtrar y ordenar
```

Ajustar `formatoTamano` si el test de `1536 → "1,5 KB"` o `48 MB` no sale exacto; el test manda.

- [ ] **Step 4: Ejecutar**

Run: `node --test tests/libreria-filtro.test.js tests/subida-archivos.test.js` → todo pasa.

- [ ] **Step 5: Commit**

```bash
git add admin.html tests/libreria-filtro.test.js
git commit -m "feat: filtrar y ordenar la Librería (lógica pura)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Panel — barra, miniaturas, ficha y borrado con aviso

**Files:**
- Modify: `admin.html` (HTML de `#page-library` ~línea 436; CSS junto a `.lib-*` ~línea 150; `loadAll` línea 1413; `renderLibrary`/`deleteItem` ~líneas 1944–1964)
- Modify: `CHANGELOG.md` (entrada nueva `1.0.49`)

**Interfaces:**
- Consumes: `filtrarOrdenar`, `formatoTamano` (Task 2); `GET /api/library-info`, `POST /api/rename`, `POST /api/delete` (Task 1).
- Produces: variables globales `libInfo={}`, `libFiltro={texto:"",tipo:"todos",orden:"nuevos"}`; funciones `loadLibInfo()`, `abrirFicha(id)`, `cerrarFicha()`, `renombrarItem(id)`, `deleteItem(id,e)` (reescrita).

- [ ] **Step 1: HTML de la barra y la ficha**

Sustituir el bloque `<div class="section-hdr" style="margin-top:16px">…</div>` de `#page-library` por:

```html
  <div class="section-hdr" style="margin-top:16px">
    <span class="section-lbl">ARCHIVOS</span>
    <span class="count-pill" id="lib-count">0</span>
  </div>
  <div class="lib-bar">
    <input type="search" id="lib-q" placeholder="Buscar por nombre…" oninput="libFiltro.texto=this.value;renderLibrary()">
    <select id="lib-tipo" onchange="libFiltro.tipo=this.value;renderLibrary()">
      <option value="todos">Todos</option><option value="image">Imágenes</option>
      <option value="video">Vídeos</option><option value="otros">Otros</option>
    </select>
    <select id="lib-orden" onchange="libFiltro.orden=this.value;renderLibrary()">
      <option value="nuevos">Más nuevos</option><option value="nombre">Nombre</option>
      <option value="tamano">Tamaño</option><option value="usados">Más usados</option>
    </select>
  </div>
```

(dejar el `<div class="lib-grid" id="lib-grid">` tal cual debajo). Añadir antes de `</body>` (junto a otros overlays) un `<div id="lib-ficha" class="lib-ficha" style="display:none"></div>`.

- [ ] **Step 2: CSS**

Junto a `.lib-*`:

```css
.lib-bar{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.lib-bar input,.lib-bar select{background:var(--s2);border:1px solid var(--b);color:inherit;border-radius:var(--r);padding:6px 8px;font-size:12px}
.lib-bar input{flex:1;min-width:160px}
.lib-meta{font-size:9px;color:var(--muted);padding:0 7px 5px}
.lib-uso{position:absolute;top:3px;left:3px;background:var(--accent);color:#fff;border-radius:8px;padding:0 6px;font-size:9px;line-height:16px}
.lib-dur{position:absolute;right:3px;bottom:26px;background:rgba(0,0,0,.75);color:#fff;border-radius:3px;padding:0 4px;font-size:9px}
.lib-ficha{position:fixed;top:0;right:0;bottom:0;width:min(380px,100vw);background:var(--s1,var(--s2));border-left:1px solid var(--b);z-index:900;padding:16px;overflow:auto;box-shadow:-8px 0 24px rgba(0,0,0,.35)}
.lib-ficha .prev{width:100%;aspect-ratio:16/9;background:#000;border-radius:var(--r);overflow:hidden;display:flex;align-items:center;justify-content:center;margin-bottom:12px}
.lib-ficha .prev img,.lib-ficha .prev video{width:100%;height:100%;object-fit:contain}
.lib-ficha dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12px;margin:0 0 12px}
.lib-ficha dt{color:var(--muted)}
.lib-ficha ul{margin:0 0 12px;padding-left:18px;font-size:12px}
```

- [ ] **Step 3: JS**

`loadAll`: sustituir `await Promise.all([loadContent(),loadScreens()]);` por `await Promise.all([loadContent(),loadScreens(),loadLibInfo()]);`.

Antes del bloque de la Task 2 (o justo después de `// ── fin de filtrar y ordenar`) añadir:

```js
let libInfo={};
let libFiltro={texto:"",tipo:"todos",orden:"nuevos"};
async function loadLibInfo(){try{const r=await fetch("/api/library-info");if(r.ok)libInfo=await r.json();}catch(e){}}
function fechaCorta(ts){return ts?new Date(ts*1000).toLocaleDateString("es-ES",{day:"2-digit",month:"2-digit",year:"numeric"}):"—";}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function duracionTxt(s){if(!isFinite(s))return"";const m=Math.floor(s/60),x=Math.round(s%60);return m+":"+String(x).padStart(2,"0");}
function resumenUsos(uses){
  const p=uses.filter(u=>u.kind==="screen").length,k=uses.filter(u=>u.kind==="package").length,t=[];
  if(p)t.push(p+" pantalla"+(p>1?"s":""));
  if(k)t.push(k+" paquete"+(k>1?"s":""));
  return t.join(" y ");
}
```

(Si `esc` ya existe en el fichero, no duplicarla: grep `function esc` antes.)

Reescribir `renderLibrary` para usar `filtrarOrdenar(content.items||[],libInfo,libFiltro)`:
- contador: `lista.length===total ? total : lista.length+" de "+total`;
- vacío: «Sin archivos» si no hay ninguno, «Nada coincide con el filtro» si hay pero ninguno pasa;
- cada tarjeta añade `.lib-meta` con `formatoTamano(info.size)` + `" · "` + tipo (extensión en mayúsculas del `src` o el tipo), `.lib-uso` con `"en uso · "+uses.length` si hay usos, y para vídeos un `<span class="lib-dur">` que se rellena en `loadedmetadata` del `<video>` de la miniatura con `duracionTxt(video.duration)`;
- `el.onclick=()=>abrirFicha(item.id)`; el botón de borrar mantiene `onclick="deleteItem('id',event)"` (ya hace `stopPropagation`). Usar `esc()` para `item.name` y `item.title` en el HTML.

Ficha:

```js
function cerrarFicha(){const f=document.getElementById("lib-ficha");f.style.display="none";f.innerHTML="";}
function abrirFicha(id){
  const it=(content.items||[]).find(i=>i.id===id); if(!it) return;
  const inf=libInfo[id]||{}, uses=inf.uses||[], f=document.getElementById("lib-ficha");
  let prev=`<i class="fa-solid ${typeIcon(it.type)}" style="font-size:40px;color:var(--muted)"></i>`;
  if(it.type==="image") prev=`<img src="${esc(it.src)}" alt="">`;
  else if(it.type==="video") prev=`<video src="${esc(it.src)}" controls preload="metadata"></video>`;
  const lista=uses.length
    ? "<ul>"+uses.map(u=>`<li>${u.kind==="screen"?"Pantalla":"Paquete"}: ${esc(u.name)}</li>`).join("")+"</ul>"
    : '<p style="font-size:12px;color:var(--muted);margin:0 0 12px">No está en ninguna pantalla ni paquete.</p>';
  f.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <strong style="font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(it.name)}</strong>
      <button class="btn btn-ghost btn-sm" onclick="cerrarFicha()"><i class="fa-solid fa-xmark"></i></button></div>
    <div class="prev">${prev}</div>
    <dl><dt>Tipo</dt><dd>${esc(it.type)}</dd><dt>Tamaño</dt><dd>${formatoTamano(inf.size)||"—"}</dd>
      <dt>Resolución</dt><dd id="fi-res">—</dd><dt>Duración</dt><dd id="fi-dur">—</dd>
      <dt>Subido</dt><dd>${fechaCorta(inf.created)}</dd></dl>
    <div class="section-lbl" style="margin-bottom:6px">DÓNDE SE USA</div>${lista}
    <div style="display:flex;gap:8px">
      <button class="btn btn-ghost btn-sm" onclick="renombrarItem('${esc(id)}')"><i class="fa-solid fa-pen"></i> Renombrar</button>
      <button class="btn btn-danger btn-sm" onclick="deleteItem('${esc(id)}')"><i class="fa-solid fa-trash"></i> Borrar</button></div>`;
  f.style.display="block";
  const m=f.querySelector(".prev img,.prev video"); if(!m) return;
  const poner=(w,h,d)=>{if(w&&h)document.getElementById("fi-res").textContent=w+"×"+h;if(d)document.getElementById("fi-dur").textContent=duracionTxt(d);};
  if(m.tagName==="IMG"){const r=()=>poner(m.naturalWidth,m.naturalHeight);m.complete?r():m.onload=r;}
  else m.onloadedmetadata=()=>poner(m.videoWidth,m.videoHeight,m.duration);
}
async function renombrarItem(id){
  const it=(content.items||[]).find(i=>i.id===id); if(!it) return;
  const nombre=prompt("Nombre nuevo (solo cambia el nombre que se ve):",it.name);
  if(nombre===null) return;
  const r=await fetch("/api/rename",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id,name:nombre})});
  if(!r.ok){let m="No se pudo renombrar";try{m=(await r.json()).error||m}catch(e){}toast(m,true);return;}
  await loadAll();toast("Renombrado");abrirFicha(id);
}
```

`deleteItem` reescrita (la `e` es opcional):

```js
async function deleteItem(id,e){
  if(e)e.stopPropagation();
  const it=(content.items||[]).find(i=>i.id===id);
  const uses=(libInfo[id]||{}).uses||[];
  const nombre=it?it.name:id;
  const msg=uses.length
    ? `«${nombre}» está en ${resumenUsos(uses)}: ${uses.map(u=>u.name).join(", ")}.\n\nSi lo borras, se quita también de ahí. ¿Borrar igualmente?`
    : `¿Borrar «${nombre}»?`;
  if(!confirm(msg)) return;
  const r=await fetch("/api/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id})});
  if(!r.ok){toast("No se pudo borrar",true);return;}
  cerrarFicha();await loadAll();toast("Eliminado");
}
```

Los sitios que hoy hacen `renderLibrary()` tras añadir contenido (líneas ~3087–3974) no recalculan `libInfo`: tras una subida (`subirConPanel`/`handleUpload`) debe llamarse `await loadLibInfo()` antes de `renderLibrary()`; revisar que `loadAll()` ya lo cubre (lo hace) y, si `handleUpload` usa `loadAll`, no hace falta nada más.

- [ ] **Step 4: Comprobar en el navegador**

Arrancar un servidor de pruebas en un directorio temporal en el puerto 8122 (copiando los archivos como hacen los tests, con un `content.json` sembrado como en la Task 1), abrir `http://127.0.0.1:8122/admin.html` en el navegador integrado con el token de admin, y comprobar a mano: buscador y filtros cambian la cuadrícula; la insignia «en uso» sale; la ficha se abre al pulsar, muestra resolución, enseña dónde se usa, Renombrar cambia el nombre, Borrar en uso muestra el aviso con nombres y, al confirmar, limpia las listas. Con `javascript_tool` si la captura falla (el panel del navegador a veces está oculto). Parar el servidor y restaurar el viewport a `desktop` al terminar.

- [ ] **Step 5: Ejecutar todos los tests relacionados**

Run: `py tests/test_libreria_info.py; py tests/test_borrar_archivo.py; py tests/test_subida_raw.py; node --test tests/*.test.js`
Expected: todos OK.

- [ ] **Step 6: CHANGELOG y commit**

Añadir en `CHANGELOG.md`, encima de la entrada 1.0.48, una entrada `1.0.49` con: buscador/filtro/orden, datos por archivo, ficha lateral con «dónde se usa», renombrar, borrar con aviso que limpia pantallas y paquetes. **No** subir la versión en los instaladores ni publicar: eso lo decide Axel.

```bash
git add admin.html CHANGELOG.md
git commit -m "feat: Librería con buscador, ficha, renombrar y borrar con aviso

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
