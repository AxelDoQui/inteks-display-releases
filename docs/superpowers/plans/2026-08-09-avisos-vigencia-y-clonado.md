# Avisos, vigencia y clonado — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que las cosas que hoy se rompen en silencio —una pantalla apagada, unas tasas viejas, un disco lleno, una promo caducada— se noten sin que nadie tenga que estar mirando el panel.

**Architecture:** Cinco tareas de menos a más difícil. Las tres primeras son cambios locales (una fusión de configuración, un dato más en `/api/info`, una función de clonado en el panel). La cuarta filtra la playlist por fechas en `/api/playlist`, el mismo embudo donde ya se expanden los paquetes. La quinta añade un hilo vigilante en el servidor que evalúa el estado cada minuto y avisa por Telegram; obliga a portar la lógica de horario a Python, y esa duplicación se defiende con un corpus de casos compartido entre las pruebas de JS y las de Python.

**Tech Stack:** Python 3 solo con la biblioteca estándar (`ThreadingHTTPServer`, `urllib.request`, `shutil.disk_usage`), HTML/CSS/JS a pelo sin paso de compilación, pruebas con `node --test` y scripts de Python que arrancan el servidor de verdad.

## Global Constraints

- **Sin dependencias nuevas.** Ni en el servidor (solo biblioteca estándar) ni en el navegador (no hay bundler ni npm: el proyecto no tiene ninguna dependencia).
- **Los identificadores internos no se renombran:** `signalos_screen_id`, `signalos_session`, `X-SignalOS-Token`, `SIGNALOS_DATA`. Renombrarlos desenlazaría todas las pantallas instaladas.
- **Nada que hable con fuera puede tumbar el servidor.** Telegram va con `timeout` y no lanza nunca. Si no hay token configurado, el servidor no contacta con nadie.
- **Ninguna pantalla se queda en negro por una regla nueva.** Ante la duda, se sigue mostrando lo último que había.
- **Comentarios y textos de interfaz en español**, como el resto del proyecto.
- **Secretos fuera de la copia de seguridad.** `admin.json` y `pin.json` no viajan; el token de Telegram vive en `config.json`, que **sí** viaja en la copia — hay que avisarlo en el panel.
- **Al terminar, subir de versión:** `powershell -File tools\subir-version.ps1 1.0.2`, anotar en `CHANGELOG.md` y recompilar.
- **Órdenes de prueba:** `npm test` para Node; `python tests/<archivo>.py` para cada suite de Python.

---

### Task 1: Guardar ajustes deja de borrar el resto de la configuración

`saveSettings` en el panel manda solo 5 claves y `/api/config` reemplaza el archivo entero. Guardar los ajustes borra `mdns_name` y `update_url`, y borraría el token de Telegram de la tarea 5. Esto va primero porque todo lo demás se apoya en que `config.json` no pierda cosas.

**Files:**
- Modify: `server.py` (bloque `if path == "/api/config"` del `do_POST`)
- Test: `tests/test_config_merge.py` (crear)

**Interfaces:**
- Consumes: `load_json`, `save_json`, `CONFIG_FILE`
- Produces: `POST /api/config` fusiona en vez de reemplazar

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_config_merge.py`:

```python
"""
Guardar los ajustes no puede borrar lo que el formulario no conoce.

El panel manda 5 claves (puerto, alternativo, nombre, autoarranque,
first_run) y el servidor hacia save_json del cuerpo entero: todo lo demas
-mdns_name, update_url, y manana el token de Telegram- desaparecia en
silencio la primera vez que alguien tocaba Ajustes y pulsaba Guardar.

Ejecutar:  python tests/test_config_merge.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8103
TOKEN = "tok-prueba-config"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_cfg_")
    datos = tempfile.mkdtemp(prefix="signalos_cfgd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(datos, "admin.json"), "w"))
    cfgpath = os.path.join(datos, "config.json")
    json.dump({"port": PORT, "port_fallback": 9000, "mdns_name": "signage",
               "installation_name": "Tienda Centro", "update_url": "https://ejemplo/v.json",
               "telegram_token": "no-me-borres", "autostart": True},
              open(cfgpath, "w"))

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def post(payload):
        r = urllib.request.Request(
            base + "/api/config", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN},
            method="POST")
        return json.load(urllib.request.urlopen(r, timeout=5))

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco")
            return 1

        # Exactamente lo que manda el formulario de Ajustes.
        post({"port": PORT, "port_fallback": 9000,
              "installation_name": "Tienda Norte", "autostart": False,
              "first_run": False})

        cfg = json.load(open(cfgpath))
        check(cfg.get("installation_name") == "Tienda Norte",
              "lo que se envia si se aplica")
        check(cfg.get("autostart") is False,
              "incluso cuando el valor nuevo es false")
        check(cfg.get("update_url") == "https://ejemplo/v.json",
              "update_url sobrevive")
        check(cfg.get("telegram_token") == "no-me-borres",
              "el token de Telegram sobrevive")
        check(cfg.get("mdns_name") == "signage",
              "mdns_name sobrevive")

        # Un cuerpo que no es un objeto no puede dejar la configuracion vacia.
        try:
            post([1, 2, 3])
        except Exception:
            pass
        cfg = json.load(open(cfgpath))
        check(cfg.get("port_fallback") == 9000,
              "un cuerpo invalido no destroza la configuracion")
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python tests/test_config_merge.py`
Expected: FALLA en `update_url sobrevive`, `el token de Telegram sobrevive` y `mdns_name sobrevive`.

- [ ] **Step 3: Implementar la fusión**

En `server.py`, sustituir el bloque del endpoint:

```python
        if path == "/api/config":
            try:
                d = json.loads(body)
                save_json(CONFIG_FILE, d)
                ok()
            except Exception as e: err(e)
            return
```

por:

```python
        if path == "/api/config":
            try:
                d = json.loads(body)
                if not isinstance(d, dict):
                    jresp(400, {"ok": False, "error": "Configuración no válida"}); return
                # Fusionar, NO reemplazar. El formulario de Ajustes solo conoce
                # cinco claves; si se guardara el cuerpo tal cual, todo lo demás
                # -mdns_name, update_url, el token de avisos- desaparecería en
                # silencio la primera vez que alguien pulsa Guardar.
                actual = load_json(CONFIG_FILE)
                actual.update(d)
                save_json(CONFIG_FILE, actual)
                ok()
            except Exception as e: err(e)
            return
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python tests/test_config_merge.py`
Expected: `TODO OK`.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_config_merge.py
git commit -m "fix: guardar los ajustes ya no borra el resto de la configuracion"
```

---

### Task 2: Aviso de disco casi lleno

**Files:**
- Modify: `server.py` (bloque `if path == "/api/info"` del `do_GET`)
- Modify: `admin.html` (tarjeta «Estado actual» de Ajustes, y `loadServerInfo`)
- Test: `tests/test_disco.py` (crear)

**Interfaces:**
- Consumes: `DATA_DIR`, `shutil` (ya importado)
- Produces: `estado_disco() -> dict` con las claves `libre_mb`, `total_mb`, `pct_usado`, `aviso`; `/api/info` lo devuelve bajo la clave `disk`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_disco.py`:

```python
"""
Espacio en disco.

Nada lo vigilaba. Cuando el disco de la tienda se llena fallan las subidas
y -peor- puede fallar la escritura de content.json y quedarse la
configuracion a medias. Es un desastre silencioso: no hay ningun sintoma
hasta que ya paso.

Ejecutar:  python tests/test_disco.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8104
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_disk_")
    datos = tempfile.mkdtemp(prefix="signalos_diskd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco")
            return 1

        info = json.load(urllib.request.urlopen(base + "/api/info", timeout=5))
        d = info.get("disk") or {}
        check(isinstance(d.get("libre_mb"), (int, float)) and d["libre_mb"] > 0,
              f"informa del espacio libre -> {d.get('libre_mb')} MB")
        check(isinstance(d.get("total_mb"), (int, float)) and d["total_mb"] >= d.get("libre_mb", 0),
              "y del total, que no puede ser menor que el libre")
        check(0 <= d.get("pct_usado", -1) <= 100,
              f"el porcentaje usado esta entre 0 y 100 -> {d.get('pct_usado')}")
        check(d.get("aviso") in (True, False),
              "dice si hay que avisar o no")
        # En la maquina de pruebas hay sitio de sobra; el aviso debe estar apagado.
        check(d.get("aviso") is False or d.get("pct_usado", 0) >= 90,
              "no avisa si hay espacio de sobra")
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python tests/test_disco.py`
Expected: FALLA en `informa del espacio libre` (la clave `disk` no existe).

- [ ] **Step 3: Implementar `estado_disco()`**

En `server.py`, justo antes de `def get_ip():`:

```python
DISCO_AVISO_PCT = 90

def estado_disco():
    """Espacio en la unidad donde viven los datos.

    Cuando el disco de la tienda se llena fallan las subidas y puede fallar
    la escritura de content.json, que es como perder la configuración. No
    hay ningún síntoma hasta que ya pasó, así que conviene avisar antes.

    Se mira DATA_DIR y no la carpeta del programa: los vídeos y las
    imágenes son lo que crece, y viven ahí.
    """
    try:
        uso = shutil.disk_usage(DATA_DIR)
    except OSError:
        return {"libre_mb": 0, "total_mb": 0, "pct_usado": 0, "aviso": False,
                "error": "no se pudo leer el disco"}
    pct = round((uso.used / uso.total) * 100) if uso.total else 0
    return {
        "libre_mb": round(uso.free / (1024 * 1024)),
        "total_mb": round(uso.total / (1024 * 1024)),
        "pct_usado": pct,
        "aviso": pct >= DISCO_AVISO_PCT,
    }
```

- [ ] **Step 4: Devolverlo en `/api/info` y avisar en el registro**

En `server.py`, dentro del bloque `if path == "/api/info":`, añadir la clave al diccionario `info`:

```python
                "pair_url_ip": url_for("/pair", host=ip),   # respaldo por IP (siempre funciona)
                "disk": estado_disco(),
```

(La línea `"pair_url_ip"` existía sin coma final por ser la última; ahora la lleva.)

Y avisarlo también en el arranque. Va **dentro** de `if __name__ == "__main__":`
(server.py:1560), justo antes de `try: srv.serve_forever()`, y por tanto
**indentado con cuatro espacios**. Fuera de ese bloque se ejecutaría también al
importar `server.py` desde los tests, que no es lo que se quiere:

```python
    _disco = estado_disco()
    if _disco.get("aviso"):
        log(f"  AVISO: disco al {_disco['pct_usado']}% "
            f"({_disco['libre_mb']} MB libres). Si se llena, fallaran las "
            f"subidas y puede corromperse la configuracion.")
        log("="*56)
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `python tests/test_disco.py`
Expected: `TODO OK`.

- [ ] **Step 6: Mostrarlo en el panel**

En `admin.html`, en la tarjeta «Estado actual» de Ajustes, después de la línea de la IP:

```html
      <div>Disco: <strong id="set-disk" style="color:var(--text)">—</strong></div>
```

Y en `loadServerInfo`, después de `if(elV) elV.textContent=info.version||"desconocida";`:

```js
      // Aviso de disco. Solo se pinta en rojo cuando de verdad urge: un
      // indicador siempre encendido deja de leerse a la semana.
      const elD=document.getElementById("set-disk");
      if(elD&&info.disk){
        const d=info.disk;
        elD.textContent=`${d.pct_usado}% usado · ${(d.libre_mb/1024).toFixed(1)} GB libres`;
        elD.style.color=d.aviso?"#f05050":"var(--text)";
        if(d.aviso){
          elD.textContent+=" ⚠ queda poco: fallarán las subidas";
        }
      }
```

- [ ] **Step 7: Commit**

```bash
git add server.py admin.html tests/test_disco.py
git commit -m "feat: avisar cuando el disco de la tienda se esta llenando"
```

---

### Task 3: Duplicar una pantalla

**Files:**
- Modify: `admin.html` (nueva función `clonarConfigPantalla` y `duplicarPantalla`, y un botón en `renderScreens`)
- Test: `tests/clonar-pantalla.test.js` (crear)

**Interfaces:**
- Consumes: los globales `content` y `regScreens` del panel; `saveScreensConfig()`
- Produces: `clonarConfigPantalla(cfg) -> object` (copia profunda lista para otra pantalla); `duplicarPantalla(sid)`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/clonar-pantalla.test.js`:

```js
/**
 * Duplicar una pantalla.
 *
 * Montar la segunda caja de una tienda significaba rehacer a mano la
 * playlist, el horario, la rotacion y la transicion. La copia de seguridad
 * clona una tienda entera; esto es el grano fino.
 *
 * Lo delicado es que NO se copia: lo que ata una pantalla a otra. Clonar el
 * emparejamiento de un videowall dejaria dos pantallas diciendo que son la
 * mitad izquierda de la misma pared.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Duplicar una pantalla";
const FIN = "// ── fin del clonado";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) {
    throw new Error("No se encuentra el bloque de clonado en admin.html " +
                    `(marcadores "${INICIO}" .. "${FIN}").`);
  }
  const ctx = { JSON, Object, Array };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

const completa = () => ({
  mode: "independent",
  rotation: 90,
  transition: "slide",
  transition_ms: 600,
  standby_image: "/uploads/cerrado.png",
  always_on: false,
  schedule: { lunes: { enabled: true, start: "09:00", end: "21:00" },
              holidays: [{ date: "2026-12-25", enabled: false }] },
  playlist: [{ id: "it_1", type: "image", src: "/uploads/a.png", duration: 8 },
             { type: "package", pkg_id: "pkg_1" }],
});

test("se copia la playlist entera, paquetes incluidos", () => {
  const c = cargar().clonarConfigPantalla(completa());
  assert.strictEqual(c.playlist.length, 2);
  assert.strictEqual(c.playlist[0].id, "it_1");
  assert.strictEqual(c.playlist[1].pkg_id, "pkg_1",
    "la referencia al paquete se mantiene: sigue siendo un grupo vivo");
});

test("se copian horario, rotacion y transicion", () => {
  const c = cargar().clonarConfigPantalla(completa());
  assert.strictEqual(c.rotation, 90);
  assert.strictEqual(c.transition, "slide");
  assert.strictEqual(c.transition_ms, 600);
  assert.strictEqual(c.schedule.lunes.start, "09:00");
  assert.strictEqual(c.schedule.holidays[0].date, "2026-12-25",
    "los festivos tambien viajan");
  assert.strictEqual(c.standby_image, "/uploads/cerrado.png");
});

test("la copia es profunda: tocar una no cambia la otra", () => {
  // Sin copia profunda, editar la playlist de la nueva editaria la original.
  // Es el fallo mas facil de cometer aqui y el mas dificil de ver luego.
  const original = completa();
  const c = cargar().clonarConfigPantalla(original);
  c.playlist[0].duration = 99;
  c.schedule.lunes.start = "07:00";
  assert.strictEqual(original.playlist[0].duration, 8);
  assert.strictEqual(original.schedule.lunes.start, "09:00");
});

test("un videowall se clona como pantalla independiente", () => {
  // Copiar mode:"wall" con su partner dejaria dos pantallas diciendo que son
  // la mitad izquierda de la misma pared.
  const c = cargar().clonarConfigPantalla({
    mode: "wall", wall_pos: "left", partner: "Caja-2", playlist: [],
  });
  assert.strictEqual(c.mode, "independent");
  assert.strictEqual(c.partner, undefined);
  assert.strictEqual(c.wall_pos, undefined);
});

test("una pantalla vacia se clona sin reventar", () => {
  const c = cargar().clonarConfigPantalla({});
  assert.deepStrictEqual(JSON.parse(JSON.stringify(c.playlist)), []);
  assert.strictEqual(c.mode, "independent");
});

test("no se arrastra el estado de conexion", () => {
  // connected y last_seen describen a un televisor concreto, no a una
  // configuracion. Copiarlos haria aparecer la nueva como si ya estuviera en
  // linea sin que nadie la haya enchufado.
  const c = cargar().clonarConfigPantalla({ connected: true, last_seen: 123, playlist: [] });
  assert.strictEqual(c.connected, undefined);
  assert.strictEqual(c.last_seen, undefined);
});
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test`
Expected: FALLA con `No se encuentra el bloque de clonado en admin.html`.

- [ ] **Step 3: Implementar el clonado**

En `admin.html`, justo antes de `// ── Screens` (donde está `function renderScreens()`):

```js
// ── Duplicar una pantalla ──────────────────────────────────────────────────
// Montar la segunda caja de una tienda obligaba a rehacer a mano la playlist,
// el horario, la rotacion y la transicion.
function clonarConfigPantalla(cfg){
  // Copia profunda. Sin ella, editar la playlist de la nueva editaria tambien
  // la de la original: mismo array, dos nombres. Es el fallo mas facil de
  // cometer aqui y el mas dificil de ver despues.
  const c=JSON.parse(JSON.stringify(cfg||{}));
  // Lo que ata esta pantalla a un televisor o a otra pantalla NO se copia.
  delete c.connected; delete c.last_seen; delete c.id;
  delete c.partner; delete c.wall_pos;
  c.mode="independent";
  if(!Array.isArray(c.playlist)) c.playlist=[];
  return c;
}
// ── fin del clonado ────────────────────────────────────────────────────────

async function duplicarPantalla(sid){
  const origen=(content.screens||{})[sid];
  if(!origen){ toast("Esa pantalla no tiene nada que copiar",true); return; }
  const sugerido=sid+" (copia)";
  const nombre=(prompt("Nombre de la pantalla nueva:", sugerido)||"").trim();
  if(!nombre) return;
  const existentes=new Set([...Object.keys(regScreens||{}),
                            ...Object.keys(content.screens||{})]);
  if(existentes.has(nombre)){ toast(`Ya existe una pantalla llamada «${nombre}»`,true); return; }
  content.screens[nombre]=clonarConfigPantalla(origen);
  await saveScreensConfig();
  renderScreens(); updateStats();
  toast(`«${nombre}» creada como copia de «${sid}» ✓`);
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test`
Expected: PASAN los 6 tests de `clonar-pantalla.test.js`.

- [ ] **Step 5: Añadir el botón**

En `admin.html`, dentro de `<div class="sc-actions">` de `renderScreens`, antes del botón de copiar enlace:

```html
          <button class="btn btn-ghost btn-sm" onclick="duplicarPantalla('${sid}')" title="Crear otra pantalla igual que esta"><i class="fa-solid fa-clone"></i></button>
```

- [ ] **Step 6: Comprobar a mano**

1. Arrancar: `python server.py --port 9000`, abrir `http://localhost:9000/admin.html`.
2. En una pantalla con playlist y horario, pulsar el botón de clonar.
3. Aceptar el nombre sugerido.

Expected: aparece la pantalla nueva con el mismo número de elementos. Al abrir su Playlist, la transición y el contenido coinciden; al cambiar una duración en la copia, la original **no** cambia.

- [ ] **Step 7: Commit**

```bash
git add admin.html tests/clonar-pantalla.test.js
git commit -m "feat: duplicar una pantalla con toda su configuracion"
```

---

### Task 4: Vigencia por fechas en la playlist

**Files:**
- Modify: `server.py` (nueva `filtrar_vigentes`, aplicada en `/api/playlist` después de `expandir_paquetes`)
- Modify: `admin.html` (`renderPlList`: dos campos de fecha por fila; `renderScreens`: aviso de «todo caducado»)
- Test: `tests/test_vigencia.py` (crear)

**Interfaces:**
- Consumes: `expandir_paquetes(playlist, content)` de `/api/playlist`
- Produces: `filtrar_vigentes(playlist, hoy) -> list`, con `hoy` en formato `"YYYY-MM-DD"`. Los elementos llevan `desde` y `hasta` opcionales, ambos `"YYYY-MM-DD"` o cadena vacía.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_vigencia.py`:

```python
"""
Vigencia por fechas.

Un contenido se quedaba en la pantalla hasta que alguien lo quitaba a mano.
Ahora una promo puede entrar y salir sola.

La regla importante es la ultima: si TODO ha caducado no se deja la pantalla
en negro. Una promo vieja en el escaparate es malo; un escaparate apagado es
peor, y encima no se nota que es un fallo de configuracion.

Ejecutar:  python tests/test_vigencia.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8105
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def item(id_, desde="", hasta=""):
    return {"id": id_, "type": "image", "src": f"/uploads/{id_}.png",
            "duration": 8, "desde": desde, "hasta": hasta}


def main():
    app = tempfile.mkdtemp(prefix="signalos_vig_")
    datos = tempfile.mkdtemp(prefix="signalos_vigd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    cpath = os.path.join(datos, "content.json")

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def guardar(playlist):
        json.dump({"items": [], "packages": [],
                   "screens": {"TV": {"mode": "independent", "playlist": playlist}}},
                  open(cpath, "w"))

    def ids():
        r = urllib.request.urlopen(f"{base}/api/playlist?screen=TV", timeout=5)
        return [x.get("id") for x in json.load(r)["playlist"]]

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco")
            return 1

        # Sin fechas, todo se ve. El comportamiento de siempre no cambia.
        guardar([item("a"), item("b")])
        check(ids() == ["a", "b"], f"sin fechas se ve todo -> {ids()}")

        # Caducado y todavia no empezado se ocultan.
        guardar([item("a"), item("viejo", hasta="2020-01-01"),
                 item("futuro", desde="2099-01-01")])
        check(ids() == ["a"], f"lo caducado y lo futuro no se ven -> {ids()}")

        # Los limites son inclusivos: el ultimo dia todavia se ve.
        hoy = time.strftime("%Y-%m-%d")
        guardar([item("hoy_fin", hasta=hoy)])
        check(ids() == ["hoy_fin"], "el ultimo dia de vigencia todavia se ve")
        guardar([item("hoy_ini", desde=hoy)])
        check(ids() == ["hoy_ini"], "el primer dia de vigencia ya se ve")

        # Solo un extremo.
        guardar([item("desde_ya", desde="2020-01-01"),
                 item("hasta_lejos", hasta="2099-01-01")])
        check(ids() == ["desde_ya", "hasta_lejos"],
              "con un solo extremo tambien funciona")

        # LA REGLA QUE IMPORTA: si todo ha caducado, no se apaga la pantalla.
        guardar([item("v1", hasta="2020-01-01"), item("v2", hasta="2020-02-01")])
        check(ids() == ["v1", "v2"],
              f"si TODO ha caducado se sigue mostrando -> {ids()}")

        # Una fecha con formato raro no puede ocultar contenido.
        guardar([item("raro", hasta="no-es-una-fecha"), item("b")])
        check(ids() == ["raro", "b"],
              "una fecha invalida se ignora en vez de esconder el contenido")

        # Una playlist vacia sigue vacia, sin inventarse nada.
        guardar([])
        check(ids() == [], "una playlist vacia sigue vacia")
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python tests/test_vigencia.py`
Expected: FALLA en `lo caducado y lo futuro no se ven` (hoy no se filtra nada).

- [ ] **Step 3: Implementar `filtrar_vigentes`**

En `server.py`, justo después de la función `expandir_paquetes`:

```python
def filtrar_vigentes(playlist, hoy):
    """Quita lo caducado y lo que aún no ha empezado.

    Las fechas van en las claves `desde` y `hasta` de cada elemento, en
    formato YYYY-MM-DD, y ambas son inclusivas: el último día todavía se ve.
    Comparar cadenas ISO funciona porque ese formato ordena igual como texto
    que como fecha; nada de parsear.

    Regla de oro: si el filtro se lo lleva TODO, se devuelve la lista sin
    filtrar. Una promo vieja en el escaparate es malo, pero un escaparate
    apagado es peor y encima no se distingue de una avería.
    """
    def valida(f):
        f = str(f or "").strip()
        # 10 caracteres y guiones en su sitio. Una fecha mal escrita se ignora
        # en vez de esconder contenido sin que nadie sepa por qué.
        return f if (len(f) == 10 and f[4] == "-" and f[7] == "-"
                     and f[:4].isdigit() and f[5:7].isdigit()
                     and f[8:].isdigit()) else ""

    def vigente(it):
        if not isinstance(it, dict):
            return True
        desde, hasta = valida(it.get("desde")), valida(it.get("hasta"))
        if desde and hoy < desde: return False
        if hasta and hoy > hasta: return False
        return True

    out = [it for it in (playlist or []) if vigente(it)]
    if not out and playlist:
        return list(playlist)
    return out
```

- [ ] **Step 4: Aplicarlo en `/api/playlist`**

En `server.py`, dentro del bloque `if path == "/api/playlist":`, sustituir:

```python
            resuelta = expandir_paquetes(scr.get("playlist", []), content)
```

por:

```python
            # Primero se expanden los paquetes y DESPUÉS se filtra por fechas:
            # así una promo caducada que vive dentro de un paquete también
            # desaparece. Al revés, el paquete entraría entero sin mirar.
            resuelta = filtrar_vigentes(
                expandir_paquetes(scr.get("playlist", []), content),
                time.strftime("%Y-%m-%d"))
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `python tests/test_vigencia.py`
Expected: `TODO OK`.

- [ ] **Step 6: Campos de fecha en el editor de playlist**

En `admin.html`, en `renderPlList`, en la rama de los elementos normales (la que construye `durControl`), añadir antes de `el.innerHTML=`:

```js
    const fechas=`<input type="date" class="dur-inp" style="width:120px" value="${item.desde||''}" `+
      `onchange="updVigencia('${sid}',${i},'desde',this.value)" title="Empieza a verse (vacío = ya)">`+
      `<input type="date" class="dur-inp" style="width:120px" value="${item.hasta||''}" `+
      `onchange="updVigencia('${sid}',${i},'hasta',this.value)" title="Deja de verse (vacío = nunca)">`;
```

Y en la plantilla de `el.innerHTML`, insertar `${fechas}` justo antes de `${durControl}`.

Después de la función `renderPlList`, añadir:

```js
function updVigencia(sid,i,campo,valor){
  const pl=(content.screens[sid]||{}).playlist||[];
  if(!pl[i]) return;
  pl[i][campo]=valor||"";
  renderPlList(sid);
}

// Cuantos elementos de una playlist estan vigentes hoy. Se usa para avisar en
// la tarjeta de la pantalla; el servidor hace su propio filtro al servirla.
function vigentesHoy(pl){
  const hoy=new Date().toISOString().slice(0,10);
  const ok=f=>{const s=String(f||"").trim(); return /^\d{4}-\d{2}-\d{2}$/.test(s)?s:"";};
  return (pl||[]).filter(it=>{
    const d=ok(it.desde), h=ok(it.hasta);
    if(d&&hoy<d) return false;
    if(h&&hoy>h) return false;
    return true;
  }).length;
}
```

- [ ] **Step 7: Avisar en la tarjeta cuando todo está caducado**

En `admin.html`, en `renderScreens`, sustituir la línea del contador de elementos:

```js
        <div style="font-size:11px;color:var(--muted);margin-bottom:8px">${contarPlaylist(pl)} elemento(s)</div>
```

por:

```js
        <div style="font-size:11px;color:var(--muted);margin-bottom:8px">${contarPlaylist(pl)} elemento(s)${
          (pl.length && vigentesHoy(pl)===0)
            ? ' · <span style="color:#f0a050">todo caducado, se sigue mostrando</span>' : ''}</div>
```

- [ ] **Step 8: Comprobar a mano**

1. Abrir la Playlist de una pantalla con dos contenidos.
2. Poner a uno `hasta` = ayer. Guardar.
3. Abrir el player de esa pantalla.

Expected: solo se reproduce el otro. Si pones ambos con `hasta` = ayer, **se siguen reproduciendo los dos** y la tarjeta de la pantalla dice «todo caducado, se sigue mostrando».

- [ ] **Step 9: Commit**

```bash
git add server.py admin.html tests/test_vigencia.py
git commit -m "feat: vigencia por fechas en los contenidos de la playlist"
```

---

### Task 5: Avisos por Telegram

La más grande. Obliga a portar la lógica de horario a Python, porque el aviso solo debe salir si la pantalla **debería** estar encendida. Esa duplicación se defiende con un corpus de casos compartido entre las pruebas de JS y las de Python: si alguien cambia una y no la otra, los tests lo cazan.

**Files:**
- Create: `tests/casos-horario.json` (corpus compartido)
- Modify: `tests/schedule.test.js` (leer el corpus además de sus casos propios)
- Create: `tests/test_horario_python.py`
- Create: `tests/test_avisos.py`
- Modify: `server.py` (`pantalla_activa`, `enviar_telegram`, hilo vigilante, endpoint `/api/alert-test`)
- Modify: `admin.html` (tarjeta de avisos en Ajustes)

**Interfaces:**
- Consumes: `load_json`, `save_json`, `SCREENS_FILE`, `CONTENT_FILE`, `load_config`, `log`, `expandir_paquetes`, `APP_VERSION`
- Produces:
  - `pantalla_activa(cfg, ahora) -> bool` — `cfg` es la configuración de la pantalla (`content["screens"][sid]`), `ahora` un `time.struct_time`
  - `enviar_telegram(texto) -> bool` — nunca lanza
  - `revisar_avisos()` — una pasada del vigilante; devuelve la lista de mensajes enviados
  - `POST /api/alert-test` → `{ok, enviado}`

- [ ] **Step 1: Crear el corpus de casos compartido**

Crear `tests/casos-horario.json`:

```json
{
  "_comentario": "Casos de horario que DEBEN dar el mismo resultado en player.html (JS) y en server.py (Python). La logica esta duplicada por necesidad: el player decide si pintar y el servidor decide si avisar de una pantalla caida. Este archivo es lo que impide que se separen. dia: 0=domingo..6=sabado.",
  "casos": [
    {"nombre": "diurno dentro del intervalo",
     "cuando": {"dia": 1, "hora": 12, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": true, "start": "08:00", "end": "20:00"}},
     "activa": true},

    {"nombre": "diurno antes de abrir",
     "cuando": {"dia": 1, "hora": 7, "minuto": 59, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": true, "start": "08:00", "end": "20:00"}},
     "activa": false},

    {"nombre": "nocturno antes de medianoche",
     "cuando": {"dia": 1, "hora": 23, "minuto": 30, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": true, "start": "22:00", "end": "02:00"}},
     "activa": true},

    {"nombre": "nocturno despues de medianoche",
     "cuando": {"dia": 1, "hora": 1, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": true, "start": "22:00", "end": "02:00"}},
     "activa": true},

    {"nombre": "nocturno a mediodia",
     "cuando": {"dia": 1, "hora": 12, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": true, "start": "22:00", "end": "02:00"}},
     "activa": false},

    {"nombre": "dia deshabilitado",
     "cuando": {"dia": 1, "hora": 12, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": false, "start": "08:00", "end": "20:00"}},
     "activa": false},

    {"nombre": "dia abierto sin horas vale todo el dia",
     "cuando": {"dia": 1, "hora": 3, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"lunes": {"enabled": true}},
     "activa": true},

    {"nombre": "sin horario configurado siempre activa",
     "cuando": {"dia": 1, "hora": 4, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": null,
     "activa": true},

    {"nombre": "festivo cerrado manda sobre el dia de la semana",
     "cuando": {"dia": 1, "hora": 12, "minuto": 0, "anio": 2026, "mes": 12, "dia_mes": 25},
     "horario": {"lunes": {"enabled": true, "start": "08:00", "end": "20:00"},
                 "holidays": [{"date": "2026-12-25", "enabled": false}]},
     "activa": false},

    {"nombre": "festivo con horario reducido: dentro",
     "cuando": {"dia": 1, "hora": 11, "minuto": 0, "anio": 2026, "mes": 12, "dia_mes": 24},
     "horario": {"lunes": {"enabled": true, "start": "08:00", "end": "20:00"},
                 "holidays": [{"date": "2026-12-24", "enabled": true, "start": "09:00", "end": "14:00"}]},
     "activa": true},

    {"nombre": "festivo con horario reducido: fuera",
     "cuando": {"dia": 1, "hora": 17, "minuto": 0, "anio": 2026, "mes": 12, "dia_mes": 24},
     "horario": {"lunes": {"enabled": true, "start": "08:00", "end": "20:00"},
                 "holidays": [{"date": "2026-12-24", "enabled": true, "start": "09:00", "end": "14:00"}]},
     "activa": false},

    {"nombre": "festivo abre un domingo normalmente cerrado",
     "cuando": {"dia": 0, "hora": 11, "minuto": 0, "anio": 2026, "mes": 12, "dia_mes": 27},
     "horario": {"lunes": {"enabled": true, "start": "08:00", "end": "20:00"},
                 "holidays": [{"date": "2026-12-27", "enabled": true, "start": "10:00", "end": "14:00"}]},
     "activa": true},

    {"nombre": "solo festivos configurados: el resto del anio sigue encendido",
     "cuando": {"dia": 1, "hora": 4, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15},
     "horario": {"holidays": [{"date": "2026-12-25", "enabled": false}]},
     "activa": true}
  ]
}
```

- [ ] **Step 2: Hacer que el test de JS lea el corpus**

En `tests/schedule.test.js`, al final del archivo:

```js
// ── Corpus compartido con Python ───────────────────────────────────────────
// La misma logica vive en player.html (decide si pintar) y en server.py
// (decide si avisar de una pantalla caida). Duplicarla es inevitable -son dos
// lenguajes- pero que se separen no. Estos casos los ejecutan las dos.
const CORPUS = require("./casos-horario.json");

for (const caso of CORPUS.casos) {
  test(`[corpus] ${caso.nombre}`, () => {
    const at = {
      day: caso.cuando.dia, hour: caso.cuando.hora, minute: caso.cuando.minuto,
      year: caso.cuando.anio, month: caso.cuando.mes - 1, date: caso.cuando.dia_mes,
    };
    assert.strictEqual(isActiveAt(at, { schedule: caso.horario }), caso.activa);
  });
}
```

- [ ] **Step 3: Ejecutar y comprobar que el corpus pasa en JS**

Run: `npm test`
Expected: PASAN los 13 casos `[corpus] …`. Si alguno falla, el corpus describe mal la lógica actual: **corrige el corpus, no `player.html`** — ese comportamiento ya está probado y acordado.

- [ ] **Step 4: Escribir el test de Python que falla**

Crear `tests/test_horario_python.py`:

```python
"""
La version Python de la logica de horario.

El servidor necesita saber si una pantalla DEBERIA estar encendida para no
avisar de una caida a las tres de la madrugada. Esa logica ya existe en
player.html, en JavaScript, y aqui hace falta en Python.

Duplicarla es inevitable -son dos lenguajes- pero que se separen no.
tests/casos-horario.json es el mismo archivo que lee schedule.test.js: si
alguien cambia una implementacion y no la otra, uno de los dos peta.

Ejecutar:  python tests/test_horario_python.py
"""
import importlib.util, json, os, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(AQUI)

# server.py arranca cosas al importarse (crea carpetas de datos), asi que se
# importa con SIGNALOS_DATA apuntando a un temporal.
import tempfile
os.environ["SIGNALOS_DATA"] = tempfile.mkdtemp(prefix="signalos_hor_")
spec = importlib.util.spec_from_file_location("srv", os.path.join(SRC, "server.py"))
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def momento(c):
    """Un struct_time con el dia de la semana y la fecha que pide el caso."""
    # time.struct_time: (anio, mes, dia, hora, min, seg, dia_semana_lunes0,
    #                    dia_del_anio, dst). El corpus usa 0=domingo (como
    #                    JavaScript), asi que hay que convertir.
    tm_wday = (c["dia"] - 1) % 7          # 0=domingo -> 0=lunes
    return time.struct_time((c["anio"], c["mes"], c["dia_mes"],
                             c["hora"], c["minuto"], 0, tm_wday, 1, -1))


def main():
    corpus = json.load(open(os.path.join(AQUI, "casos-horario.json"), encoding="utf-8"))
    for caso in corpus["casos"]:
        cfg = {"schedule": caso["horario"]} if caso["horario"] is not None else {}
        got = srv.pantalla_activa(cfg, momento(caso["cuando"]))
        check(got == caso["activa"], f"[corpus] {caso['nombre']} -> {got}")

    # always_on manda sobre todo, igual que en el player.
    cfg = {"always_on": True,
           "schedule": {"lunes": {"enabled": False, "start": "08:00", "end": "20:00"}}}
    check(srv.pantalla_activa(cfg, momento(
        {"dia": 1, "hora": 3, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15})) is True,
        "always_on ignora el horario")

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
```

- [ ] **Step 5: Ejecutar el test para verificar que falla**

Run: `python tests/test_horario_python.py`
Expected: FALLA con `AttributeError: module 'srv' has no attribute 'pantalla_activa'`.

- [ ] **Step 6: Portar la lógica de horario a Python**

En `server.py`, después de `filtrar_vigentes`:

```python
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def pantalla_activa(cfg, ahora):
    """¿Debería estar encendida esta pantalla ahora mismo?

    Copia en Python de isScreenActive() de player.html. La duplicación es
    inevitable —son dos lenguajes— y hace falta porque el servidor tiene que
    decidir si avisa de una pantalla caída: sin esto, avisaría de todas las
    pantallas del mundo a las tres de la madrugada.

    tests/casos-horario.json es el mismo corpus que ejecuta schedule.test.js.
    Si esta función y la de JavaScript se separan, uno de los dos tests peta.
    """
    cfg = cfg or {}
    if cfg.get("always_on"):
        return True
    horario = cfg.get("schedule") or {}
    if not horario:
        return True

    hoy = time.strftime("%Y-%m-%d", ahora)
    dia_cfg = None
    for f in horario.get("holidays") or []:
        if isinstance(f, dict) and f.get("date") == hoy:
            dia_cfg = f
            break

    if dia_cfg is None:
        dias = [k for k in horario.keys() if k != "holidays"]
        if not dias:
            return True                       # solo hay festivos configurados
        dia_cfg = horario.get(DIAS_ES[ahora.tm_wday])

    if not dia_cfg or not dia_cfg.get("enabled"):
        return False

    actual = time.strftime("%H:%M", ahora)
    inicio = dia_cfg.get("start") or "00:00"
    fin = dia_cfg.get("end") or "23:59"
    if inicio <= fin:
        return inicio <= actual <= fin
    return actual >= inicio or actual <= fin   # cruza medianoche
```

- [ ] **Step 7: Ejecutar los dos tests de horario**

Run:
```bash
python tests/test_horario_python.py
npm test
```
Expected: `TODO OK` y los 13 `[corpus]` en verde en ambos.

- [ ] **Step 8: Commit del horario portado**

```bash
git add server.py tests/casos-horario.json tests/schedule.test.js tests/test_horario_python.py
git commit -m "feat: logica de horario en Python, con corpus compartido con JS"
```

- [ ] **Step 9: Escribir el test de avisos que falla**

Crear `tests/test_avisos.py`:

```python
"""
Avisos por Telegram.

El servidor sabe desde hace tiempo que pantallas estan conectadas y desde
cuando, pero esa informacion solo existe si alguien mira el panel, y nadie lo
mira. Si un televisor pierde corriente un sabado a las 9, te enteras el lunes.

Se avisa de tres cosas: pantalla caida en horario, pantalla que vuelve, y
tasas caducadas. Cada una UNA vez: un aviso por minuto durante el fin de
semana se convierte en ruido y se deja de leer.

Aqui Telegram es un servidor de mentira, para no depender de internet ni
mandarle nada a nadie.

Ejecutar:  python tests/test_avisos.py
"""
import http.server, importlib.util, json, os, socketserver, sys, tempfile
import threading, time

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(AQUI)
FAKE_PORT = 8196

enviados = []


class FalsoTelegram(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(n).decode("utf-8", "replace")
        enviados.append(cuerpo)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    datos = tempfile.mkdtemp(prefix="signalos_avi_")
    os.environ["SIGNALOS_DATA"] = datos

    socketserver.TCPServer.allow_reuse_address = True
    falso = socketserver.TCPServer(("127.0.0.1", FAKE_PORT), FalsoTelegram)
    threading.Thread(target=falso.serve_forever, daemon=True).start()

    spec = importlib.util.spec_from_file_location("srv", os.path.join(SRC, "server.py"))
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)

    # Telegram apuntando al servidor de mentira.
    srv.TELEGRAM_API = f"http://127.0.0.1:{FAKE_PORT}/bot{{token}}/sendMessage"

    cfg = srv.load_json(srv.CONFIG_FILE)
    cfg.update({"telegram_token": "123:ABC", "telegram_chat_id": "999",
                "alert_offline_min": 15})
    srv.save_json(srv.CONFIG_FILE, cfg)

    ahora = time.time()
    try:
        # ── Pantalla caida en horario ──────────────────────────────────────
        srv.save_json(srv.CONTENT_FILE, {"items": [], "packages": [], "screens": {
            "Escaparate": {"mode": "independent", "always_on": True, "playlist": []}}})
        srv.save_json(srv.SCREENS_FILE, {
            "Escaparate": {"id": "Escaparate", "connected": False,
                           "last_seen": ahora - 3600}})
        enviados.clear()
        srv.revisar_avisos()
        check(len(enviados) == 1 and "Escaparate" in enviados[0],
              f"avisa de la pantalla caida -> {enviados}")

        # ── No repite ──────────────────────────────────────────────────────
        enviados.clear()
        srv.revisar_avisos()
        srv.revisar_avisos()
        check(enviados == [], "no repite el aviso en cada pasada")

        # ── Cuando vuelve, avisa una vez ───────────────────────────────────
        srv.save_json(srv.SCREENS_FILE, {
            "Escaparate": {"id": "Escaparate", "connected": True,
                           "last_seen": time.time()}})
        enviados.clear()
        srv.revisar_avisos()
        check(len(enviados) == 1 and "Escaparate" in enviados[0],
              f"avisa de que ha vuelto -> {enviados}")
        enviados.clear()
        srv.revisar_avisos()
        check(enviados == [], "y tampoco repite la recuperacion")

        # ── Fuera de horario no molesta ────────────────────────────────────
        # Un dia con el horario deshabilitado: la pantalla esta apagada porque
        # toca, no porque se haya roto.
        srv.save_json(srv.CONTENT_FILE, {"items": [], "packages": [], "screens": {
            "Caja": {"mode": "independent", "playlist": [], "schedule": {
                "lunes": {"enabled": False}, "martes": {"enabled": False},
                "miércoles": {"enabled": False}, "jueves": {"enabled": False},
                "viernes": {"enabled": False}, "sábado": {"enabled": False},
                "domingo": {"enabled": False}}}})
        srv.save_json(srv.SCREENS_FILE, {
            "Caja": {"id": "Caja", "connected": False, "last_seen": ahora - 7200}})
        srv._alertas.clear()
        enviados.clear()
        srv.revisar_avisos()
        check(enviados == [], "no avisa de una pantalla que esta fuera de horario")

        # ── Tasas caducadas ────────────────────────────────────────────────
        srv.save_json(srv.CONTENT_FILE, {
            "items": [], "packages": [],
            "screens": {"TV": {"mode": "independent", "always_on": True, "playlist": [
                {"id": "fx_1", "type": "fx", "name": "WU", "stale_hours": 24,
                 "updated_at": ahora - 3 * 86400, "rows": []}]}}})
        srv.save_json(srv.SCREENS_FILE, {
            "TV": {"id": "TV", "connected": True, "last_seen": time.time()}})
        srv._alertas.clear()
        enviados.clear()
        srv.revisar_avisos()
        check(len(enviados) == 1 and "WU" in enviados[0],
              f"avisa de las tasas caducadas -> {enviados}")
        enviados.clear()
        srv.revisar_avisos()
        check(enviados == [], "y no lo repite cada minuto")

        # ── Sin token no se contacta con nadie ─────────────────────────────
        cfg = srv.load_json(srv.CONFIG_FILE)
        cfg["telegram_token"] = ""
        srv.save_json(srv.CONFIG_FILE, cfg)
        srv._alertas.clear()
        enviados.clear()
        srv.save_json(srv.SCREENS_FILE, {
            "TV": {"id": "TV", "connected": False, "last_seen": ahora - 7200}})
        srv.revisar_avisos()
        check(enviados == [], "sin token configurado no se habla con nadie")

        # ── Telegram caido no puede tumbar el servidor ─────────────────────
        cfg["telegram_token"] = "123:ABC"
        srv.save_json(srv.CONFIG_FILE, cfg)
        srv.TELEGRAM_API = "http://127.0.0.1:9/bot{token}/sendMessage"  # puerto muerto
        srv._alertas.clear()
        try:
            srv.revisar_avisos()
            check(True, "si Telegram no responde, no revienta")
        except Exception as e:
            check(False, f"si Telegram no responde, no revienta -> {e}")
    finally:
        falso.shutdown()
        import shutil
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
```

- [ ] **Step 10: Ejecutar el test para verificar que falla**

Run: `python tests/test_avisos.py`
Expected: FALLA con `AttributeError: module 'srv' has no attribute 'revisar_avisos'`.

- [ ] **Step 11: Implementar los avisos**

En `server.py`, después de `pantalla_activa`:

```python
# ── Avisos ─────────────────────────────────────────────────────────────────
# El servidor sabe qué pantallas están conectadas y desde cuándo, pero esa
# información solo existe si alguien mira el panel, y nadie lo mira. Si un
# televisor pierde corriente un sábado a las 9, te enteras el lunes.
#
# Cada aviso se manda UNA vez. Un mensaje por minuto durante el fin de semana
# se convierte en ruido y se deja de leer, que es lo mismo que no avisar.
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
ALERT_OFFLINE_MIN_DEFECTO = 15
_alertas = set()          # avisos ya enviados: {("caida", "Escaparate"), ...}
_alertas_lock = threading.Lock()

def enviar_telegram(texto):
    """Manda un mensaje. Devuelve True si salió. NUNCA lanza.

    Que Telegram esté caído, sin cobertura o mal configurado no puede tumbar
    el servidor de una tienda: lo que está en juego es un aviso, no el
    escaparate.
    """
    cfg = load_config()
    token = str(cfg.get("telegram_token", "") or "").strip()
    chat = str(cfg.get("telegram_chat_id", "") or "").strip()
    if not token or not chat:
        return False
    try:
        datos = json.dumps({"chat_id": chat, "text": texto}).encode()
        req = urllib.request.Request(
            TELEGRAM_API.format(token=token), data=datos,
            headers={"Content-Type": "application/json",
                     "User-Agent": f"InTeks-Display/{APP_VERSION}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            r.read(2048)
        return True
    except Exception as e:
        log(f"  [avisos] no se pudo enviar: {e}")
        return False

def _nombre_instalacion():
    return str(load_config().get("installation_name", "") or "InTeks Display")

def revisar_avisos():
    """Una pasada del vigilante. Devuelve la lista de mensajes enviados."""
    enviados = []
    try:
        cfg = load_config()
        if not str(cfg.get("telegram_token", "") or "").strip():
            return enviados                     # apagado: no se habla con nadie
        minutos = cfg.get("alert_offline_min", ALERT_OFFLINE_MIN_DEFECTO)
        try:
            minutos = max(1, int(minutos))
        except Exception:
            minutos = ALERT_OFFLINE_MIN_DEFECTO

        sitio = _nombre_instalacion()
        ahora_ts = time.time()
        ahora_tm = time.localtime(ahora_ts)
        screens = load_json(SCREENS_FILE)
        content = load_json(CONTENT_FILE)
        pantallas = content.get("screens", {})

        for sid, reg in screens.items():
            if sid == "admin":
                continue
            cfg_p = pantallas.get(sid, {})
            debe_estar = pantalla_activa(cfg_p, ahora_tm)
            visto = reg.get("last_seen") or 0
            caida = (not reg.get("connected")) and (ahora_ts - visto) > minutos * 60
            clave = ("caida", sid)

            with _alertas_lock:
                ya_avisada = clave in _alertas

            if caida and debe_estar and not ya_avisada:
                if enviar_telegram(
                        f"⚠ {sitio}\n\nLa pantalla «{sid}» lleva más de "
                        f"{minutos} min sin responder, y debería estar encendida."):
                    with _alertas_lock:
                        _alertas.add(clave)
                    enviados.append(clave)
            elif not caida and ya_avisada:
                if enviar_telegram(f"✅ {sitio}\n\nLa pantalla «{sid}» ha vuelto."):
                    with _alertas_lock:
                        _alertas.discard(clave)
                    enviados.append(("vuelve", sid))

        # ── Tasas caducadas ────────────────────────────────────────────────
        # Se miran las playlists ya expandidas: un módulo de divisas puede
        # venir dentro de un paquete y ahí también cuenta.
        vistos = set()
        for sid, cfg_p in pantallas.items():
            for it in expandir_paquetes(cfg_p.get("playlist", []), content):
                if not isinstance(it, dict) or it.get("type") != "fx":
                    continue
                mid = it.get("id") or it.get("name") or "fx"
                if mid in vistos:
                    continue
                vistos.add(mid)
                horas = it.get("stale_hours")
                horas = 24 if horas in (None, "") else float(horas)
                ts = it.get("updated_at")
                if not horas or not ts:
                    continue
                clave = ("tasas", mid)
                caducado = (ahora_ts - float(ts)) > horas * 3600
                with _alertas_lock:
                    ya = clave in _alertas
                if caducado and not ya:
                    dias = int((ahora_ts - float(ts)) // 86400)
                    cuanto = f"{dias} día(s)" if dias else "más del plazo"
                    if enviar_telegram(
                            f"⚠ {sitio}\n\nEl tablero «{it.get('name') or mid}» "
                            f"lleva {cuanto} sin actualizarse."):
                        with _alertas_lock:
                            _alertas.add(clave)
                        enviados.append(clave)
                elif not caducado and ya:
                    with _alertas_lock:
                        _alertas.discard(clave)
    except Exception as e:
        # El vigilante no puede matar al servidor pase lo que pase.
        log(f"  [avisos] error al revisar: {e}")
    return enviados

def _vigilante():
    """Hilo de fondo. Una pasada por minuto."""
    while True:
        time.sleep(60)
        revisar_avisos()
```

- [ ] **Step 12: Ejecutar el test para verificar que pasa**

Run: `python tests/test_avisos.py`
Expected: `TODO OK`.

- [ ] **Step 13: Arrancar el vigilante y añadir el endpoint de prueba**

En `server.py`, **dentro** de `if __name__ == "__main__":` (server.py:1560), justo
antes de `try: srv.serve_forever()` y por tanto **indentado con cuatro espacios**:

```python
    # Vigilante de avisos. Solo cuando el programa se ejecuta de verdad: si
    # arrancara al importar server.py, los tests que lo importan tendrian un
    # hilo suelto mandando mensajes por su cuenta.
    threading.Thread(target=_vigilante, daemon=True).start()
```

Y en `do_POST`, después del bloque `/api/screen-unlink`:

```python
        # ── Mandar un mensaje de prueba, para saber si los avisos funcionan
        if path == "/api/alert-test":
            try:
                sitio = _nombre_instalacion()
                enviado = enviar_telegram(
                    f"🔔 {sitio}\n\nPrueba de avisos. Si lees esto, está bien configurado.")
                ok({"enviado": bool(enviado)})
            except Exception as e: err(e)
            return
```

- [ ] **Step 14: Interfaz en Ajustes**

En `admin.html`, después de la tarjeta «Copia de seguridad»:

```html
  <div class="card">
    <div class="card-title">Avisos al móvil (Telegram)</div>
    <p style="font-size:12px;color:var(--muted);margin-bottom:14px;line-height:1.6">
      Avisa cuando una pantalla se cae en su horario, cuando vuelve, y cuando un tablero
      de divisas lleva demasiado sin actualizarse.<br>
      Para activarlo: habla con <strong style="color:var(--text)">@BotFather</strong> en Telegram,
      crea un bot y pega aquí su token. El <em>chat ID</em> lo da
      <strong style="color:var(--text)">@userinfobot</strong>.
    </p>
    <div class="form-row">
      <div class="fg"><label class="flabel">Token del bot</label><input class="finput" id="set-tg-token" placeholder="123456:ABC-DEF..."></div>
      <div class="fg"><label class="flabel">Chat ID</label><input class="finput" id="set-tg-chat" placeholder="123456789"></div>
    </div>
    <div class="form-row">
      <div class="fg"><label class="flabel">Avisar tras (minutos sin responder)</label><input class="finput" id="set-tg-min" type="number" min="1" max="1440" value="15" style="width:120px"></div>
    </div>
    <p style="font-size:11px;color:#f0a050;margin:4px 0 12px">
      El token se guarda en config.json, que <strong>sí</strong> va dentro de la copia de seguridad.
      Trata ese archivo como una contraseña.
    </p>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-accent" onclick="guardarAvisos()"><i class="fa-solid fa-floppy-disk"></i> Guardar avisos</button>
      <button class="btn btn-ghost" onclick="probarAvisos()"><i class="fa-solid fa-paper-plane"></i> Enviar mensaje de prueba</button>
    </div>
  </div>
```

Y en el script, junto a `saveSettings`:

```js
// Los avisos se guardan aparte de los ajustes del servidor: cambiar el token
// no tiene por que obligar a reiniciar, y mezclarlos invitaria a hacerlo.
async function guardarAvisos(){
  const cfg={
    telegram_token:document.getElementById("set-tg-token").value.trim(),
    telegram_chat_id:document.getElementById("set-tg-chat").value.trim(),
    alert_offline_min:parseInt(document.getElementById("set-tg-min").value)||15
  };
  try{
    const r=await fetch("/api/config",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(cfg)});
    toast(r.ok?"Avisos guardados ✓":"No se pudieron guardar",!r.ok);
  }catch(e){ toast("Error al guardar los avisos",true); }
}

async function probarAvisos(){
  toast("Enviando…");
  try{
    const r=await fetch("/api/alert-test",{method:"POST",
      headers:{"Content-Type":"application/json"},body:"{}"});
    const d=await r.json();
    toast(d.enviado ? "Enviado ✓ — mira el móvil"
                    : "No salió. Revisa el token y el chat ID.", !d.enviado);
  }catch(e){ toast("Error al enviar la prueba",true); }
}
```

Y en `loadSettings`, dentro del `if(res.ok){`:

```js
      document.getElementById("set-tg-token").value=cfg.telegram_token||"";
      document.getElementById("set-tg-chat").value=cfg.telegram_chat_id||"";
      document.getElementById("set-tg-min").value=cfg.alert_offline_min||15;
```

- [ ] **Step 15: Comprobar a mano con un bot de verdad**

1. En Telegram, hablar con `@BotFather` → `/newbot` → copiar el token.
2. Hablar con `@userinfobot` → copiar el número de `Id`.
3. **Escribirle algo al bot recién creado** (Telegram no deja que un bot inicie la conversación; sin este paso el envío falla con «chat not found»).
4. Pegar token y chat ID en Ajustes → **Guardar avisos** → **Enviar mensaje de prueba**.

Expected: llega el mensaje al móvil y el panel dice «Enviado ✓».

- [ ] **Step 16: Commit**

```bash
git add server.py admin.html tests/test_avisos.py
git commit -m "feat: avisos por Telegram de pantalla caida, recuperada y tasas viejas"
```

---

### Task 6: Cerrar la versión

- [ ] **Step 1: Toda la batería**

Run:
```bash
npm test
python tests/test_data_dir.py
python tests/test_fx_update.py
python tests/test_emparejamiento.py
python tests/test_paquetes.py
python tests/test_backup.py
python tests/test_reset_password.py
python tests/test_log_rotacion.py
python tests/test_actualizacion.py
python tests/test_config_merge.py
python tests/test_disco.py
python tests/test_vigencia.py
python tests/test_horario_python.py
python tests/test_avisos.py
```
Expected: `fail 0` en Node y `TODO OK` en las trece suites de Python.

- [ ] **Step 2: Subir de versión**

Run: `powershell -ExecutionPolicy Bypass -File tools\subir-version.ps1 1.0.2`
Expected: cambia los cuatro sitios y dice `Todo coincide.`

- [ ] **Step 3: Anotar los cambios**

Añadir al principio de `CHANGELOG.md`, bajo el título:

```markdown
## 1.0.2 — 2026-08-09

### Nuevo

- **Avisos al móvil por Telegram**: pantalla caída en su horario, pantalla que
  vuelve, y tablero de divisas sin actualizar. Se configura en Ajustes.
- **Vigencia por fechas**: cada contenido de una playlist puede tener fecha de
  inicio y de fin, y entra y sale solo. Si todo caduca, se sigue mostrando lo
  último antes que dejar el escaparate en negro.
- **Duplicar una pantalla** con toda su configuración, para montar la segunda
  caja sin rehacer nada.
- **Aviso de disco casi lleno** en Ajustes.

### Corregido

- Guardar los ajustes borraba el resto de `config.json` (el nombre mDNS, la
  dirección de actualizaciones y, a partir de ahora, el token de avisos).
```

- [ ] **Step 4: Compilar**

Run: `"C:\Users\axeld\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer/setup.iss`
Expected: `dist\installer\InTeks_Display_Setup_v1.0.2.exe`, sin ningún aviso.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: version 1.0.2"
```

---

## Notas para quien implemente

**El orden importa poco entre las tareas 2, 3 y 4** —son independientes— pero la **1 va primero de todas**: sin la fusión de `config.json`, guardar los ajustes borraría el token de Telegram de la tarea 5 y se perdería media tarde buscando por qué dejan de llegar los avisos.

**Lo más delicado de la tarea 5** no es Telegram, es `pantalla_activa`. Es una copia en Python de una función de JavaScript, y las copias se separan. El corpus compartido (`tests/casos-horario.json`) es lo único que lo impide: **si tocas una implementación, ejecuta los dos tests**, no solo el de tu lenguaje.

**Los tests de Python que importan `server.py`** (tareas 5) tienen que poner `SIGNALOS_DATA` a un temporal **antes** de importarlo. `server.py` crea carpetas y archivos al cargarse, y sin eso escribiría en los datos reales de la máquina de desarrollo.

**Ningún aviso puede repetirse en bucle.** El estado vive en `_alertas`, en memoria: si el servidor se reinicia, se vuelve a avisar una vez. Es lo correcto — tras un reinicio conviene saber qué sigue caído.
