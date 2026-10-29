# Subida robusta de archivos — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir archivos a la Librería en bruto y por trozos, con progreso real, comprobación del tipo por contenido, aviso claro de fallos y sin cargar el archivo entero en RAM.

**Architecture:** Ruta nueva `POST /api/upload-raw?name=…` en `server.py` que escribe el cuerpo a `uploads/*.part` por trozos de 1 MB y lo renombra al validar. El panel (`admin.html`) sube con `XMLHttpRequest` desde una función única `subirArchivos` que usan Librería y Paquetes. `/api/upload` (base64) se conserva.

**Tech Stack:** Python stdlib (`ThreadingHTTPServer`), JS sin dependencias, tests como scripts (`python tests/test_*.py`) y `node --test`.

## Global Constraints

Del spec `docs/superpowers/specs/2026-10-29-subida-robusta-design.md`:

- Todo por IP local: sin nube ni web.
- Tipo por contenido: JPG, PNG, GIF, WEBP, MP4/MOV (`ftyp`), WEBM (EBML). Todo lo demás se rechaza.
- Ajuste `upload_max_mb` en `config.json`, por defecto 2048, editable en Ajustes.
- Debe quedar libre en disco al menos tamaño + 500 MB.
- Mensajes de error en español que dicen el motivo.
- Una subida cortada no deja `.part`; al arrancar se limpian los `.part` huérfanos.
- `/api/upload` (base64) no cambia.
- Tests: scripts independientes con servidor real en puerto propio (puertos usados: 8107–8117; este plan usa **8118**).
- Todo el texto de la interfaz, comentarios y commits en español.

---

### Task 1: Servidor — `/api/upload-raw`

**Files:**
- Modify: `server.py` (constantes y funciones junto a `UPLOAD_DIR`/`contenido_en_edicion`; limpieza de `.part` tras `os.makedirs(UPLOAD_DIR…)` en la línea ~144; ruta en `do_POST` antes del chequeo `length > MAX_BODY_BYTES`, ~línea 2143)
- Create: `tests/test_subida_raw.py`

**Interfaces:**
- Produces:
  - `detectar_tipo(cabecera: bytes) -> str | None` (`"image"`, `"video"` o `None`)
  - `class SubidaRechazada(Exception)` con `.codigo: int` y `.mensaje: str`
  - `guardar_subida_raw(lector, length: int, name: str) -> dict` (el `item` añadido al contenido: `{"id","name","type","src","size"}`)
  - Ruta `POST /api/upload-raw?name=<nombre>` → `200 {"ok":true,"item":{…}}` o `{"ok":false,"error":"…"}` con códigos 400/413/415/507.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_subida_raw.py`:

```python
"""
Subida en bruto: POST /api/upload-raw.

El archivo llega como cuerpo, se escribe a disco por trozos en un .part y solo
se renombra al validar. Una subida rechazada o cortada no deja nada.

Ejecutar:
    python tests/test_subida_raw.py
"""
import hashlib, http.client, json, os, shutil, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8118
TOKEN = "token-de-pruebas-0123456789"
MAX_MB = 40

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def peticion(metodo, ruta, cuerpo=None, token=TOKEN, cabeceras=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    h = dict(cabeceras or {})
    if token: h["X-SignalOS-Token"] = token
    c.request(metodo, ruta, body=cuerpo, headers=h)
    r = c.getresponse()
    datos = r.read()
    c.close()
    try: return r.status, json.loads(datos or b"{}")
    except ValueError: return r.status, {}


def subir(nombre, datos, token=TOKEN):
    from urllib.parse import quote
    return peticion("POST", "/api/upload-raw?name=" + quote(nombre), datos, token,
                    {"Content-Type": "application/octet-stream"})


def a_medias(nombre, declarar, enviar):
    """Declara `declarar` bytes, manda `enviar` y cierra el socket."""
    from urllib.parse import quote
    s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
    s.sendall((f"POST /api/upload-raw?name={quote(nombre)} HTTP/1.1\r\nHost: x\r\n"
               f"X-SignalOS-Token: {TOKEN}\r\nContent-Type: application/octet-stream\r\n"
               f"Content-Length: {declarar}\r\n\r\n").encode() + enviar)
    s.close()


def declarar_de_mas(nombre, declarar):
    """Declara un tamaño y NO manda cuerpo: el servidor debe rechazar por la cabecera."""
    from urllib.parse import quote
    s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
    s.sendall((f"POST /api/upload-raw?name={quote(nombre)} HTTP/1.1\r\nHost: x\r\n"
               f"X-SignalOS-Token: {TOKEN}\r\nContent-Type: application/octet-stream\r\n"
               f"Content-Length: {declarar}\r\n\r\n").encode())
    s.settimeout(10)
    resp = s.recv(4096).decode("latin-1")
    s.close()
    return int(resp.split(" ", 2)[1])


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_raw_")
    proc = None
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        cfg = json.load(open(os.path.join(work, "config.json")))
        cfg["upload_max_mb"] = MAX_MB
        json.dump(cfg, open(os.path.join(work, "config.json"), "w"))
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        up = os.path.join(work, "uploads")
        os.makedirs(up, exist_ok=True)
        open(os.path.join(up, "9999_huerfano.mp4.part"), "wb").write(b"resto de una subida vieja")
        proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=work,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/auth-status", timeout=1); break
            except Exception: pass

        fallos += comprobar("al arrancar se limpia el .part huérfano",
                            not os.path.exists(os.path.join(up, "9999_huerfano.mp4.part")))

        cod, r = subir("logo.png", PNG)
        fallos += comprobar("PNG correcto -> 200 y tipo image",
                            cod == 200 and r.get("item", {}).get("type") == "image", f"{cod} {r}")
        item = r.get("item", {})
        fallos += comprobar("el archivo existe con su tamaño",
                            os.path.getsize(os.path.join(up, item.get("id", "x"))) == len(PNG))
        _, contenido = peticion("GET", "/api/content")
        fallos += comprobar("queda en la Librería", any(i["id"] == item.get("id") for i in contenido.get("items", [])))

        cod, r = subir("clip.mp4", MP4)
        fallos += comprobar("MP4 -> video", cod == 200 and r["item"]["type"] == "video", f"{cod} {r}")
        cod, r = subir("clip.webm", WEBM)
        fallos += comprobar("WEBM -> video", cod == 200 and r["item"]["type"] == "video", f"{cod} {r}")

        antes = sorted(os.listdir(up))
        cod, r = subir("falso.png", b"esto no es una imagen, es texto" * 10)
        fallos += comprobar("texto disfrazado de .png -> 415", cod == 415 and "imagen" in r.get("error", ""), f"{cod} {r}")
        cod, r = subir("foto.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
        fallos += comprobar("HEIC (ftyp de imagen) no se toma por vídeo -> 415", cod == 415, f"{cod} {r}")
        cod, r = subir("vacio.png", b"")
        fallos += comprobar("archivo vacío -> 400", cod == 400, f"{cod} {r}")
        fallos += comprobar("lo rechazado no deja archivos", sorted(os.listdir(up)) == antes)

        grande = PNG + os.urandom(30 * 1024 * 1024)
        cod, r = subir("grande.png", grande)
        fallos += comprobar("30 MB suben enteros",
                            cod == 200 and os.path.getsize(os.path.join(up, r["item"]["id"])) == len(grande), f"{cod} {r}")
        h = hashlib.sha256(open(os.path.join(up, r["item"]["id"]), "rb").read()).hexdigest()
        fallos += comprobar("y sin alterar un byte", h == hashlib.sha256(grande).hexdigest())

        antes = sorted(os.listdir(up))
        fallos += comprobar(f"más que el máximo ({MAX_MB} MB) -> 413 sin leer el cuerpo",
                            declarar_de_mas("enorme.png", (MAX_MB + 1) * 1024 * 1024) == 413)

        a_medias("cortado.png", 5 * 1024 * 1024, PNG + b"\x00" * (1024 * 1024))
        time.sleep(1.5)
        fallos += comprobar("subida cortada a mitad: sin .part ni archivo", sorted(os.listdir(up)) == antes,
                            str(sorted(set(os.listdir(up)) - set(antes))))
        _, contenido = peticion("GET", "/api/content")
        fallos += comprobar("ni elemento en la Librería", not any(i["name"] == "cortado.png" for i in contenido.get("items", [])))

        cod, _ = subir("sin_permiso.png", PNG, token=None)
        fallos += comprobar("sin sesión -> 401", cod == 401, str(cod))
        fallos += comprobar("y no se guarda nada", not any("sin_permiso" in n for n in os.listdir(up)))

        import base64
        cod, r = peticion("POST", "/api/upload", json.dumps(
            {"name": "viejo.png", "type": "image", "data": base64.b64encode(PNG).decode(), "size": len(PNG)}).encode(),
            cabeceras={"Content-Type": "application/json"})
        fallos += comprobar("el /api/upload antiguo sigue funcionando", cod == 200 and r.get("ok"), f"{cod} {r}")
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_subida_raw" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `py tests/test_subida_raw.py`
Expected: varios `FALLO` (la ruta `/api/upload-raw` aún no existe: 404/401 en lugar de 200/415/413).

- [ ] **Step 3: Implementar en `server.py`**

3a. Junto a `contenido_en_edicion()` (después de esa función) añadir:

```python
# ── Subida de archivos en bruto ─────────────────────────────────────────────
# El archivo llega como cuerpo de la petición y se escribe a disco por trozos:
# la memoria usada no depende de su tamaño (con base64 un vídeo de 300 MB
# ocupaba ~400 MB en el navegador y otro tanto aquí).
SUBIDA_TROZO = 1024 * 1024
SUBIDA_MARGEN_DISCO = 500 * 1024 * 1024
SUBIDA_MAX_MB_DEFECTO = 2048
_subida_lock = threading.Lock()

class SubidaRechazada(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje

def detectar_tipo(cab):
    """'image' / 'video' / None, mirando los primeros bytes (no la extensión
    ni lo que diga el navegador)."""
    if cab[:3] == b"\xff\xd8\xff": return "image"                      # JPEG
    if cab[:8] == b"\x89PNG\r\n\x1a\n": return "image"
    if cab[:6] in (b"GIF87a", b"GIF89a"): return "image"
    if cab[:4] == b"RIFF" and cab[8:12] == b"WEBP": return "image"
    if cab[4:8] == b"ftyp":
        # HEIC/AVIF también empiezan por ftyp y son imágenes que la TV no abre.
        if cab[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"avif"): return None
        return "video"                                                  # MP4 / MOV
    if cab[:4] == b"\x1a\x45\xdf\xa3": return "video"                  # WEBM
    return None

def _espacio_legible(n):
    return f"{n // (1024**3)} GB" if n >= 1024**3 else f"{n // (1024**2)} MB"

def guardar_subida_raw(lector, length, name):
    """Lee `length` bytes de `lector` (por trozos) y los guarda como archivo de
    la Librería. Lanza SubidaRechazada con el motivo si no se puede."""
    try:
        maximo_mb = int(load_config().get("upload_max_mb", SUBIDA_MAX_MB_DEFECTO) or SUBIDA_MAX_MB_DEFECTO)
    except (TypeError, ValueError):
        maximo_mb = SUBIDA_MAX_MB_DEFECTO
    if length <= 0:
        raise SubidaRechazada(400, "El archivo está vacío")
    if length > maximo_mb * 1024 * 1024:
        raise SubidaRechazada(413, f"Pasa del máximo de {maximo_mb} MB por archivo")
    libre = shutil.disk_usage(UPLOAD_DIR).free
    if libre < length + SUBIDA_MARGEN_DISCO:
        raise SubidaRechazada(507, f"No cabe: quedan {_espacio_legible(libre)} libres en el disco")
    nombre = os.path.basename(str(name).replace("\\", "/")).strip() or "archivo"
    primero = lector.read(min(SUBIDA_TROZO, length))
    tipo = detectar_tipo(primero)
    if not tipo:
        raise SubidaRechazada(415, "No es una imagen ni un vídeo que se pueda mostrar "
                                   "(vale JPG, PNG, GIF, WEBP, MP4, MOV o WEBM)")
    # Primer número libre y el .part reservado a la vez: dos subidas simultáneas
    # no pueden elegir el mismo nombre.
    with _subida_lock:
        idx = len(os.listdir(UPLOAD_DIR))
        while (os.path.exists(os.path.join(UPLOAD_DIR, f"{idx:04d}_{nombre}"))
               or os.path.exists(os.path.join(UPLOAD_DIR, f"{idx:04d}_{nombre}.part"))):
            idx += 1
        filename = f"{idx:04d}_{nombre}"
        destino = os.path.join(UPLOAD_DIR, filename)
        parcial = destino + ".part"
        open(parcial, "xb").close()
    recibido = len(primero)
    try:
        with open(parcial, "wb") as f:
            f.write(primero)
            while recibido < length:
                trozo = lector.read(min(SUBIDA_TROZO, length - recibido))
                if not trozo:
                    raise SubidaRechazada(400, "La subida se cortó antes de terminar")
                f.write(trozo)
                recibido += len(trozo)
        os.replace(parcial, destino)
    except BaseException:
        try: os.remove(parcial)
        except OSError: pass
        raise
    item = {"id": filename, "name": nombre, "type": tipo,
            "src": f"/uploads/{filename}", "size": recibido}
    with contenido_en_edicion() as content:
        content.setdefault("items", []).append(item)
    return item

class _Lector:
    """Cuenta lo leído para saber, si se rechaza, cuánto cuerpo queda sin leer."""
    def __init__(self, rfile):
        self.rfile = rfile
        self.leido = 0
    def read(self, n):
        d = self.rfile.read(n)
        self.leido += len(d)
        return d
```

3b. Tras `os.makedirs(UPLOAD_DIR, exist_ok=True)` (línea ~144) añadir:

```python
# Restos de subidas que se cortaron con el servidor apagado.
for _n in os.listdir(UPLOAD_DIR):
    if _n.endswith(".part"):
        try: os.remove(os.path.join(UPLOAD_DIR, _n))
        except OSError: pass
```

3c. En `Handler`, junto a `do_POST`, añadir el método:

```python
    def _subida_raw(self, parsed, length):
        """POST /api/upload-raw?name=... El cuerpo es el archivo. La sesión ya se
        comprobó en do_POST."""
        nombre = (parse_qs(parsed.query).get("name", [""])[0])
        lector = _Lector(self.rfile)
        try:
            item = guardar_subida_raw(lector, length, nombre)
            codigo, cuerpo = 200, {"ok": True, "item": item}
        except SubidaRechazada as e:
            codigo, cuerpo = e.codigo, {"ok": False, "error": e.mensaje}
            sin_leer = length - lector.leido
            if 0 < sin_leer <= 8 * 1024 * 1024:
                while sin_leer > 0:                 # pequeño: se vacía y la respuesta llega limpia
                    d = self.rfile.read(min(SUBIDA_TROZO, sin_leer))
                    if not d: break
                    sin_leer -= len(d)
            elif sin_leer > 0:
                self.close_connection = True        # grande: no se lee, se corta
        except Exception as e:
            codigo, cuerpo = 500, {"ok": False, "error": f"Error del servidor: {e}"}
            self.close_connection = True
        self.send_response(codigo); self.send_header("Content-Type", "application/json")
        if self.close_connection: self.send_header("Connection", "close")
        self.cors(); self.end_headers()
        self.wfile.write(json.dumps(cuerpo).encode())
```

3d. En `do_POST`, justo **antes** de `if length > MAX_BODY_BYTES:` (después del bloque `if path in POST_PUBLICOS and length > MAX_BODY_PUBLICO`) añadir:

```python
        # La subida en bruto se lee por trozos, no se carga en RAM: no le
        # aplica MAX_BODY_BYTES (manda upload_max_mb).
        if path == "/api/upload-raw":
            self._subida_raw(parsed, length)
            return
```

- [ ] **Step 4: Ejecutar y comprobar que pasa**

Run: `py tests/test_subida_raw.py`
Expected: todas las líneas `ok` y `OK test_subida_raw`.

- [ ] **Step 5: Regresión del servidor y commit**

Run: `for t in tests/test_*.py; do py "$t" >/dev/null 2>&1 || echo "FALLA $t"; done`
Expected: sin líneas `FALLA`.

```bash
git add server.py tests/test_subida_raw.py
git commit -m "feat: subida de archivos en bruto por trozos (/api/upload-raw)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Panel — `subirArchivos` con progreso real

**Files:**
- Modify: `admin.html` (reemplazar `handleUpload`/`handlePkgUpload`, línea ~1778–1825; añadir CSS y bloque marcado; campo `upload_max_mb` en Ajustes)
- Create: `tests/subida-archivos.test.js`

**Interfaces:**
- Consumes: ruta `POST /api/upload-raw?name=` de la Task 1 (`200 {"ok":true,"item"}` / `{"ok":false,"error"}`).
- Produces (dentro del bloque marcado `// ── Subida de archivos` … `// ── fin de la subida`, sin DOM):
  - `resumenSubida(resultados) -> {subidos:number, fallidos:number, texto:string, hayError:boolean}`; cada resultado es `{ok, nombre, item?, error?, cancelado?}`
  - `subirUno(file, nuevoXHR, alProgreso, ctl) -> Promise<resultado>`; `alProgreso(fraccion0a1)`; `ctl.abort()` cancela
  - `async subirArchivos(files, nuevoXHR, ganchos) -> resultados[]`; `ganchos = {alEmpezar(i,total,file), alProgreso(i,fraccion), alTerminar(i,resultado), cancelado()}`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/subida-archivos.test.js`:

```js
/**
 * Subida de archivos del panel: progreso real, un fallo no para el resto y el
 * resumen no dice «subido» de lo que el servidor no confirmó.
 *
 * Ejecutar:  node --test tests/subida-archivos.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Subida de archivos";
const FIN = "// ── fin de la subida";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) throw new Error("No se encuentra el bloque de subida en admin.html");
  const ctx = { JSON, Object, Array, Promise, encodeURIComponent, Math, String };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

// XHR falso: responde según el nombre del archivo.
function fabricaXHR(respuestas) {
  return () => {
    const x = {
      upload: {}, status: 0, responseText: "", _url: "",
      open(_m, url) { this._url = url; },
      setRequestHeader() {},
      abort() { this.onabort && this.onabort(); },
      send(file) {
        const r = respuestas[file.name] || { status: 200, cuerpo: { ok: true, item: { id: "1_" + file.name, name: file.name } } };
        setImmediate(() => {
          if (r.red) return this.onerror();
          this.upload.onprogress && this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
          this.status = r.status; this.responseText = JSON.stringify(r.cuerpo);
          this.onload();
        });
      },
    };
    return x;
  };
}

test("resumenSubida cuenta subidos y fallidos con el motivo", () => {
  const { resumenSubida } = cargar();
  const r = resumenSubida([
    { ok: true, nombre: "a.png" }, { ok: true, nombre: "b.png" },
    { ok: false, nombre: "c.txt", error: "No es una imagen ni un vídeo" },
  ]);
  assert.strictEqual(r.subidos, 2);
  assert.strictEqual(r.fallidos, 1);
  assert.strictEqual(r.hayError, true);
  assert.match(r.texto, /2 subidos/);
  assert.match(r.texto, /1 falló/);
  assert.match(r.texto, /c\.txt/);
  assert.match(r.texto, /No es una imagen/);
});

test("resumenSubida sin fallos no habla de errores", () => {
  const { resumenSubida } = cargar();
  const r = resumenSubida([{ ok: true, nombre: "a.png" }]);
  assert.strictEqual(r.hayError, false);
  assert.match(r.texto, /1 subido/);
  assert.doesNotMatch(r.texto, /falló/);
});

test("resumenSubida: todo cancelado no es un error", () => {
  const { resumenSubida } = cargar();
  const r = resumenSubida([{ ok: false, nombre: "a.mp4", error: "Cancelado", cancelado: true }]);
  assert.strictEqual(r.hayError, false);
  assert.match(r.texto, /cancel/i);
});

test("subirUno: éxito devuelve el item del servidor", async () => {
  const { subirUno } = cargar();
  const r = await subirUno({ name: "a.png" }, fabricaXHR({}), () => {}, {});
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.item.id, "1_a.png");
});

test("subirUno: rechazo del servidor trae su motivo", async () => {
  const { subirUno } = cargar();
  const xhr = fabricaXHR({ "x.png": { status: 415, cuerpo: { ok: false, error: "No es una imagen ni un vídeo" } } });
  const r = await subirUno({ name: "x.png" }, xhr, () => {}, {});
  assert.strictEqual(r.ok, false);
  assert.match(r.error, /No es una imagen/);
});

test("subirUno: se perdió la red", async () => {
  const { subirUno } = cargar();
  const r = await subirUno({ name: "x.png" }, fabricaXHR({ "x.png": { red: true } }), () => {}, {});
  assert.strictEqual(r.ok, false);
  assert.match(r.error, /conexión/);
});

test("subirUno informa del progreso como fracción", async () => {
  const { subirUno } = cargar();
  const visto = [];
  await subirUno({ name: "a.png" }, fabricaXHR({}), f => visto.push(f), {});
  assert.deepStrictEqual(visto, [0.5]);
});

test("subirUno: ctl.abort cancela y lo marca", async () => {
  const { subirUno } = cargar();
  const ctl = {};
  const xhr = () => {
    const x = { upload: {}, open() {}, setRequestHeader() {}, send() {}, abort() { this.onabort(); } };
    return x;
  };
  const p = subirUno({ name: "a.mp4" }, xhr, () => {}, ctl);
  ctl.abort();
  const r = await p;
  assert.strictEqual(r.cancelado, true);
  assert.strictEqual(r.ok, false);
});

test("subirArchivos: un fallo no detiene los demás y se avisa de cada uno", async () => {
  const { subirArchivos } = cargar();
  const xhr = fabricaXHR({ "b.txt": { status: 415, cuerpo: { ok: false, error: "No es una imagen ni un vídeo" } } });
  const eventos = [];
  const res = await subirArchivos(
    [{ name: "a.png" }, { name: "b.txt" }, { name: "c.png" }], xhr,
    { alEmpezar: (i, t) => eventos.push("E" + i + "/" + t), alProgreso() {},
      alTerminar: (i, r) => eventos.push("T" + i + (r.ok ? "ok" : "mal")), cancelado: () => false });
  assert.deepStrictEqual(res.map(r => r.ok), [true, false, true]);
  assert.deepStrictEqual(eventos, ["E0/3", "T0ok", "E1/3", "T1mal", "E2/3", "T2ok"]);
});

test("subirArchivos: si se cancela, no empieza los siguientes", async () => {
  const { subirArchivos } = cargar();
  let cancelar = false;
  const res = await subirArchivos(
    [{ name: "a.png" }, { name: "b.png" }, { name: "c.png" }], fabricaXHR({}),
    { alEmpezar() {}, alProgreso() {}, alTerminar: () => { cancelar = true; }, cancelado: () => cancelar });
  assert.strictEqual(res.length, 1);
});
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `node --test tests/subida-archivos.test.js`
Expected: FAIL con «No se encuentra el bloque de subida en admin.html».

- [ ] **Step 3: Implementar en `admin.html`**

3a. Reemplazar `handleUpload` y `handlePkgUpload` (y conservar `toB64` solo si algo más lo usa; comprobarlo con `grep -n "toB64" admin.html`: si queda sin uso, borrarlo) por este bloque. Borrar de la línea `// ── Library` hasta antes de `async function deleteItem` el código viejo de ambas funciones y poner:

```js
// ── Subida de archivos
// Se envía el archivo en bruto con XMLHttpRequest (da el progreso real) y de
// uno en uno, para no saturar el mini PC. Solo se dice «subido» de lo que el
// servidor confirmó.
function resumenSubida(res){
  const ok=res.filter(r=>r.ok).length;
  const cancel=res.filter(r=>r.cancelado).length;
  const mal=res.filter(r=>!r.ok&&!r.cancelado);
  let texto=ok+(ok===1?" subido":" subidos");
  if(mal.length) texto+=", "+mal.length+(mal.length===1?" falló":" fallaron")+": "+
    mal.map(r=>r.nombre+" ("+(r.error||"error")+")").join("; ");
  if(cancel) texto+=(ok||mal.length?", ":"")+"cancelado"+(cancel>1?"s":"");
  return {subidos:ok,fallidos:mal.length,texto,hayError:mal.length>0};
}
function subirUno(f,nuevoXHR,alProgreso,ctl){
  return new Promise(resolve=>{
    const x=nuevoXHR();
    x.open("POST","/api/upload-raw?name="+encodeURIComponent(f.name));
    x.setRequestHeader("Content-Type","application/octet-stream");
    x.upload.onprogress=e=>{ if(e.lengthComputable&&e.total) alProgreso(e.loaded/e.total); };
    x.onload=()=>{
      let d={}; try{ d=JSON.parse(x.responseText); }catch(e){}
      if(x.status===200&&d.ok) resolve({ok:true,nombre:f.name,item:d.item});
      else resolve({ok:false,nombre:f.name,error:d.error||("Error "+x.status)});
    };
    x.onerror=()=>resolve({ok:false,nombre:f.name,error:"Se perdió la conexión con el servidor"});
    x.onabort=()=>resolve({ok:false,nombre:f.name,error:"Cancelado",cancelado:true});
    if(ctl) ctl.abort=()=>x.abort();
    x.send(f);
  });
}
async function subirArchivos(files,nuevoXHR,g){
  const res=[];
  for(let i=0;i<files.length;i++){
    if(g.cancelado()) break;
    g.alEmpezar(i,files.length,files[i]);
    const r=await subirUno(files[i],nuevoXHR,fr=>g.alProgreso(i,fr),g.ctl||{});
    g.alTerminar(i,r);
    res.push(r);
  }
  return res;
}
// ── fin de la subida

// Una fila por archivo dentro de `cont`, con barra, porcentaje y estado.
function filaSubida(cont,nombre){
  const fila=document.createElement("div");fila.className="sub-fila";
  fila.innerHTML=`<div class="sub-nom"></div><div class="sub-barra"><div class="sub-relleno"></div></div><div class="sub-est">En cola</div>`;
  fila.querySelector(".sub-nom").textContent=nombre;
  cont.appendChild(fila);
  const rel=fila.querySelector(".sub-relleno"),est=fila.querySelector(".sub-est");
  return {
    progreso(fr){ rel.style.width=Math.round(fr*100)+"%"; est.textContent=Math.round(fr*100)+"%"; },
    fin(r){
      fila.classList.add(r.ok?"sub-ok":(r.cancelado?"sub-can":"sub-mal"));
      rel.style.width=r.ok?"100%":rel.style.width;
      est.textContent=r.ok?"✓ Subido":(r.error||"Error");
    }
  };
}
// Sube lo elegido y devuelve los items que el servidor confirmó. `cont` es el
// contenedor de filas y `btnCancelar` el botón que aborta la subida en curso.
async function subirConPanel(files,cont,btnCancelar){
  const arr=Array.from(files); if(!arr.length) return [];
  cont.innerHTML="";cont.classList.add("show");
  const filas=arr.map(f=>filaSubida(cont,f.name));
  const ctl={};let cancelado=false;
  if(btnCancelar){btnCancelar.style.display="";btnCancelar.onclick=()=>{cancelado=true;if(ctl.abort)ctl.abort();};}
  const res=await subirArchivos(arr,()=>new XMLHttpRequest(),{
    ctl,cancelado:()=>cancelado,
    alEmpezar(){}, alProgreso:(i,fr)=>filas[i].progreso(fr), alTerminar:(i,r)=>filas[i].fin(r)});
  if(btnCancelar) btnCancelar.style.display="none";
  const s=resumenSubida(res);
  toast(s.texto,s.hayError);
  return res.filter(r=>r.ok).map(r=>r.item);
}
async function handleUpload(files){
  await subirConPanel(files,document.getElementById("uprog-lista"),document.getElementById("uprog-cancel"));
  document.getElementById("fi").value="";
  await loadAll();
}
// Sube contenido directamente desde la página de Paquetes y lo añade al paquete en edición.
// El archivo queda también en la Librería (reutilizable), pero sin el paso manual de ir allí.
async function handlePkgUpload(files){
  const arr=Array.from(files); if(!arr.length)return;
  const btn=document.getElementById("pkg-upload-btn");
  btn.disabled=true;
  const added=await subirConPanel(arr,document.getElementById("pkg-uprog-lista"),document.getElementById("pkg-uprog-cancel"));
  await loadAll();                       // refresca la librería con lo nuevo
  added.forEach(item=>{                  // auto-añadir al paquete en construcción
    if(!pkgSelection.some(x=>x.id===item.id))
      pkgSelection.push({id:item.id,duration:pkgDefaultDur(item)});
  });
  renderPkgPicker(); renderPkgSelected();
  btn.disabled=false;
  document.getElementById("pkg-fi").value="";
}
```

3b. En el HTML de Librería, reemplazar el bloque `<div class="uprog" id="uprog">…</div>` (líneas ~420–423) por:

```html
  <div class="uprog" id="uprog">
    <div id="uprog-lista" class="sub-lista"></div>
    <button class="btn btn-ghost btn-sm" id="uprog-cancel" style="display:none;margin-top:6px"><i class="fa-solid fa-xmark"></i> Cancelar subida</button>
  </div>
```

y la clase `uprog` debe mostrarse siempre que tenga filas: ver CSS (3d). En la página de Paquetes, justo después de la línea con `<input type="file" id="pkg-fi" …>` y su `</div>` de cierre (la fila que contiene el botón «Subir nuevo al paquete»), añadir:

```html
    <div id="pkg-uprog-lista" class="sub-lista" style="margin-bottom:8px"></div>
    <button class="btn btn-ghost btn-sm" id="pkg-uprog-cancel" style="display:none;margin-bottom:8px"><i class="fa-solid fa-xmark"></i> Cancelar subida</button>
```

3c. Cambiar el texto de ayuda `JPG · PNG · GIF · WEBP · MP4 · WEBM · MOV` (zona de arrastre) a `JPG · PNG · GIF · WEBP · MP4 · WEBM · MOV — se sube de uno en uno, con progreso`.

3d. CSS: junto a las reglas `.uprog` existentes (buscar con `grep -n "^\.uprog" admin.html`) añadir:

```css
.sub-lista{display:none;flex-direction:column;gap:6px}
.sub-lista.show{display:flex}
.sub-fila{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,2fr) 120px;gap:10px;align-items:center;font-size:12px}
.sub-nom{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub-barra{height:6px;background:var(--s3);border-radius:3px;overflow:hidden}
.sub-relleno{height:100%;width:0;background:var(--accent);transition:width .15s}
.sub-est{color:var(--muted);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub-ok .sub-est{color:var(--ok,#3ecf8e)}
.sub-mal .sub-est{color:#ef6a6a}
.sub-mal .sub-relleno{background:#ef6a6a}
@media (max-width:600px){.sub-fila{grid-template-columns:1fr;gap:4px}.sub-est{text-align:left}}
```

Si `.uprog` oculta su contenido con `display:none` salvo `.show`, la lista sigue mostrándose porque `handleUpload` ya añade `.show` a `#uprog-lista`; añadir también `document.getElementById("uprog").classList.add("show")` al principio de `handleUpload`.

3e. Ajuste del máximo. En la tarjeta «Copia de seguridad» **no**; añadir una tarjeta nueva justo **antes** de `<div class="card">\n    <div class="card-title">Copia de seguridad</div>` (línea ~908):

```html
  <div class="card">
    <div class="card-title">Subida de archivos</div>
    <p style="font-size:12px;color:var(--muted);margin-bottom:12px;line-height:1.6">
      Tamaño máximo de cada imagen o vídeo que se sube a la Librería. Los vídeos largos
      pesan mucho; si no caben, se avisa con el motivo.
    </p>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <input class="finput" id="set-upload-max" type="number" min="10" max="20480" style="width:120px"> <span style="font-size:12px;color:var(--muted)">MB por archivo</span>
      <button class="btn btn-accent" onclick="guardarUploadMax()"><i class="fa-solid fa-floppy-disk"></i> Guardar</button>
    </div>
  </div>
```

Cargar el valor junto a `document.getElementById("set-copia-ext").value=…` (línea ~3915):

```js
      document.getElementById("set-upload-max").value=cfg.upload_max_mb||2048;
```

y añadir junto a `guardarCopiaExterna`:

```js
async function guardarUploadMax(){
  const mb=parseInt(document.getElementById("set-upload-max").value,10);
  if(!(mb>=10&&mb<=20480)){ toast("Pon un número entre 10 y 20480",true); return; }
  try{
    const r=await fetch("/api/config",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({upload_max_mb:mb})});
    toast(r.ok?"Máximo guardado ✓":"No se pudo guardar",!r.ok);
  }catch(e){ toast("Error al guardar",true); }
}
```

- [ ] **Step 4: Ejecutar y comprobar que pasa**

Run: `node --test tests/subida-archivos.test.js`
Expected: `pass 10`, `fail 0`.

- [ ] **Step 5: Todas las pruebas y commit**

Run: `node --test tests/*.test.js 2>&1 | grep -E "^ℹ (pass|fail)"` → `fail 0`.
Run: `for t in tests/test_*.py; do py "$t" >/dev/null 2>&1 || echo "FALLA $t"; done` → sin líneas `FALLA`.

```bash
git add admin.html tests/subida-archivos.test.js
git commit -m "feat: el panel sube con progreso real, de uno en uno y avisa de cada fallo

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Verificación visual, versión y entrega

**Files:**
- Modify: `CHANGELOG.md`, versión vía `tools/subir-version.ps1`
- Modify: `MANUAL.md` (frase en la sección de Librería, si existe; ver Step 1)

- [ ] **Step 1: Comprobar en un servidor de prueba**

Copiar el proyecto a una carpeta temporal del scratchpad (nunca ejecutar `server.py` desde el proyecto), arrancar en el puerto 8120, entrar con una contraseña de prueba y, desde la Librería, subir un PNG, un archivo `.txt` renombrado a `.png` y cancelar una subida. Comprobar con capturas/DOM:
- una fila por archivo con barra y porcentaje;
- el `.txt` sale en rojo con «No es una imagen ni un vídeo…»;
- el resumen del aviso dice «1 subido, 1 falló: …»;
- «Cancelar subida» aborta y no deja `.part` en `uploads/`.
Parar el servidor al terminar.

Si la ventana del navegador está oculta y las capturas fallan, comprobarlo con `javascript_tool` leyendo el DOM y decirlo en el informe.

- [ ] **Step 2: Versión y changelog**

Añadir al principio de `CHANGELOG.md` (debajo de la cabecera, antes de la versión más reciente) la entrada de la siguiente versión (la que corresponda tras la última de `package.json`):

```markdown
## 1.0.48 — 2026-10-29

### Mejorado

- **Subida de archivos más robusta.** Los archivos se envían directamente y por
  trozos, así que un vídeo grande ya no tumba el mini PC. Se ve una barra de
  progreso por archivo, se puede cancelar, y si algo falla el panel dice cuál y
  por qué (antes decía «subido» igualmente).
- El servidor comprueba que el archivo es de verdad una imagen o un vídeo, y que
  cabe en el disco. Nuevo ajuste «Subida de archivos» con el tamaño máximo.

---
```

Run: `powershell -ExecutionPolicy Bypass -File tools/subir-version.ps1 1.0.48`

- [ ] **Step 3: Suites completas y commit**

Run las dos suites (comandos de Task 2 Step 5) y `node --test tests/version-sync.test.js`.

```bash
git add -A
git commit -m "chore: versión 1.0.48 con la subida robusta de archivos

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Compilar**

```bash
powershell -ExecutionPolicy Bypass -File build_installer.ps1
(cd android && JAVA_HOME="C:/Program Files/Android/Android Studio/jbr" ./gradlew.bat assembleDebug -q)
powershell -ExecutionPolicy Bypass -File tools/preparar-entrega.ps1
```

Expected: «Instalador compilado correctamente» y `InTeks_Display_Setup_v1.0.48.exe` + `InTeks_Display_TV_v1.0.48.apk` en `Entregables\`. **No publicar en GitHub sin que Axel lo pida.**

---

## Auto-revisión

- **Cobertura del spec:** envío en bruto y `.part` atómico (T1), limpieza de huérfanos (T1 3b), tipo por contenido incl. HEIC (T1), tope `upload_max_mb` (T1 + ajuste en T2 3e), espacio en disco (T1, sin test automático: no se puede simular sin llenar un disco; se revisa leyendo el código), nombre y número libre (T1), rechazos con motivo (T1), sin sesión (T1), `/api/upload` antiguo (T1 test), progreso por archivo, uno a uno, resumen y cancelar (T2), Librería y Paquetes con la misma función (T2).
- **Desviación del spec:** la prueba «la memoria no crece con un archivo grande» no se automatiza (medir memoria de un proceso es poco fiable). Se sustituye por el test de 30 MB íntegros con hash y por la lectura por trozos en `guardar_subida_raw`, que es lo que garantiza que no se carga en RAM. Se avisa de esto en el informe final.
- **Tipos y nombres:** `detectar_tipo`, `SubidaRechazada`, `guardar_subida_raw`, `_Lector`, `resumenSubida`, `subirUno`, `subirArchivos`, `subirConPanel`, `filaSubida` coinciden entre tareas y tests.
