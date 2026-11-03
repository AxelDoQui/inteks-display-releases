#!/usr/bin/env python3
"""
InTeks Display — Servidor Digital Signage
Ejecutar: python server.py [--port PUERTO]
Admin:    http://localhost/admin.html   (puerto 80 por defecto)
Player:   http://TU_IP/player.html?screen=NOMBRE
Enlazar:  http://signage.local/pair     (nombre mDNS, configurable en config.json)
"""
import json, os, base64, mimetypes, threading, time, socket, sys, random, struct
import unicodedata
import hmac, hashlib, secrets, shutil, io, zipfile, contextlib, subprocess, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request, urllib.error

# ── Programa y datos van SEPARADOS ─────────────────────────────────────────
# Instalado en C:\Program Files, Windows prohíbe escribir junto al ejecutable:
# el servidor moría al arrancar con PermissionError al crear 'uploads'. Los
# estáticos (html, vendor, assets) se leen de APP_DIR y todo lo que cambia se
# guarda en DATA_DIR. En desarrollo ambos son la carpeta del proyecto, así que
# nada cambia al trabajar desde el código.
# Versión del programa. Está también en installer/setup.iss y package.json, y
# tests/version-sync.test.js exige que las tres coincidan: si divergen, el panel
# de una tienda dice una cosa y el instalador otra, y el soporte se vuelve
# adivinanza sobre qué código corre realmente ese equipo.
APP_VERSION = "1.0.74"

APP_DIR = os.path.dirname(os.path.abspath(__file__))

def _dentro_de(ruta, carpeta):
    """¿'ruta' cuelga de 'carpeta'? Comparando como lo hace Windows.

    Con startswith a pelo, «C:\\Program Files Comunes» contaría como dentro de
    «C:\\Program Files»: hay que exigir el separador.
    """
    if not carpeta:
        return False
    ruta = os.path.normcase(os.path.abspath(ruta))
    carpeta = os.path.normcase(os.path.abspath(carpeta)).rstrip(os.sep)
    return ruta == carpeta or ruta.startswith(carpeta + os.sep)

def _carpeta_de_datos_del_sistema():
    base = os.environ.get("PROGRAMDATA") or os.path.expanduser("~")
    d = os.path.join(base, "InTeks Display")
    os.makedirs(d, exist_ok=True)
    return d

def pick_data_dir():
    """Carpeta donde guardar lo que cambia. Junto al programa mientras se
    desarrolla; en ProgramData cuando está instalado en Program Files."""
    override = os.environ.get("SIGNALOS_DATA")
    if override:
        os.makedirs(override, exist_ok=True)
        return os.path.abspath(override)
    # Instalado en Archivos de programa: a ProgramData, y no se pregunta si se
    # puede escribir aquí.
    #
    # Antes esto lo decidía solo la prueba de escritura de más abajo, y la
    # prueba se escribió pensando en un proceso de usuario normal, que no puede
    # escribir en Program Files. Pero el servidor arranca desde la tarea
    # programada como SYSTEM, y SYSTEM sí puede: la prueba pasaba y los datos
    # acababan dentro de Program Files —mezclados con el programa, borrables
    # por el instalador y justo donde el manual jura que no están—. Quien
    # decide es DÓNDE está instalado, no qué permisos tenga quien arranca.
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        if _dentro_de(APP_DIR, os.environ.get(var)):
            return _carpeta_de_datos_del_sistema()
    # Comprobar escritura de verdad: los permisos de Windows no se deducen
    # fiablemente con os.access(), hay que intentarlo.
    try:
        probe = os.path.join(APP_DIR, ".signalos-escritura")
        with open(probe, "w") as f: f.write("")
        os.remove(probe)
        return APP_DIR
    except OSError:
        return _carpeta_de_datos_del_sistema()

DATA_DIR = pick_data_dir()
LOG_FILE = os.path.join(DATA_DIR, "server.log")
MAX_LOG_BYTES = 2 * 1024 * 1024     # y se guarda una vuelta: 4 MB de techo
_log_lock = threading.Lock()

def _rotar_log():
    """Aparta el registro cuando se hace grande y empieza otro.

    Se abría en modo «añadir» y no se recortaba nunca. En el PC de una tienda,
    encendido a diario durante años, eso solo crece: con un error que se repita
    en bucle puede comerse el disco, y justo entonces el servidor se queda sin
    poder escribir la pista de lo que está fallando.

    Se guarda UNA sola vuelta anterior. Acumular .1, .2, .3... sería el mismo
    problema repartido en más archivos.
    """
    try:
        if os.path.getsize(LOG_FILE) < MAX_LOG_BYTES:
            return
    except OSError:
        return                       # todavía no existe: nada que apartar
    try:
        os.replace(LOG_FILE, LOG_FILE + ".1")
    except OSError:
        pass                         # otro proceso lo tiene abierto: ya rotará

def log(msg=""):
    """Escribe en la consola si la hay, y SIEMPRE en el log.

    El servidor se ejecuta con pythonw.exe desde una tarea programada para que
    no haya ninguna ventana que alguien pueda cerrar por error. Sin consola,
    sys.stdout puede ser None y un simple print() tumbaría el arranque; además
    se perdería cualquier pista de por qué no levanta. De ahí las dos vías.
    """
    try:
        if sys.stdout is not None:
            print(msg)
    except Exception:
        pass
    try:
        # El candado importa: con ThreadingHTTPServer hay varios hilos
        # escribiendo, y en Windows renombrar un archivo que otro tiene abierto
        # falla.
        with _log_lock:
            _rotar_log()
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except OSError:
        pass

UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
SCREENS_FILE = os.path.join(DATA_DIR, "screens.json")
CONTENT_FILE = os.path.join(DATA_DIR, "content.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Sistema de PIN para enlace
# El PIN se persiste en disco (PIN_FILE) para que sea el MISMO sin importar quién
# lo sirva: el admin (/api/pin), la validación de la tablet (/api/pair) y cualquier
# reinicio o instancia del servidor comparten una única fuente de verdad.
PIN_FILE = os.path.join(DATA_DIR, "pin.json")
pin_state = {
    "pin": None,
    "expires_at": 0,
    "failed_attempts": 0,
    "blocked_until": 0
}

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Restos de subidas que se cortaron con el servidor apagado.
for _n in os.listdir(UPLOAD_DIR):
    if _n.endswith(".part"):
        try: os.remove(os.path.join(UPLOAD_DIR, _n))
        except OSError: pass

# El instalador deja una config.json junto al programa. La primera vez sirve de
# plantilla para la de datos, así se respetan el puerto y el nombre elegidos.
_plantilla = os.path.join(APP_DIR, "config.json")
if DATA_DIR != APP_DIR and not os.path.exists(CONFIG_FILE) and os.path.exists(_plantilla):
    try: shutil.copy2(_plantilla, CONFIG_FILE)
    except OSError: pass

ESTADO = ("screens.json", "content.json", "admin.json", "pin.json")

def _traer_de(origen):
    """Copia el estado desde una ubicación anterior. Nunca pisa lo que ya
    exista en destino: si hay datos nuevos, mandan ellos."""
    if not origen or not os.path.isdir(origen) or os.path.abspath(origen) == os.path.abspath(DATA_DIR):
        return
    for nombre in ESTADO:
        viejo, nuevo = os.path.join(origen, nombre), os.path.join(DATA_DIR, nombre)
        if os.path.exists(viejo) and not os.path.exists(nuevo):
            try:
                shutil.copy2(viejo, nuevo)
                log(f"  [migración] {nombre} traído de {origen}")
            except OSError: pass
    viejo_up = os.path.join(origen, "uploads")
    if os.path.isdir(viejo_up):
        for f in os.listdir(viejo_up):
            o, d = os.path.join(viejo_up, f), os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(o) and not os.path.exists(d):
                try: shutil.copy2(o, d)
                except OSError: pass

def migrar_datos_antiguos():
    """Trae el estado de versiones que lo guardaban junto al programa.

    Antes todo vivía en la carpeta de instalación. Al separar programa y datos,
    una actualización dejaría ese estado huérfano y el cliente perdería sus
    pantallas, su contenido y su contraseña. Se copia una sola vez y NUNCA se
    pisa lo que ya exista en destino: si hay datos nuevos, mandan ellos.
    """
    if DATA_DIR == APP_DIR:
        return
    # Junto al programa: versiones anteriores a separar programa y datos.
    _traer_de(APP_DIR)
    # Carpeta del nombre anterior: el producto se llamaba SignalOS Pro y sus
    # datos vivían en ProgramData\SignalOS Pro. Sin traerlos, cambiarle el
    # nombre al producto le borraría al cliente sus pantallas y su contraseña.
    base = os.path.dirname(DATA_DIR)
    for antiguo in ("SignalOS Pro", "SignalOS"):
        _traer_de(os.path.join(base, antiguo))

migrar_datos_antiguos()

# ── Emparejamiento inverso ─────────────────────────────────────────────────
# Antes el admin generaba un PIN y había que teclearlo EN la pantalla, con el
# mando del televisor. Ahora la pantalla pide un código, lo muestra en grande, y
# el nombre se le pone desde el ordenador: se lee un número en el TV y se teclea
# con un teclado de verdad. Además el nombre deja de escribirse con el mando.
#
# En memoria a propósito: el emparejamiento dura segundos y se cura solo. Si el
# servidor se reinicia, la pantalla no reconoce su token, pide otro código y
# vuelve a mostrarlo. Persistirlo sería complicarlo sin ganar nada.
pending_lock = threading.Lock()
pending_screens = {}          # token -> {code, created, claimed_as}
PENDING_TTL = 900             # 15 min sin reclamar y se olvida

def _purge_pending():
    ahora = time.time()
    for t in [t for t, v in pending_screens.items() if ahora - v["created"] > PENDING_TTL]:
        del pending_screens[t]

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
            code = f"{secrets.randbelow(10000):04d}"
            if code not in usados: break
        token = secrets.token_hex(16)
        pending_screens[token] = {"code": code, "created": time.time(),
                                  "claimed_as": None, "known_as": str(known_as)[:64]}
        return code, token

def pending_list():
    """Códigos a la espera, para que el admin los muestre."""
    with pending_lock:
        _purge_pending()
        return sorted(
            ({"code": v["code"], "waiting_for": int(time.time() - v["created"]),
              "known_as": v.get("known_as", "")}
             for v in pending_screens.values() if not v["claimed_as"]),
            key=lambda x: x["waiting_for"])

def pending_claim(code, name):
    """El admin asigna un nombre a un código. Devuelve (ok, mensaje)."""
    with pending_lock:
        _purge_pending()
        for v in pending_screens.values():
            if v["code"] == str(code).strip() and not v["claimed_as"]:
                v["claimed_as"] = name
                return True, "enlazada"
        return False, "Ese código no está esperando. Comprueba el número en la pantalla."

def pending_status(token):
    """La pantalla pregunta si ya la han enlazado."""
    with pending_lock:
        _purge_pending()
        v = pending_screens.get(token)
        if not v: return None
        return v["claimed_as"]

def init_file(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f: json.dump(default, f, indent=2)

def load_config():
    default_config = {
        "port": 80,
        "port_fallback": 9000,
        "installation_name": "InTeks Display",
        "mdns_name": "signage",
        "autostart": False,
        # Dónde se publica la última versión. Vacío = el servidor no habla con
        # nadie de fuera. Se rellena el día que haya donde publicarla.
        "update_url": "",
        "first_run": True
    }
    init_file(CONFIG_FILE, default_config)
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return default_config

def _save_pin_state():
    """Persiste el estado del PIN en disco (fuente de verdad compartida; escritura atómica)."""
    try: save_json(PIN_FILE, pin_state)
    except Exception: pass

def _load_pin_state():
    """Relee el PIN desde disco para reflejar cambios de otra instancia/reinicio."""
    d = load_json(PIN_FILE)
    if isinstance(d, dict) and d: pin_state.update(d)

def generate_pin():
    """Genera un nuevo PIN de 6 dígitos válido por 10 minutos y lo persiste"""
    pin_state["pin"] = str(100000 + secrets.randbelow(900000))
    pin_state["expires_at"] = time.time() + 600  # 10 minutos
    pin_state["failed_attempts"] = 0
    pin_state["blocked_until"] = 0
    _save_pin_state()
    return pin_state["pin"]

def get_active_pin():
    """Devuelve el PIN activo (desde disco), regenerando sólo si falta o expiró"""
    _load_pin_state()
    if not pin_state.get("pin") or time.time() > pin_state["expires_at"]:
        generate_pin()
    return pin_state["pin"]

def validate_pin(pin_input):
    """Valida un PIN, con protección contra intentos fallidos"""
    _load_pin_state()  # usar siempre el PIN vigente en disco

    # Verificar si está bloqueado
    if time.time() < pin_state["blocked_until"]:
        return False, "Demasiados intentos fallidos. Intenta en unos segundos."

    # Verificar si el PIN ha expirado
    if not pin_state.get("pin") or time.time() > pin_state["expires_at"]:
        generate_pin()
        return False, "PIN expirado. Se ha generado uno nuevo."

    # Verificar PIN
    if str(pin_input) == pin_state["pin"]:
        pin_state["failed_attempts"] = 0
        _save_pin_state()
        return True, "PIN válido"

    # PIN inválido
    pin_state["failed_attempts"] += 1
    if pin_state["failed_attempts"] >= 5:
        pin_state["blocked_until"] = time.time() + 60  # Bloquear 1 minuto
        _save_pin_state()
        return False, "Demasiados intentos fallidos. Intenta en 1 minuto."

    _save_pin_state()
    return False, f"PIN incorrecto. Intentos restantes: {5 - pin_state['failed_attempts']}"

# ─────────────────────────────────────────────────────────────
#  Autenticación del panel admin (stdlib pura)
#  - Contraseña: PBKDF2-HMAC-SHA256 con sal aleatoria (admin.json, NUNCA servido).
#  - Sesión: cookie firmada con HMAC ("expiración.firma"), sin estado en memoria,
#    así sobrevive a reinicios del watchdog.
#  - api_token: para integraciones sin cookie (extensión Chrome) vía cabecera.
#  El PIN de emparejamiento (arriba) es independiente: PIN = enlazar pantallas,
#  contraseña = entrar al panel de control.
# ─────────────────────────────────────────────────────────────
ADMIN_FILE = os.path.join(DATA_DIR, "admin.json")
SESSION_COOKIE = "signalos_session"
SESSION_TTL = 7 * 24 * 3600  # 7 días

def _load_admin():
    d = load_json(ADMIN_FILE)
    return d if isinstance(d, dict) else {}

def admin_has_password():
    return bool(_load_admin().get("pwd_hash"))

# Iteraciones de PBKDF2. Las contraseñas guardadas antes de existir el campo
# "iter" en admin.json se hicieron con 100.000: se siguen aceptando, y se
# vuelven a guardar con las nuevas la primera vez que entran bien.
PBKDF2_ITER_ANTIGUAS = 100000
PBKDF2_ITER = 600000
PASSWORD_MIN = 8

def _hash_password(password, salt, iteraciones=PBKDF2_ITER):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iteraciones).hex()

def set_admin_password(password):
    """Crea/actualiza la contraseña del admin y garantiza secret + api_token."""
    a = _load_admin()
    # Sal nueva en cada cambio: la misma contraseña no repite el mismo hash.
    salt = secrets.token_hex(16)
    a["salt"] = salt
    a["iter"] = PBKDF2_ITER
    a["pwd_hash"] = _hash_password(password, salt)
    if not a.get("secret"):    a["secret"] = secrets.token_hex(32)
    if not a.get("api_token"): a["api_token"] = secrets.token_hex(24)
    save_json(ADMIN_FILE, a)
    return a

def verify_admin_password(password):
    a = _load_admin()
    if not a.get("pwd_hash") or not a.get("salt"): return False
    iteraciones = int(a.get("iter") or PBKDF2_ITER_ANTIGUAS)
    if not hmac.compare_digest(_hash_password(password, a["salt"], iteraciones), a["pwd_hash"]):
        return False
    if iteraciones < PBKDF2_ITER:
        # Migración: ya tenemos la contraseña en claro y sabemos que es buena.
        # Si guardar falla, no pasa nada: seguirá valiendo con las antiguas.
        try:
            a["iter"] = PBKDF2_ITER
            a["pwd_hash"] = _hash_password(password, a["salt"])
            save_json(ADMIN_FILE, a)
        except Exception as e:
            log(f"  [auth] no se pudo actualizar el hash: {e}")
    return True

def _session_secret():
    a = _load_admin()
    s = a.get("secret")
    if not s:
        s = secrets.token_hex(32); a["secret"] = s; save_json(ADMIN_FILE, a)
    return s.encode("utf-8")

def make_session_token(ttl=SESSION_TTL):
    exp = str(int(time.time() + ttl))
    sig = hmac.new(_session_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"

def verify_session_token(token):
    try:
        exp_s, sig = token.split(".", 1)
        good = hmac.new(_session_secret(), exp_s.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good): return False
        return time.time() < int(exp_s)
    except Exception:
        return False

def get_api_token():
    return _load_admin().get("api_token")

def find_free_port(preferred_port, fallback_port):
    """Intenta usar puerto preferido, si está ocupado prueba el alternativo y otros"""
    ports_to_try = [preferred_port, fallback_port]
    # Si los dos principales no funcionan, intenta puertos consecutivos desde el fallback
    for offset in range(1, 20):
        extra = fallback_port + offset
        if extra not in ports_to_try:
            ports_to_try.append(extra)
    for port in ports_to_try:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            s.close()
            return port
        except Exception:
            continue
    return None

config = load_config()
PORT = int(sys.argv[sys.argv.index("--port")+1]) if "--port" in sys.argv else config["port"]

# Detectar puerto libre automáticamente
port_to_use = find_free_port(PORT, config.get("port_fallback", PORT + 1))
if not port_to_use:
    _fb = config.get("port_fallback", PORT + 1)
    log(f"ERROR: No hay puertos disponibles (intentados: {PORT}, {_fb}, y {_fb+1}-{_fb+19})")
    sys.exit(1)
PORT = port_to_use

init_file(SCREENS_FILE, {})
init_file(CONTENT_FILE, {"items": [], "screens": {}, "rev": 0})

# La limpieza del registro se hace más abajo, en cuanto load_json/save_json
# existen. Aquí arriba todavía no están definidas.

sse_clients = {}  # screen_id -> [wfile, ...]
sse_lock = threading.Lock()
file_lock = threading.RLock()  # serializa lectura/escritura de los JSON (ThreadingHTTPServer)

def notify_screen(screen_id):
    with sse_lock:
        dead = []
        for wfile in sse_clients.get(screen_id, []):
            try:
                wfile.write(f"data: update:{screen_id}\n\n".encode())
                wfile.flush()
            except Exception: dead.append(wfile)
        if dead:
            sse_clients[screen_id] = [c for c in sse_clients.get(screen_id,[]) if c not in dead]

def notify_all():
    with sse_lock:
        all_ids = list(sse_clients.keys())
    for sid in all_ids: notify_screen(sid)

def notify_reload(screen_id):
    """Pide a la pantalla que recargue su reproductor (botón «Reiniciar reproductor»).
    Devuelve a cuántas conexiones se le escribió el aviso."""
    n = 0
    with sse_lock:
        for wfile in list(sse_clients.get(screen_id, [])):
            try:
                wfile.write(f"data: reload:{screen_id}\n\n".encode())
                wfile.flush()
                n += 1
            except Exception: pass
    return n

def notify_deleted(screen_id):
    """Avisa a la pantalla (vía SSE) de que fue eliminada para que se desconecte."""
    with sse_lock:
        for wfile in list(sse_clients.get(screen_id, [])):
            try:
                wfile.write(f"data: deleted:{screen_id}\n\n".encode())
                wfile.flush()
            except Exception: pass

# ── Aviso de version nueva ─────────────────────────────────────────────────
# Esto NO instala nada solo. En una pantalla de escaparate, actualizarse sin
# permiso es la peor idea posible: el momento lo eliges tú, no el programa.
# Avisa en el panel; instalar es una acción aparte (el botón «Actualizar ahora»,
# más abajo), que solo ocurre cuando alguien con sesión la pide.
#
# Consulta la dirección de `url_actualizaciones()` solo cuando el panel lo pide
# (no hay ninguna consulta en segundo plano). "update_url": "off" la apaga.
_update_cache = {"cuando": 0, "datos": None}

# Dónde se publica la última versión (GitHub Releases, repositorio solo de
# descargas). Es el valor de fábrica: las instalaciones ya hechas tienen
# `update_url` vacía en su config.json y así también reciben el aviso sin tocar
# nada. Para apagar la consulta de una tienda: "update_url": "off".
UPDATE_URL_DEFECTO = ("https://github.com/AxelDoQui/inteks-display-releases"
                      "/releases/latest/download/version.json")

def url_actualizaciones():
    v = str(load_config().get("update_url", "") or "").strip()
    if v.lower() == "off":
        return ""
    return v or UPDATE_URL_DEFECTO
UPDATE_TTL = 600                   # no molestar al servidor de versiones cada rato (10 min)

def comparar_versiones(a, b):
    """-1 si a<b, 0 si iguales, 1 si a>b.

    Comparar como texto sería un error clásico: "1.0.10" < "1.0.9" en
    alfabético, así que la actualización más esperada sería justo la que no se
    anuncia. Se comparan los números.
    """
    def partes(v):
        out = []
        for t in str(v or "").split("."):
            digitos = "".join(c for c in t if c.isdigit())
            out.append(int(digitos) if digitos else 0)
        return out
    pa, pb = partes(a), partes(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    return (pa > pb) - (pa < pb)

def comprobar_actualizacion(url):
    """Consulta la última versión publicada. Nunca lanza: el panel no puede
    romperse porque el sitio de versiones esté caído o devuelva basura."""
    ahora = time.time()
    if _update_cache["datos"] and ahora - _update_cache["cuando"] < UPDATE_TTL:
        return _update_cache["datos"]
    base = {"enabled": True, "current": APP_VERSION, "update_available": False}
    try:
        peticion = urllib.request.Request(
            url, headers={"User-Agent": f"InTeks-Display/{APP_VERSION}"})
        with urllib.request.urlopen(peticion, timeout=5) as r:
            remoto = json.loads(r.read(65536).decode("utf-8", "replace"))
        ultima = str(remoto.get("version", "")).strip()
        if not ultima:
            raise ValueError("la respuesta no trae 'version'")
        base.update({
            "latest": ultima,
            "update_available": comparar_versiones(APP_VERSION, ultima) < 0,
            "url": remoto.get("url", ""),
            "notes": remoto.get("notes", ""),
            # Solo para el botón «Actualizar»: de dónde bajar el instalador y su huella.
            "installer_url": str(remoto.get("installer_url", "") or ""),
            "sha256": str(remoto.get("sha256", "") or "").strip().lower(),
        })
    except Exception as e:
        base["error"] = f"No se pudo consultar: {e}"
    _update_cache.update({"cuando": ahora, "datos": base})
    return base

# ── Instalar la versión nueva (botón «Actualizar» del panel) ───────────────
# El aviso de arriba sigue sin instalar nada solo: esto solo ocurre cuando
# alguien con sesión pulsa el botón. La dirección del instalador sale del
# version.json que consulta el SERVIDOR; el navegador no puede mandar la suya.
#
# Qué protege y qué no: el SHA-256 evita instalar un archivo corrupto o cortado.
# NO protege de quien controle la cuenta donde se publica (podría cambiar el
# instalador y la huella a la vez): esa cuenta es la raíz de confianza, y hay
# que protegerla con verificación en dos pasos. La defensa de verdad sería
# firmar el instalador.
UPDATE_MAX_BYTES = 300 * 1024 * 1024
UPDATE_DIR = os.path.join(DATA_DIR, "actualizacion")
_update_lock = threading.Lock()

def _url_instalador_valida(u):
    p = urlparse(str(u or ""))
    if p.scheme == "https" and p.hostname:
        return True
    # http solo hacia esta misma máquina (pruebas): nunca por la red.
    return p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost")

def preparar_instalador(datos):
    """Baja el instalador anunciado y comprueba su huella. Devuelve la ruta.
    Lanza ValueError con un mensaje legible si algo no cuadra (y borra lo bajado)."""
    ver = str(datos.get("latest", ""))
    if not re.fullmatch(r"\d+(\.\d+){1,3}", ver):
        raise ValueError("La versión publicada no tiene un formato válido")
    url = datos.get("installer_url", "")
    if not _url_instalador_valida(url):
        raise ValueError("La versión publicada no trae una dirección de descarga segura (https)")
    esperado = datos.get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", esperado):
        raise ValueError("La versión publicada no trae la huella SHA-256 del instalador")
    os.makedirs(UPDATE_DIR, exist_ok=True)
    for f in os.listdir(UPDATE_DIR):                       # restos de intentos anteriores
        try: os.remove(os.path.join(UPDATE_DIR, f))
        except OSError: pass
    ruta = os.path.join(UPDATE_DIR, f"InTeks_Display_Setup_{ver}.exe")
    h = hashlib.sha256()
    total = 0
    try:
        peticion = urllib.request.Request(url, headers={"User-Agent": f"InTeks-Display/{APP_VERSION}"})
        with urllib.request.urlopen(peticion, timeout=30) as r, open(ruta, "wb") as f:
            if not _url_instalador_valida(r.geturl()):      # una redirección tampoco puede bajar a http
                raise ValueError("La descarga se redirigió a una dirección no segura")
            while True:
                trozo = r.read(65536)
                if not trozo: break
                total += len(trozo)
                if total > UPDATE_MAX_BYTES:
                    raise ValueError("El instalador es más grande de lo esperado")
                h.update(trozo); f.write(trozo)
        if h.hexdigest() != esperado:
            raise ValueError("El instalador descargado no coincide con su huella SHA-256: no se instala")
        with open(ruta, "rb") as f:
            if f.read(2) != b"MZ":
                raise ValueError("Lo descargado no es un programa de Windows")
    except Exception as e:
        try: os.remove(ruta)
        except OSError: pass
        if isinstance(e, ValueError): raise
        raise ValueError(f"No se pudo descargar el instalador: {e}")
    return ruta

def lanzar_instalador(ruta):
    """Ejecuta el instalador en silencio, separado de este proceso: él mismo
    parará este servidor para sustituir los archivos y lo volverá a arrancar."""
    args = [ruta, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            f"/LOG={os.path.join(UPDATE_DIR, 'instalacion.log')}"]
    if os.environ.get("SIGNALOS_UPDATE_DRYRUN"):             # pruebas: no ejecuta nada
        with open(os.path.join(UPDATE_DIR, "lanzaria.txt"), "w") as f:
            f.write(" ".join(args))
        return
    if os.name != "nt":
        raise ValueError("La actualización desde el panel solo existe en Windows")
    DETACHED, NUEVO_GRUPO, FUERA_DEL_JOB = 0x00000008, 0x00000200, 0x01000000
    try:
        subprocess.Popen(args, creationflags=DETACHED | NUEVO_GRUPO | FUERA_DEL_JOB, close_fds=True)
    except OSError:
        # El job de Windows no permite salirse: sin esa marca.
        subprocess.Popen(args, creationflags=DETACHED | NUEVO_GRUPO, close_fds=True)
    log(f"  [actualizar] instalador lanzado: {ruta}")

# ── Televisores LG con la mini-app: cuánto les queda de modo desarrollador ──
# El «Developer Mode» de un LG caduca a las ~1000 h de activarlo o renovarlo
# («Extend Session Time») y entonces la mini-app deja de abrirse. instalar-lg.ps1
# apunta aquí cada TV con el momento (hora del televisor) en que empezó la sesión;
# el panel avisa unos días antes. El servidor no habla con el TV: calcula con esa
# fecha, y si se renueva el modo desarrollador se pulsa «Ya lo renové».
LG_TVS_FILE = os.path.join(DATA_DIR, "lg_tvs.json")
LG_DEVMODE_SEGUNDOS = 1000 * 3600
LG_AVISO_SEGUNDOS = 7 * 24 * 3600

def lg_tvs_estado(ahora=None):
    """Lista de TVs con lo que les queda. Nunca lanza: un archivo raro no puede
    romper el panel."""
    ahora = time.time() if ahora is None else ahora
    try:
        tvs = load_json(LG_TVS_FILE).get("tvs", [])
    except Exception:
        return []
    out = []
    for t in tvs if isinstance(tvs, list) else []:
        if not isinstance(t, dict):
            continue
        try:
            inicio = float(t.get("inicio"))
        except (TypeError, ValueError):
            continue
        restante = max(0, int(inicio + LG_DEVMODE_SEGUNDOS - ahora))
        out.append({"id": str(t.get("id", "")), "nombre": str(t.get("nombre", "")),
                    "ip": str(t.get("ip", "")), "inicio": int(inicio),
                    "vigilar": t.get("vigilar") is True,
                    "restante_s": restante, "restante_h": restante // 3600,
                    "aviso": restante <= LG_AVISO_SEGUNDOS})
    return out

def lg_tv_cambiar(tv_id, accion, ahora=None, activo=None):
    """«renovado» (reinicia la cuenta atrás), «borrar» o «vigilar» (activo True/False:
    si vigilar-lg.ps1 debe abrir la mini-app cuando no esté abierta). False si no existe."""
    ahora = time.time() if ahora is None else ahora
    datos = load_json(LG_TVS_FILE)
    tvs = datos.get("tvs", []) if isinstance(datos.get("tvs", []), list) else []
    for t in list(tvs):
        if isinstance(t, dict) and str(t.get("id")) == str(tv_id):
            if accion == "borrar":
                tvs.remove(t)
            elif accion == "vigilar":
                t["vigilar"] = bool(activo)
            else:
                t["inicio"] = int(ahora)
            save_json(LG_TVS_FILE, {"tvs": tvs})
            return True
    return False

# ── Instalar la mini-app en un LG desde el panel ────────────────────────────
# El panel pide la IP del TV, su passphrase y la dirección de este servidor, y el
# servidor lanza tools\instalar-lg.ps1 (el mismo que usaba el acceso del menú Inicio).
# El servidor corre como SYSTEM, así que el script recibe -Casa: la clave del TV y los
# datos de la herramienta de LG quedan en lg-home\ dentro de los datos, y la tarea que
# mantiene la mini-app abierta (vigilar-lg.ps1) los busca allí. La passphrase viaja
# por variable de entorno, no por la línea de comandos. Solo una instalación a la vez.
LG_CASA = os.path.join(DATA_DIR, "lg-home")
LG_INSTALAR_MAX_S = 15 * 60
_lg_inst = {"estado": "libre", "lineas": [], "tv": ""}     # libre | instalando | ok | error
_lg_inst_lock = threading.Lock()

def lg_script_instalar():
    """Ruta de instalar-lg.ps1 si esta instalación puede usarlo, o None."""
    ruta = os.environ.get("SIGNALOS_LG_SCRIPT")
    if ruta:
        return ruta if os.path.isfile(ruta) else None
    if not os.path.isdir(os.path.join(APP_DIR, "webos")):
        return None
    for sub in ("", "tools"):
        p = os.path.join(APP_DIR, sub, "instalar-lg.ps1")
        if os.path.isfile(p):
            return p
    return None

def lg_validar(ip, passphrase, servidor):
    """Texto del problema, o None si los tres datos valen. Se comprueba aquí porque
    acaban en una línea de comandos y en un JSON de la herramienta de LG."""
    m = re.fullmatch(r"(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})", ip or "")
    if not m or any(int(x) > 255 for x in m.groups()):
        return "La IP del televisor no es válida (algo como 192.168.0.108)"
    if not re.fullmatch(r"[A-Za-z0-9]{4,32}", passphrase or ""):
        return "La passphrase solo lleva letras y números (la que sale en «Developer Mode»)"
    if not re.fullmatch(r"(https?://)?[A-Za-z0-9.\-]+(:\d{1,5})?/?", servidor or ""):
        return "La dirección del servidor no es válida (algo como 192.168.0.90)"
    return None

def lg_instalar_estado():
    with _lg_inst_lock:
        return {"estado": _lg_inst["estado"], "lineas": list(_lg_inst["lineas"]), "tv": _lg_inst["tv"]}

def lg_instalar_iniciar(ip, passphrase, servidor, vigilar):
    """Lanza la instalación en segundo plano. (True, "") o (False, motivo)."""
    err = lg_validar(ip, passphrase, servidor)
    if err:
        return False, err
    script = lg_script_instalar()
    if not script:
        return False, "Esta instalación no trae la mini-app para LG. Reinstala InTeks Display con la última versión."
    if sys.platform != "win32":
        return False, "La instalación en un LG solo existe en Windows"
    with _lg_inst_lock:
        if _lg_inst["estado"] == "instalando":
            return False, "Ya hay una instalación en marcha"
        _lg_inst.update(estado="instalando", lineas=[], tv=ip)
    args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
            "-TV", ip, "-Servidor", servidor, "-Casa", LG_CASA]
    if vigilar:
        args.append("-Vigilar")
    entorno = dict(os.environ, INTEKS_LG_PASS=passphrase)

    def anota(linea):
        linea = linea.replace(passphrase, "***").strip()[:300]
        if linea:
            with _lg_inst_lock:
                _lg_inst["lineas"] = (_lg_inst["lineas"] + [linea])[-200:]

    def correr():
        codigo = 1
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=entorno,
                                    stdin=subprocess.DEVNULL, creationflags=0x08000000)   # sin ventana
            def vigila():
                try: proc.wait(timeout=LG_INSTALAR_MAX_S)
                except subprocess.TimeoutExpired:
                    anota("ERROR: la instalación tardó demasiado y se canceló."); proc.kill()
            threading.Thread(target=vigila, daemon=True).start()
            for bruto in proc.stdout:
                for linea in re.split(r"[\r\n]+", bruto.decode("utf-8", "replace")):
                    anota(linea)
            codigo = proc.wait()
        except Exception as e:
            anota(f"ERROR: no se pudo lanzar la instalación ({e})")
        with _lg_inst_lock:
            _lg_inst["estado"] = "ok" if codigo == 0 else "error"
        log(f"  [lg] instalación en {ip}: {'ok' if codigo == 0 else 'falló'}")

    threading.Thread(target=correr, daemon=True).start()
    return True, ""

# ── Acceso remoto: enlazar este PC con la cuenta de InTeks y dejarlo accesible desde
# internet en su propia dirección (tienda1.inteksdisplay.com).
# El usuario saca un PIN en su cuenta y lo escribe en el panel. Aquí se canjea con el
# Worker de la cuenta, que crea el túnel y la dirección y devuelve SOLO el token de ese
# túnel; con él se instala cloudflared como servicio de Windows. El token no se guarda
# ni se muestra en ningún sitio: lo guarda el propio servicio.
ACCESO_FILE = os.path.join(DATA_DIR, "acceso-remoto.json")
CUENTA_URL = os.environ.get("SIGNALOS_CUENTA_URL", "https://cuenta.inteksdisplay.com").rstrip("/")
_acc = {"estado": "libre", "pasos": [], "error": ""}     # libre | activando | ok | error
_acc_lock = threading.Lock()

def acceso_cloudflared():
    """Ruta de cloudflared.exe si esta instalación lo trae, o None."""
    ruta = os.environ.get("SIGNALOS_CLOUDFLARED")
    if ruta:
        return ruta if os.path.isfile(ruta) else None
    p = os.path.join(APP_DIR, "cloudflared.exe")
    return p if os.path.isfile(p) else None

def acceso_servicio_activo():
    if os.environ.get("SIGNALOS_CLOUDFLARED"):
        return True                                       # en las pruebas no hay servicio real
    try:
        r = subprocess.run(["sc.exe", "query", "cloudflared"], capture_output=True, text=True,
                           timeout=15, creationflags=0x08000000)
        return "RUNNING" in r.stdout
    except Exception:
        return False

def acceso_servicio_existe():
    """True si Windows aún tiene registrado el servicio cloudflared (en marcha, parándose o no)."""
    if os.environ.get("SIGNALOS_CLOUDFLARED"):
        return False                                      # en las pruebas no hay servicio real
    try:
        r = subprocess.run(["sc.exe", "query", "cloudflared"], capture_output=True, text=True,
                           timeout=15, creationflags=0x08000000)
        return r.returncode != 1060
    except Exception:
        return False

def acceso_estado():
    f = load_json(ACCESO_FILE)
    f = f if isinstance(f, dict) else {}
    with _acc_lock:
        e = {"estado": _acc["estado"], "pasos": list(_acc["pasos"]), "error": _acc["error"]}
    e.update(disponible=acceso_cloudflared() is not None, password=admin_has_password(),
             activo=bool(f.get("hostname")), hostname=f.get("hostname", ""),
             servicio=acceso_servicio_activo() if f.get("hostname") else False)
    return e

def _acceso_cf(exe, *args, timeout=120):
    return subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=0x08000000)

def acceso_activar(pin, puerto):
    """Lanza la activación en segundo plano. (True, "") o (False, motivo)."""
    if not re.fullmatch(r"\d{6}", pin or ""):
        return False, "El PIN son 6 cifras"
    if not admin_has_password():
        return False, "Antes de activarlo, crea la contraseña del administrador (Seguridad y acceso): si no, el panel quedaría abierto a internet"
    exe = acceso_cloudflared()
    if not exe:
        return False, "Esta instalación no trae cloudflared. Reinstala InTeks Display con la última versión."
    if sys.platform != "win32" and not os.environ.get("SIGNALOS_CLOUDFLARED"):
        return False, "El acceso remoto solo existe en Windows"
    with _acc_lock:
        if _acc["estado"] == "activando":
            return False, "Ya hay una activación en marcha"
        _acc.update(estado="activando", pasos=[], error="")

    def paso(t):
        with _acc_lock:
            _acc["pasos"] = (_acc["pasos"] + [t])[-20:]

    def correr():
        token = ""
        try:
            paso("Comprobando el PIN con tu cuenta…")
            req = urllib.request.Request(CUENTA_URL + "/api/enlazar",
                data=json.dumps({"pin": pin, "puerto": puerto}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "InTeksDisplay"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r)
            except urllib.error.HTTPError as e:
                try: d = json.loads(e.read() or b"{}")
                except ValueError: d = {}
                raise ValueError(d.get("error") or ("La cuenta respondió " + str(e.code)))
            token, host = str(d.get("token", "")), str(d.get("hostname", ""))
            if not re.fullmatch(r"[A-Za-z0-9_\-=.]{20,2000}", token) or not re.fullmatch(r"[a-z0-9.\-]{3,120}", host):
                token = ""                                # no se usa ni se imprime
                raise ValueError("La cuenta devolvió una respuesta que no se puede usar")
            paso("Instalando el servicio de conexión…")
            try: _acceso_cf(exe, "service", "uninstall", timeout=60)      # por si había otro túnel
            except Exception: pass
            # cloudflared tarda en detenerse (espera a cerrar conexiones): hasta que Windows
            # no lo da por borrado, instalar el nuevo falla.
            for _ in range(60):
                if not acceso_servicio_existe(): break
                time.sleep(1)
            r = _acceso_cf(exe, "service", "install", token)
            if r.returncode != 0:
                raise ValueError("No se pudo instalar el servicio (hacen falta permisos de administrador)")
            paso("Comprobando que arranca…")
            for _ in range(20):
                if acceso_servicio_activo(): break
                time.sleep(1)
            else:
                raise ValueError("El servicio se instaló pero no arrancó")
            save_json(ACCESO_FILE, {"hostname": host, "activado_en": time.time()})
            paso("Listo: " + host)
            with _acc_lock: _acc["estado"] = "ok"
            log(f"  [acceso] activado en {host}")
        except Exception as e:
            msg = str(e).replace(token, "***") if token else str(e)
            with _acc_lock: _acc.update(estado="error", error=msg[:300])
            log(f"  [acceso] no se pudo activar: {msg[:200]}")

    threading.Thread(target=correr, daemon=True).start()
    return True, ""

def acceso_desactivar():
    exe = acceso_cloudflared()
    if exe:
        try: _acceso_cf(exe, "service", "uninstall", timeout=60)
        except Exception: pass
    try: os.remove(ACCESO_FILE)
    except OSError: pass
    with _acc_lock: _acc.update(estado="libre", pasos=[], error="")

# ── Copia de seguridad ─────────────────────────────────────────────────────
# Toda la configuración de una tienda vivía solo en el disco de ese PC. Si el
# equipo moría, se perdía entera; y montar una segunda tienda obligaba a rehacer
# el trabajo desde cero.
#
# Lo que NO viaja: admin.json y pin.json. Llevan el hash de la contraseña, el
# secreto de sesión y el token de la extensión. Un archivo que va por correo o
# en un pendrive no puede llevar eso dentro, y además cada equipo debe conservar
# sus credenciales al restaurar.
BACKUP_JSONS = ("content.json", "screens.json", "config.json")
BACKUP_FICHA = "inteks-backup.json"
MAX_BODY_BYTES = 512 * 1024 * 1024      # el cuerpo POST se carga entero en RAM
# POST que se aceptan sin sesión (el resto exige cookie o api_token antes de
# leer el cuerpo). Sus cuerpos son JSON de unas pocas líneas.
POST_PUBLICOS = {"/api/login", "/api/set-password", "/api/logout",
                 "/api/pair-request", "/api/pair-status", "/api/pair",
                 "/api/screen-now", "/api/wall-sync"}
# Lo que cada pantalla está mostrando ahora (solo memoria, se pierde al reiniciar).
ahora_pantalla = {}
# Videowall: lo que muestra la pantalla que manda (la izquierda), para que la otra la siga.
# {pantalla_que_manda: {id, t, video, at}} con «at» en el reloj del servidor, que es el
# único reloj que comparten las dos pantallas. Solo memoria: se rehace cada segundo.
wall_estado = {}


def wall_de(scr, sid):
    """(ids, posición) de la pantalla `sid` en su videowall. `ids` va de izquierda a derecha y
    la primera es la que manda. Los muros antiguos solo traen «partner» y «wall_pos»."""
    ids = scr.get("wall_ids")
    if isinstance(ids, list) and sid in ids:
        ids = [str(x) for x in ids]
        return ids, ids.index(sid)
    partner = str(scr.get("partner", "") or "")
    if scr.get("wall_pos") == "right":
        return [partner, sid], 1
    return [sid, partner], 0
# Vídeos que una pantalla no consigue reproducir: {pantalla: {id, name, motivo, at}}.
fallos_video = {}
MAX_BODY_PUBLICO = 64 * 1024

# Intentos de login fallidos por dirección: 5 y se bloquea un minuto. Por
# dirección y no global, para que un intruso no deje fuera al dueño.
LOGIN_MAX_FALLOS = 5
LOGIN_BLOQUEO_S = 60
_login_fallos = {}          # ip -> {"n": fallos, "hasta": instante de desbloqueo}
_login_lock = threading.Lock()

def login_bloqueado(ip):
    """Segundos que faltan para poder reintentar, o 0 si puede intentarlo."""
    with _login_lock:
        e = _login_fallos.get(ip)
        if not e: return 0
        resto = e["hasta"] - time.time()
        if resto > 0: return int(resto) + 1
        if e["hasta"]: del _login_fallos[ip]       # el bloqueo ya pasó
        return 0

def login_fallo(ip):
    with _login_lock:
        if len(_login_fallos) > 1000:               # que no crezca sin fin
            _login_fallos.clear()
        e = _login_fallos.setdefault(ip, {"n": 0, "hasta": 0})
        e["n"] += 1
        if e["n"] >= LOGIN_MAX_FALLOS:
            e["hasta"] = time.time() + LOGIN_BLOQUEO_S
            e["n"] = 0

def login_acierto(ip):
    with _login_lock: _login_fallos.pop(ip, None)

def crear_backup(incluir_media=True):
    """Devuelve los bytes de un zip con la configuración (y opcionalmente los
    archivos subidos). Sin multimedia cabe en un correo; con ella es un clon."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(BACKUP_FICHA, json.dumps({
            "app": "InTeks Display",
            "version": 1,
            "created_at": time.time(),
            "created_at_txt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "media": bool(incluir_media),
        }, indent=2))
        for nombre in BACKUP_JSONS:
            ruta = os.path.join(DATA_DIR, nombre)
            if os.path.exists(ruta):
                z.write(ruta, nombre)
        if incluir_media and os.path.isdir(UPLOAD_DIR):
            for raiz, _, ficheros in os.walk(UPLOAD_DIR):
                for f in ficheros:
                    if f.endswith(".part"): continue    # subida a medias
                    completa = os.path.join(raiz, f)
                    rel = os.path.relpath(completa, UPLOAD_DIR).replace("\\", "/")
                    z.write(completa, f"uploads/{rel}")
    return buf.getvalue()

# ── Copia de seguridad automática ──────────────────────────────────────────
# La del panel es a mano, y lo que se hace a mano un día no se hace. Una al día,
# sin multimedia (playlists, pantallas y ajustes: lo que cuesta rehacer; los
# vídeos están en el equipo que los subió), en una carpeta junto a los datos.
# Va a disco aparte de uploads/ y no entra en las copias del panel.
COPIAS_DIR = os.path.join(DATA_DIR, "copias")
COPIAS_PREFIJO = "InTeks-Display-auto-"
COPIAS_GUARDAR_DEFECTO = 14

def copia_automatica_si_toca():
    """Hace la copia de hoy si no existe y poda las viejas. Devuelve la ruta
    creada, o None si no tocaba. Lanza si la copia falla (la llama el vigilante)."""
    cfg = load_config()
    if cfg.get("copia_auto", True) is False:
        return None
    hoy = time.strftime("%Y-%m-%d")
    destino = os.path.join(COPIAS_DIR, f"{COPIAS_PREFIJO}{hoy}.zip")
    if os.path.exists(destino):
        return None
    try:
        os.makedirs(COPIAS_DIR, exist_ok=True)
        tmp = destino + ".tmp"
        with open(tmp, "wb") as f:
            f.write(crear_backup(False))
        # Una copia que no abre no es una copia: se comprueba antes de darla por buena.
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None or BACKUP_FICHA not in z.namelist():
                raise RuntimeError("la copia recién hecha no es válida")
        os.replace(tmp, destino)
    except Exception as e:
        log(f"  [copias] no se pudo hacer la copia automática: {e}")
        raise
    # Poda solo DESPUÉS de tener la de hoy, y solo lo que lleva nuestro prefijo.
    try:
        guardar = max(1, int(cfg.get("copia_auto_dias", COPIAS_GUARDAR_DEFECTO)))
    except (TypeError, ValueError):
        guardar = COPIAS_GUARDAR_DEFECTO
    viejas = sorted(f for f in os.listdir(COPIAS_DIR)
                    if f.startswith(COPIAS_PREFIJO) and f.endswith(".zip"))
    for f in viejas[:-guardar]:
        try: os.remove(os.path.join(COPIAS_DIR, f))
        except OSError: pass
    log(f"  [copias] copia automática: {destino}")
    return destino

def copia_externa_si_toca():
    """Copia la de hoy a la carpeta externa (Drive, un USB, otro disco) si está
    configurada en `copia_externa`. Se reintenta cada minuto mientras falte: un
    USB desenchufado no cuenta como «hecho». Nunca lanza."""
    try:
        cfg = load_config()
        destino_base = str(cfg.get("copia_externa", "") or "").strip()
        if not destino_base:
            return None
        hoy = time.strftime("%Y-%m-%d")
        nombre_zip = f"{COPIAS_PREFIJO}{hoy}.zip"
        origen = os.path.join(COPIAS_DIR, nombre_zip)
        if not os.path.exists(origen):
            return None                                   # aún no hay copia de hoy
        # La carpeta tiene que existir ya: si es un USB que no está, no se
        # inventa una carpeta con ese nombre en el disco del sistema.
        if not os.path.isdir(destino_base):
            return None
        real_base = os.path.realpath(destino_base)
        if real_base == os.path.realpath(DATA_DIR) or real_base.startswith(os.path.realpath(DATA_DIR) + os.sep):
            return None                                   # no tiene sentido «fuera» dentro de los datos
        # Una subcarpeta por instalación: varias tiendas pueden usar el mismo Drive.
        sitio = re.sub(r'[^\w\- ]', "", _nombre_instalacion()).strip() or "InTeks Display"
        carpeta = os.path.join(destino_base, sitio)
        destino = os.path.join(carpeta, nombre_zip)
        if os.path.exists(destino):
            return None
        os.makedirs(carpeta, exist_ok=True)
        tmp = destino + ".tmp"
        shutil.copyfile(origen, tmp)
        with zipfile.ZipFile(tmp) as z:                   # se comprueba lo copiado, no lo de origen
            if z.testzip() is not None or BACKUP_FICHA not in z.namelist():
                raise RuntimeError("la copia externa no es válida")
        os.replace(tmp, destino)
        try:
            guardar = max(1, int(cfg.get("copia_auto_dias", COPIAS_GUARDAR_DEFECTO)))
        except (TypeError, ValueError):
            guardar = COPIAS_GUARDAR_DEFECTO
        viejas = sorted(f for f in os.listdir(carpeta)
                        if f.startswith(COPIAS_PREFIJO) and f.endswith(".zip"))
        for f in viejas[:-guardar]:
            try: os.remove(os.path.join(carpeta, f))
            except OSError: pass
        log(f"  [copias] copia externa: {destino}")
        return destino
    except Exception as e:
        log(f"  [copias] no se pudo hacer la copia externa: {e}")
        return None

def _destino_seguro(nombre):
    """Ruta absoluta dentro de DATA_DIR, o None si el zip intenta salirse.

    Un zip malicioso puede traer nombres como '../../algo': extraerlo a pelo
    escribiría fuera de la carpeta de datos. Se comprueba la ruta YA RESUELTA,
    porque comprobar solo si empieza por '..' se esquiva de varias formas.
    """
    nombre = nombre.replace("\\", "/")
    if nombre.endswith("/"):
        return None
    if nombre != BACKUP_FICHA and nombre not in BACKUP_JSONS \
            and not nombre.startswith("uploads/"):
        return None                          # nada fuera de lo que ponemos nosotros
    destino = os.path.realpath(os.path.join(DATA_DIR, *nombre.split("/")))
    base = os.path.realpath(DATA_DIR)
    if destino != base and not destino.startswith(base + os.sep):
        return None
    return destino

def restaurar_backup(datos):
    """Vuelca una copia sobre la carpeta de datos. Devuelve (ok, mensaje)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
    except Exception:
        return False, "Ese archivo no es una copia de seguridad válida."
    if BACKUP_FICHA not in z.namelist():
        return False, "Ese zip no es una copia de InTeks Display."
    try:
        ficha = json.loads(z.read(BACKUP_FICHA))
    except Exception:
        ficha = {}
    if ficha.get("app") != "InTeks Display":
        return False, "Ese zip no es una copia de InTeks Display."

    # El rev que había aquí antes de volcar nada. La copia trae el suyo, de otra
    # instalación, y si por casualidad coincidiera con el de un panel abierto ese
    # panel podría escribir encima de lo recién restaurado creyéndose al día.
    try:
        rev_local = int(load_json(CONTENT_FILE).get("rev", 0))
    except Exception:
        rev_local = 0

    escritos, saltados = 0, 0
    for nombre in z.namelist():
        if nombre == BACKUP_FICHA:
            continue
        destino = _destino_seguro(nombre)
        if not destino:
            saltados += 1
            log(f"  [copia] entrada descartada por ruta insegura: {nombre}")
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with z.open(nombre) as origen, open(destino, "wb") as salida:
            shutil.copyfileobj(origen, salida)
        escritos += 1
    # El contador solo puede crecer: así ningún panel que estuviera abierto antes
    # de la restauración puede tener un rev que el servidor acepte como válido.
    try:
        with file_lock:
            content = load_json(CONTENT_FILE)
            if content:
                content["rev"] = max(rev_local, int(content.get("rev", 0))) + 1
                save_json(CONTENT_FILE, content)
    except Exception as e:
        log(f"  [copia] no se pudo ajustar rev tras restaurar: {e}")

    log(f"  [copia] restaurados {escritos} archivo(s)"
        + (f", {saltados} descartado(s)" if saltados else ""))
    return True, f"{escritos} archivo(s) restaurados"

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
        nombre = (reg.get("name") if isinstance(reg, dict) else None) or sid
        for p in scr.get("playlist", []):
            if isinstance(p, dict) and p.get("type") != "package" and p.get("id"):
                anotar(p["id"], "screen", sid, nombre)
    for pkg in content.get("packages", []):
        for item_id in pkg.get("itemIds", []):
            anotar(item_id, "package", pkg.get("id", ""), pkg.get("name") or pkg.get("id", ""))
    return usos

def expandir_paquetes(playlist, content):
    """Sustituye las referencias a paquetes por los contenidos que tienen AHORA.

    Un paquete es un grupo vivo, no un «pegar varios de golpe». Antes el admin
    copiaba los contenidos dentro de la playlist de cada pantalla y no dejaba
    ninguna huella de dónde venían: editar el paquete después no cambiaba nada,
    y no había forma de arreglarlo porque no existía el dato que dijera qué
    diapositivas salieron de qué paquete.

    Ahora la playlist guarda {"type": "package", "pkg_id": ...} y se resuelve
    aquí, al servirla. Así no hay copias que puedan quedarse viejas: es
    imposible por construcción, y el player no se entera de nada porque recibe
    la lista ya resuelta.

    Nada de esto puede tumbar una pantalla: un paquete borrado, un contenido que
    ya no está en la librería o un paquete vacío se saltan en silencio y el
    resto de la playlist sigue reproduciéndose.
    """
    paquetes = {p.get("id"): p for p in content.get("packages", []) if p.get("id")}
    biblioteca = {i.get("id"): i for i in content.get("items", []) if i.get("id")}

    def contenidos_de(pkg):
        # Formato actual: [{"id", "duration"}]. El antiguo guardaba solo ids.
        if isinstance(pkg.get("items"), list):
            return [{"id": x.get("id"), "duration": x.get("duration")}
                    for x in pkg["items"] if isinstance(x, dict)]
        return [{"id": i, "duration": None} for i in pkg.get("itemIds", [])]

    salida = []
    for entrada in playlist or []:
        if not isinstance(entrada, dict) or entrada.get("type") != "package":
            salida.append(entrada)
            continue
        pkg = paquetes.get(entrada.get("pkg_id"))
        if not pkg:
            continue                       # paquete borrado: el resto sigue
        for sel in contenidos_de(pkg):
            item = biblioteca.get(sel.get("id"))
            if not item:
                continue                   # contenido borrado de la librería
            copia = dict(item)
            copia["duration"] = sel.get("duration") or item.get("duration") or 8
            copia["from_pkg"] = pkg.get("id")
            salida.append(copia)
    return salida

def filtrar_vigentes(playlist, hoy):
    """Quita lo caducado y lo que aún no ha empezado.

    Las fechas van en las claves `desde` y `hasta` de cada elemento, en formato
    YYYY-MM-DD, y ambas son inclusivas: el último día todavía se ve. Comparar
    cadenas ISO funciona porque ese formato ordena igual como texto que como
    fecha; nada de parsear.

    Regla de oro: si el filtro se lo lleva TODO, se devuelve la lista sin
    filtrar. Una promo vieja en el escaparate es malo, pero un escaparate
    apagado es peor y encima no se distingue de una avería.
    """
    def valida(f):
        f = str(f or "").strip()
        # Una fecha mal escrita se ignora en vez de esconder contenido sin que
        # nadie sepa por qué.
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

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def pantalla_activa(cfg, ahora):
    """¿Debería estar encendida esta pantalla ahora mismo?

    Copia en Python de isScreenActive() de player.html. La duplicación es
    inevitable —son dos lenguajes— y hace falta porque el servidor tiene que
    decidir si avisa de una pantalla caída: sin esto avisaría de todas las
    pantallas del mundo a las tres de la madrugada.

    tests/casos-horario.json es el mismo corpus que ejecuta schedule.test.js.
    Si esta función y la de JavaScript se separan, uno de los dos tests peta.
    """
    cfg = cfg or {}
    horario = cfg.get("schedule") or {}
    hoy = time.strftime("%Y-%m-%d", ahora)
    dia_cfg = None
    for f in horario.get("holidays") or []:
        if isinstance(f, dict) and f.get("date") == hoy:
            dia_cfg = f
            break

    # 24/7: siempre encendida, salvo en una fecha especial puesta a propósito.
    if cfg.get("always_on") and dia_cfg is None:
        return True
    if not horario:
        return True

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

    Que Telegram esté caído, sin cobertura o mal configurado no puede tumbar el
    servidor de una tienda: lo que está en juego es un aviso, no el escaparate.
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

RECORDATORIOS_FILE = os.path.join(DATA_DIR, "avisos.json")

def _leer_recordatorios():
    """Cuándo se recordó por última vez cada tablero. {id_modulo: epoch}

    Va a disco y no en memoria: si el equipo se reinicia a las 4 de la mañana,
    un estado en memoria se perdería y el vigilante mandaría el recordatorio
    ahí mismo. Es un archivo diminuto y no entra en la copia de seguridad —es
    estado de este equipo, no configuración.
    """
    d = load_json(RECORDATORIOS_FILE)
    return d.get("tasas", {}) if isinstance(d, dict) else {}

def _guardar_recordatorios(tasas):
    try:
        save_json(RECORDATORIOS_FILE, {"tasas": tasas})
    except Exception as e:
        log(f"  [avisos] no se pudo guardar el estado: {e}")

ALERT_TASAS_DESDE = "09:00"
ALERT_TASAS_HASTA = "22:00"
ALERT_TASAS_CADA_H = 1

def _en_franja(actual, inicio, fin):
    """¿Está `actual` («HH:MM») dentro de la franja? Admite cruzar medianoche."""
    if inicio <= fin:
        return inicio <= actual <= fin
    return actual >= inicio or actual <= fin

def toca_recordar(ahora_tm, ultimo_ts, inicio, fin, cada_horas):
    """¿Toca insistir ahora con unas tasas viejas?

    Las tasas viejas no son un suceso, son una tarea pendiente: siguen ahí
    hasta que alguien las actualice, y un solo aviso a las 9 de la mañana se
    pierde entre las notificaciones del día. Por eso se recuerda cada X horas
    dentro de una franja, en vez de una única vez.

    Y por eso hay franja: insistir a las tres de la madrugada no consigue que
    nadie actualice nada, solo que se silencien los avisos para siempre.
    """
    actual = time.strftime("%H:%M", ahora_tm)
    if not _en_franja(actual, inicio, fin):
        return False
    if not ultimo_ts:
        return True                          # nunca avisado de esto
    ahora_ts = time.mktime(ahora_tm)
    try:
        cada = float(cada_horas)
    except (TypeError, ValueError):
        cada = ALERT_TASAS_CADA_H
    if cada <= 0:
        # Un único aviso al día: se compara el día del calendario, no las horas
        # transcurridas, para que a las 9 de la mañana siguiente vuelva a sonar
        # aunque el de ayer fuera a las 21:00.
        return time.strftime("%Y-%m-%d", ahora_tm) != \
               time.strftime("%Y-%m-%d", time.localtime(ultimo_ts))
    return (ahora_ts - ultimo_ts) >= cada * 3600

def _nombre_instalacion():
    return str(load_config().get("installation_name", "") or "InTeks Display")

def revisar_avisos():
    """Una pasada del vigilante. Devuelve la lista de avisos enviados."""
    enviados = []
    try:
        cfg = load_config()
        if not str(cfg.get("telegram_token", "") or "").strip():
            return enviados                     # apagado: no se habla con nadie
        try:
            minutos = max(1, int(cfg.get("alert_offline_min", ALERT_OFFLINE_MIN_DEFECTO)))
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
                continue                        # el panel no es una pantalla
            debe_estar = pantalla_activa(pantallas.get(sid, {}), ahora_tm)
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
        # Se miran las playlists ya expandidas: un módulo de divisas puede venir
        # dentro de un paquete y ahí también cuenta.
        desde = str(cfg.get("alert_tasas_desde", "") or ALERT_TASAS_DESDE)
        hasta = str(cfg.get("alert_tasas_hasta", "") or ALERT_TASAS_HASTA)
        cada_h = cfg.get("alert_tasas_cada_h", ALERT_TASAS_CADA_H)
        recordatorios = _leer_recordatorios()

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
                try:
                    horas = 24.0 if horas in (None, "") else float(horas)
                    ts = float(it.get("updated_at") or 0)
                except (TypeError, ValueError):
                    continue
                if not horas or not ts:
                    continue
                caducado = (ahora_ts - ts) > horas * 3600
                if not caducado:
                    # Ya se actualizaron: se olvida para que la próxima vez que
                    # caduquen vuelva a avisar desde cero.
                    if recordatorios.pop(mid, None) is not None:
                        _guardar_recordatorios(recordatorios)
                    continue
                if not toca_recordar(ahora_tm, recordatorios.get(mid, 0),
                                     desde, hasta, cada_h):
                    continue
                dias = int((ahora_ts - ts) // 86400)
                cuanto = f"{dias} día(s)" if dias else "más del plazo"
                if enviar_telegram(
                        f"⚠ {sitio}\n\nEl tablero «{it.get('name') or mid}» "
                        f"lleva {cuanto} sin actualizarse."):
                    recordatorios[mid] = ahora_ts
                    _guardar_recordatorios(recordatorios)
                    enviados.append(("tasas", mid))
    except Exception as e:
        # El vigilante no puede matar al servidor pase lo que pase.
        log(f"  [avisos] error al revisar: {e}")
    return enviados

def _vigilante():
    """Hilo de fondo. Una pasada por minuto."""
    while True:
        # Primero la copia (si hoy no hay): al arrancar el equipo se hace ya.
        try: copia_automatica_si_toca()
        except Exception: pass            # ya quedó en el log
        copia_externa_si_toca()
        time.sleep(60)
        revisar_avisos()

# ── Bot de Telegram (solo lectura) ──────────────────────────────────────────
# Telegram era de una sola dirección: el servidor empuja avisos, nunca
# contesta nada. Esto añade un único comando, /estado, que responde con lo
# mismo que ya sabe el vigilante de avisos —pantallas caídas, tableros
# vencidos— sin exponer nada nuevo: nada de reiniciar el servidor ni de dar
# el PIN de emparejamiento por chat.
TELEGRAM_GETUPDATES_API = "https://api.telegram.org/bot{token}/getUpdates"

def _telegram_get_updates(token, offset=None, timeout=25):
    """Long-poll de mensajes nuevos. Nunca lanza: devuelve [] si algo falla."""
    try:
        qs = f"timeout={int(timeout)}"
        if offset is not None:
            qs += f"&offset={int(offset)}"
        req = urllib.request.Request(
            f"{TELEGRAM_GETUPDATES_API.format(token=token)}?{qs}",
            headers={"User-Agent": f"InTeks-Display/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=timeout + 10) as r:
            datos = json.loads(r.read().decode("utf-8", "replace"))
        return datos.get("result", []) if datos.get("ok") else []
    except Exception as e:
        log(f"  [bot] no se pudo leer mensajes: {e}")
        return []

def _formatear_duracion(segundos):
    segundos = max(0, int(segundos))
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    if dias:
        return f"{dias}d {horas}h"
    if horas:
        return f"{horas}h {minutos}min"
    return f"{minutos}min"

def construir_estado():
    """Texto de `/estado`: mismos datos que ya usa `revisar_avisos()`, en un
    único mensaje corto -pensado para leerse entero en un móvil."""
    ahora_ts = time.time()
    screens = load_json(SCREENS_FILE)
    content = load_json(CONTENT_FILE)
    pantallas = content.get("screens", {})

    lineas_p = []
    for sid, reg in sorted(screens.items()):
        if sid == "admin":
            continue
        if reg.get("connected"):
            lineas_p.append(f"✅ {sid} — en línea")
        else:
            visto = reg.get("last_seen") or 0
            desde = _formatear_duracion(ahora_ts - visto) if visto else "?"
            lineas_p.append(f"❌ {sid} — caída desde hace {desde}")
    if not lineas_p:
        lineas_p = ["(sin pantallas registradas)"]

    lineas_t = []
    vistos = set()
    for sid, cfg_p in pantallas.items():
        for it in expandir_paquetes(cfg_p.get("playlist", []), content):
            if not isinstance(it, dict) or it.get("type") != "fx":
                continue
            mid = it.get("id") or it.get("name") or "fx"
            if mid in vistos:
                continue
            vistos.add(mid)
            nombre = it.get("name") or mid
            try:
                horas_venc = it.get("stale_hours")
                horas_venc = 24.0 if horas_venc in (None, "") else float(horas_venc)
                ts = float(it.get("updated_at") or 0)
            except (TypeError, ValueError):
                ts, horas_venc = 0, 24.0
            if not ts:
                lineas_t.append(f"⚠ {nombre} — sin actualizar nunca")
                continue
            caducado = horas_venc and (ahora_ts - ts) > horas_venc * 3600
            marca = "⚠" if caducado else "✅"
            lineas_t.append(f"{marca} {nombre} — hace {_formatear_duracion(ahora_ts - ts)}")
    if not lineas_t:
        lineas_t = ["(sin tableros de divisas)"]

    disco = estado_disco()
    disco_txt = f"{disco.get('pct_usado', 0)}% usado, {disco.get('libre_mb', 0)} MB libres"
    if disco.get("aviso"):
        disco_txt += " ⚠"

    return (f"📋 {_nombre_instalacion()}\n\n"
            f"🖥 Pantallas\n" + "\n".join(lineas_p) + "\n\n"
            f"💱 Tableros\n" + "\n".join(lineas_t) + "\n\n"
            f"InTeks Display {APP_VERSION} · disco {disco_txt}")

def _responder_mensaje(texto, chat_id, chat_autorizado):
    """Qué contestar, o None si no hay que contestar nada.

    Un bot es público: cualquiera que sepa su nombre puede escribirle. Solo
    se responde al chat configurado en el panel; a cualquier otro, silencio
    total -ni siquiera un error, para no confirmarle a un desconocido que el
    bot existe y está vivo.
    """
    if str(chat_id) != str(chat_autorizado):
        return None
    comando = (texto or "").strip().lower().split("@")[0]   # tolera /estado@nombrebot
    if comando == "/estado":
        return construir_estado()
    return "No entendí. Escribe /estado para ver pantallas y tableros."

def _bot_loop():
    """Hilo de fondo: long-poll de Telegram, contesta solo /estado.

    Relee la configuración en cada vuelta -igual que enviar_telegram()- para
    que activar el bot o cambiar el token/chat desde el panel se note sin
    reiniciar el servidor. Con el token vacío no llama a Telegram para nada:
    se limita a dormir y comprobar de nuevo.
    """
    offset = None
    token_previo = None
    while True:
        try:
            cfg = load_config()
            token = str(cfg.get("telegram_token", "") or "").strip()
            chat_autorizado = str(cfg.get("telegram_chat_id", "") or "").strip()
            if not token or not chat_autorizado:
                token_previo = None
                time.sleep(5)
                continue

            if token != token_previo:
                # Token nuevo (o primer arranque tras encenderlo): descarta lo
                # pendiente sin contestarlo. Si no, un /estado de ayer -Telegram
                # guarda lo no leído 24h- se contestaría con datos de ahora
                # como si fuera de este momento, y eso confunde más que ayuda.
                pendientes = _telegram_get_updates(token, offset=-1, timeout=0)
                offset = (pendientes[-1]["update_id"] + 1) if pendientes else None
                token_previo = token

            for upd in _telegram_get_updates(token, offset, timeout=25):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                if chat_id is None:
                    continue
                respuesta = _responder_mensaje(msg.get("text"), chat_id, chat_autorizado)
                if respuesta:
                    enviar_telegram(respuesta)
        except Exception as e:
            # Mismo criterio que el vigilante de avisos: esto no puede tumbar
            # el servidor, y una vuelta que falla no debe convertirse en un
            # bucle que grita sin parar.
            log(f"  [bot] error en el hilo: {e}")
            time.sleep(5)

def notify_unlink(screen_id):
    """Le dice a la pantalla que olvide quién era, sin borrar su configuración.

    Es lo contrario de notify_deleted: allí la pantalla desaparece; aquí sigue
    existiendo con su playlist, su horario y su rotación, y lo único que se
    suelta es el dispositivo. Sirve para reenlazar un televisor desde el panel
    sin ir a tocarlo con el mando.

    Devuelve a CUÁNTOS aparatos se le pudo entregar. Quien llama lo necesita:
    si no había nadie escuchando —la tele estaba apagada— hay que apuntar el
    desenlace para dárselo cuando aparezca, o se pierde en silencio.
    """
    entregados = 0
    with sse_lock:
        for wfile in list(sse_clients.get(screen_id, [])):
            try:
                wfile.write(f"data: unlink:{screen_id}\n\n".encode())
                wfile.flush()
                entregados += 1
            except Exception: pass
    return entregados

def _leer_json_crudo(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)

def load_json(path):
    """Lee un JSON. Un archivo que NO existe es «vacío» ({}); uno que existe y
    está dañado NO: devolver {} sin más haría que el siguiente guardado
    escribiera encima y borrara todo (un corte de luz puede dejar un archivo a
    medias o a cero bytes). Se recupera de la copia .bak, y lo dañado se aparta
    con otro nombre, nunca se borra."""
    with file_lock:
        try:
            return _leer_json_crudo(path)
        except FileNotFoundError:
            return {}
        except Exception as e:
            log(f"  [datos] {os.path.basename(path)} está dañado: {e}")
        aparte = f"{path}.corrupto-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(path, aparte)
            log(f"  [datos] el dañado se aparta como {os.path.basename(aparte)}")
        except OSError:
            pass
        try:
            datos = _leer_json_crudo(path + ".bak")
            shutil.copyfile(path + ".bak", path)
            log(f"  [datos] recuperado de {os.path.basename(path)}.bak")
            return datos
        except Exception:
            log(f"  [datos] sin copia .bak utilizable de {os.path.basename(path)}")
            return {}

def save_json(path, data):
    # Escritura atómica + lock: evita corrupción si dos peticiones escriben a la vez
    with file_lock:
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush(); os.fsync(f.fileno())      # a disco de verdad antes de sustituir
            # La versión buena anterior se guarda como .bak (solo si lo que hay
            # ahora se lee: no se pisa una copia buena con una dañada).
            try:
                _leer_json_crudo(path)
                shutil.copyfile(path, path + ".bak")
            except Exception:
                pass
            os.replace(tmp, path)
        except Exception:
            try:
                if os.path.exists(tmp): os.remove(tmp)
            except Exception: pass
            raise

class RevConflicto(Exception):
    """El panel intentó guardar con una foto que ya no es la actual.

    Se lanza desde dentro de contenido_en_edicion() para abortar la escritura:
    la excepción atraviesa el yield y el guardián no llega a guardar nada. Es la
    única forma de comprobar y decidir sin soltar el lock en medio, que es
    justo el hueco que este cambio existe para cerrar.
    """
    def __init__(self, actual): self.actual = actual

class ArchivoNoExiste(Exception):
    """Se lanza dentro de contenido_en_edicion() para abortar sin guardar ni subir rev."""

class NadaQueAnadir(Exception):
    pass

class EtiquetasDeMas(Exception):
    """Un archivo se pasaría de 10 etiquetas: aborta sin guardar."""

def _clave_nombre(s):
    """Clave de comparación de carpetas/etiquetas: sin mayúsculas ni acentos."""
    s = unicodedata.normalize("NFD", str(s).strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))

def _lista_tags(it):
    """Las etiquetas de un item como lista; si 'tags' no es una lista, vacío."""
    t = it.get("tags")
    return list(t) if isinstance(t, list) else []

class DestinoNoExiste(Exception):
    """Archivo o pantalla inexistente: aborta sin guardar; lleva el mensaje para el 404."""

@contextlib.contextmanager
def contenido_en_edicion():
    """Lee, deja modificar y guarda content.json sin soltar el lock en medio.

    El hueco entre load_json y save_json era la carrera: dos peticiones
    simultáneas (una subida y las tasas de la extensión, por ejemplo) leían la
    misma foto y la segunda escribía encima de la primera. Medido antes de
    existir esto: de 20 subidas a la vez sobrevivían 6.

    Funciona sin tocar load_json ni save_json porque file_lock es un RLock:
    las adquisiciones de dentro se vuelven anidamientos inofensivos en el mismo
    hilo. Con un Lock() normal esto se bloquearía a sí mismo.

    Sube 'rev' en cada escritura. Como es el único camino que escribe el
    archivo, ningún manejador futuro puede olvidarse de subirlo.

    Si el cuerpo lanza, la excepción atraviesa el yield y NO se guarda nada.
    Ojo: salir con 'return' desde dentro del with sí guarda.
    """
    with file_lock:
        content = load_json(CONTENT_FILE)
        yield content
        content["rev"] = int(content.get("rev", 0)) + 1
        save_json(CONTENT_FILE, content)

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

def nombre_seguro(name):
    """Nombre de archivo válido también en Windows: sin separadores, sin
    caracteres reservados (<>:"/\\|?*) ni de control, sin puntos/espacios al
    final y de 120 caracteres como mucho (conservando la extensión)."""
    nombre = os.path.basename(str(name).replace("\\", "/"))
    nombre = "".join("_" if (c in '<>:"/\\|?*' or ord(c) < 32) else c for c in nombre)
    nombre = nombre.strip().rstrip(". ")
    # Un .part es una subida a medias: el arranque los borra, así que un archivo
    # de verdad no puede acabar así (p. ej. una descarga de Firefox sin terminar).
    if nombre.lower().endswith(".part"):
        nombre = nombre[:-5] + "_part"
    if len(nombre) > 120:
        raiz, ext = os.path.splitext(nombre)
        ext = ext[:20]
        nombre = (raiz[:120 - len(ext)] + ext).rstrip(". ")
    return nombre or "archivo"

def reservar_nombre(nombre):
    """Primer número libre y el .part reservado a la vez, bajo candado: dos
    subidas simultáneas no pueden elegir el mismo nombre. Devuelve
    (filename, destino, parcial); el .part ya existe (vacío)."""
    with _subida_lock:
        idx = len(os.listdir(UPLOAD_DIR))
        while (os.path.exists(os.path.join(UPLOAD_DIR, f"{idx:04d}_{nombre}"))
               or os.path.exists(os.path.join(UPLOAD_DIR, f"{idx:04d}_{nombre}.part"))):
            idx += 1
        filename = f"{idx:04d}_{nombre}"
        destino = os.path.join(UPLOAD_DIR, filename)
        parcial = destino + ".part"
        open(parcial, "xb").close()
    return filename, destino, parcial

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
    nombre = nombre_seguro(name)
    primero = lector.read(min(SUBIDA_TROZO, length))
    tipo = detectar_tipo(primero)
    if not tipo:
        raise SubidaRechazada(415, "No es una imagen ni un vídeo que se pueda mostrar "
                                   "(vale JPG, PNG, GIF, WEBP, MP4, MOV o WEBM)")
    filename, destino, parcial = reservar_nombre(nombre)
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
    try:
        with contenido_en_edicion() as content:
            content.setdefault("items", []).append(item)
    except BaseException:
        # Sin entrada en la Librería el archivo quedaría huérfano en uploads/.
        try: os.remove(destino)
        except OSError: pass
        raise
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

def _migrar_rev():
    """Añade 'rev' al content.json que viene de una versión anterior.

    Sin esto, la comprobación optimista de POST /api/content deja el panel en
    bucle: carga un contenido sin rev, guarda sin rev, recibe 409
    rev_stale_client, recarga, y vuelve a empezar. Dejaría el panel inutilizable
    en toda instalación actualizada desde 1.0.9, que son todas.
    """
    try:
        with file_lock:
            content = load_json(CONTENT_FILE)
            if content and "rev" not in content:
                content["rev"] = 0
                save_json(CONTENT_FILE, content)
                log("  [contenido] migrado: se añade rev 0 (venía de una versión anterior)")
    except Exception as e:
        log(f"  [contenido] no se pudo migrar rev: {e}")

def _limpiar_pantalla_fantasma():
    """Quita el 'admin' que las versiones anteriores inscribían como pantalla.

    El panel escucha los avisos por SSE con screen=admin. El servidor le dejaba
    pasar —debe hacerlo— pero además lo apuntaba en screens.json, así que el
    panel salía en su propia lista como una tele que nadie ha enchufado nunca.
    Ya no se apunta; esto se lleva el que quedó de instalaciones anteriores.

    Va aquí, y no junto a los init_file de arriba, porque load_json y save_json
    todavía no existen en ese punto del archivo.
    """
    try:
        screens = load_json(SCREENS_FILE)
        if "admin" in screens:
            del screens["admin"]
            save_json(SCREENS_FILE, screens)
            log("  [limpieza] retirada la pantalla fantasma 'admin' del registro")
    except Exception as e:
        # Nada de tragarse esto en silencio: si la limpieza falla, el panel
        # sigue apareciendo en su propia lista y hay que poder saber por qué.
        log(f"  [limpieza] no se pudo retirar 'admin' del registro: {e}")

_limpiar_pantalla_fantasma()
_migrar_rev()

def ruta_decodificada(ruta):
    """Deshace el porcentaje-encoding de la ruta pedida.

    urlparse() NO decodifica. Sin esto, el navegador pide
    «/uploads/Tarifas%20sujetas…mp4» y el servidor busca en disco un archivo
    cuyo nombre contenga literalmente «%20»: no existe, y devuelve 404 sin
    decir por qué. Cualquier archivo con espacios o acentos era invisible —el
    vídeo no se reproducía y su miniatura salía negra— mientras que los
    «0000_1.png» funcionaban de casualidad, por no llevar ningún carácter que
    necesite codificarse.

    Decodificar mete «../» por la puerta de atrás (%2e%2e%2f), pero los dos
    manejadores de archivos comprueban la ruta YA RESUELTA con realpath contra
    su carpeta base, así que el intento se queda fuera igual. Hay tests que lo
    fijan, incluidas las variantes codificadas.
    """
    try:
        return unquote(ruta, errors="surrogatepass")
    except Exception:
        return ruta

DISCO_AVISO_PCT = 90

def estado_disco():
    """Espacio en la unidad donde viven los datos.

    Cuando el disco de la tienda se llena fallan las subidas y puede fallar la
    escritura de content.json, que es como perder la configuración. No hay
    ningún síntoma hasta que ya pasó, así que conviene avisar antes.

    Se mira DATA_DIR y no la carpeta del programa: los vídeos y las imágenes
    son lo que crece, y viven ahí.
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

# ── Arranque automático (desde 1.0.21) ──────────────────────────────────────
# La casilla «Iniciar con Windows» del panel guardaba un valor en config.json
# que nadie leía: el arranque real lo daba (o no) la tarea programada que
# registra el instalador, y la casilla no tenía ninguna conexión con eso.
# Quien la desmarcaba creyendo apagar el arranque no apagaba nada, y quien la
# marcaba se quedaba sin servidor tras un corte de luz igual. Ahora la casilla
# consulta y toca la tarea de Windows de verdad.
TAREA_AUTOARRANQUE = "InTeks Display"
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # no aplica fuera de Windows

def _tarea_autoarranque_estado():
    """¿Existe la tarea de autoarranque en Windows, y está activada? Consulta
    real vía schtasks, no lo que diga config.json."""
    try:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", TAREA_AUTOARRANQUE, "/FO", "LIST"],
            capture_output=True, text=True, timeout=10, creationflags=_SIN_VENTANA)
        if r.returncode != 0:
            return {"existe": False, "activa": False}
        # El nombre del campo de estado cambia con el idioma de Windows
        # ("Estado"/"Status"); buscar que NO diga deshabilitada es más
        # robusto que adivinar el valor exacto en cada idioma.
        salida = r.stdout.lower()
        activa = "disabled" not in salida and "deshabilitad" not in salida
        return {"existe": True, "activa": activa}
    except Exception as e:
        return {"existe": None, "activa": None, "error": str(e)}

def _fijar_autoarranque(activar):
    """Enciende o apaga el arranque automático DE VERDAD, tocando la tarea
    programada de Windows en vez de un valor decorativo.

    Nunca lanza: es una acción desde el panel y no puede tumbar el servidor
    si falla -y falla fácil, porque hace falta ser administrador para tocar
    el Programador de tareas. Devuelve (ok, mensaje); mensaje vacío si salió
    bien.
    """
    estado = _tarea_autoarranque_estado()
    try:
        if activar:
            if estado.get("existe"):
                r = subprocess.run(
                    ["schtasks", "/Change", "/TN", TAREA_AUTOARRANQUE, "/Enable"],
                    capture_output=True, text=True, timeout=10, creationflags=_SIN_VENTANA)
            else:
                # No existe -instalación antigua, o se desmarcó en el
                # instalador-: se crea de cero reutilizando registrar-tarea.ps1
                # en vez de duplicar aquí cómo encuentra pythonw.exe y los
                # ajustes de reintento que ya tiene ese script.
                ps1 = os.path.join(APP_DIR, "registrar-tarea.ps1")
                if not os.path.exists(ps1):
                    ps1 = os.path.join(APP_DIR, "installer", "registrar-tarea.ps1")
                if not os.path.exists(ps1):
                    return False, "No se encuentra registrar-tarea.ps1."
                r = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                     "-File", ps1, "-AppDir", APP_DIR],
                    capture_output=True, text=True, timeout=30, creationflags=_SIN_VENTANA)
        else:
            if not estado.get("existe"):
                return True, ""             # ya estaba apagado
            r = subprocess.run(
                ["schtasks", "/Change", "/TN", TAREA_AUTOARRANQUE, "/Disable"],
                capture_output=True, text=True, timeout=10, creationflags=_SIN_VENTANA)
        if r.returncode != 0:
            detalle = (r.stderr or r.stdout or "error desconocido").strip()
            return False, detalle[:300]
        return True, ""
    except Exception as e:
        return False, str(e)
# ── fin del arranque automático ─────────────────────────────────────────────

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return "127.0.0.1"

# ─────────────────────────────────────────────────────────────
#  URLs amigables
# ─────────────────────────────────────────────────────────────
def mdns_host():
    """Nombre mDNS de la instalación, ej. 'signage.local'."""
    return f"{config.get('mdns_name', 'signage')}.local"

def url_for(path="", host=None, port=None):
    """Construye una URL omitiendo el puerto cuando es el 80 (HTTP por defecto)."""
    host = host or mdns_host()
    port = PORT if port is None else port
    return f"http://{host}{path}" if port == 80 else f"http://{host}:{port}{path}"

# ─────────────────────────────────────────────────────────────
#  Responder mDNS (Bonjour/Zeroconf) — stdlib pura
#  Permite que las tablets entren a http://signage.local en vez
#  de teclear la IP. mDNS = DNS sobre UDP multicast 224.0.0.251:5353.
# ─────────────────────────────────────────────────────────────
MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353

def _dns_encode_name(name):
    """'signage.local' -> b'\\x07signage\\x05local\\x00'"""
    out = b""
    for label in name.split("."):
        b = label.encode("utf-8")
        out += bytes([len(b)]) + b
    return out + b"\x00"

def _dns_read_name(data, offset):
    """Lee un nombre DNS (saltando compresión) y devuelve (nombre, nuevo_offset)."""
    labels = []
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if (length & 0xC0) == 0xC0:   # puntero de compresión (raro en queries)
            offset += 2
            break
        offset += 1
        labels.append(data[offset:offset + length].decode("utf-8", "ignore"))
        offset += length
    return ".".join(labels), offset

def _mdns_response(fqdn, ip):
    """Paquete de respuesta mDNS con un registro A (nombre -> ip)."""
    header = struct.pack(">HHHHHH", 0, 0x8400, 0, 1, 0, 0)   # QR=1, AA=1; 1 answer
    answer = _dns_encode_name(fqdn)
    answer += struct.pack(">HHIH", 1, 0x8001, 120, 4)        # type A, class IN+cache-flush, TTL 120
    answer += socket.inet_aton(ip)
    return header + answer

def start_mdns_responder():
    """Lanza en segundo plano el anunciador mDNS. Si falla (otro responder ya
    ocupa el 5353, ej. Bonjour de Apple), el servidor sigue y se usa la IP."""
    fqdn = mdns_host().lower()

    def run():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            sock.bind(("", MDNS_PORT))
            mreq = socket.inet_aton(MDNS_ADDR) + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as e:
            log(f"  [mDNS] No disponible ({e}). Las tablets deberán usar la IP.")
            return

        # Anuncio inicial no solicitado para aparecer rápido en la red
        try: sock.sendto(_mdns_response(fqdn, get_ip()), (MDNS_ADDR, MDNS_PORT))
        except Exception: pass
        log(f"  [mDNS] Anunciando '{fqdn}' en la red local")

        while True:
            try:
                data, _ = sock.recvfrom(2048)
                if len(data) < 12:
                    continue
                _, flags, qdcount = struct.unpack(">HHH", data[:6])
                if flags & 0x8000:        # es una respuesta, no una pregunta
                    continue
                offset, matched = 12, False
                for _ in range(qdcount):
                    qname, offset = _dns_read_name(data, offset)
                    if offset + 4 > len(data):
                        break
                    qtype, _qclass = struct.unpack(">HH", data[offset:offset + 4])
                    offset += 4
                    if qname.lower() == fqdn and qtype in (1, 255):  # A o ANY
                        matched = True
                if matched:
                    sock.sendto(_mdns_response(fqdn, get_ip()), (MDNS_ADDR, MDNS_PORT))
            except Exception:
                continue

    threading.Thread(target=run, daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): log(f"  {self.address_string()} -> {args[0]}")
    def cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type, X-SignalOS-Token")
    def do_OPTIONS(self): self.send_response(200); self.cors(); self.end_headers()

    # ── Autenticación ────────────────────────────────────────
    def _get_cookie(self, name):
        raw = self.headers.get("Cookie", "") or ""
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == name: return v
        return None

    def is_authed(self):
        """True si hay sesión válida (cookie del panel) o api_token válido (cabecera)."""
        tok = self._get_cookie(SESSION_COOKIE)
        if tok and verify_session_token(tok): return True
        api = self.headers.get("X-SignalOS-Token", "")
        real = get_api_token()
        if real and api and hmac.compare_digest(api, real): return True
        return False

    def require_auth(self):
        """Si no está autenticado, responde 401 y devuelve False (cortar el handler)."""
        if self.is_authed(): return True
        self.send_response(401); self.send_header("Content-Type","application/json")
        self.cors(); self.end_headers()
        self.wfile.write(json.dumps({"error":"no autorizado","auth_required":True}).encode())
        return False

    def ip_cliente(self):
        """IP desde la que viene de verdad la petición. Las que llegan por el túnel de
        Cloudflare salen de 127.0.0.1 (cloudflared corre aquí): sin esto, todo internet
        compartiría el mismo contador de intentos de login y uno solo bloquearía al resto.
        La cabecera solo se cree si la conexión es local; desde otro equipo se ignora."""
        directa = self.client_address[0]
        if directa in ("127.0.0.1", "::1"):
            real = (self.headers.get("CF-Connecting-IP") or "").strip()
            if real and len(real) <= 45 and re.fullmatch(r"[0-9a-fA-F:.]+", real):
                return real
        return directa

    def _set_session_cookie(self, token, max_age=SESSION_TTL):
        self.send_header("Set-Cookie",
            f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age={max_age}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = ruta_decodificada(parsed.path)
        qs = parse_qs(parsed.query)

        # ── API: estado de autenticación (público; lo usa login.html)
        if path == "/api/auth-status":
            info = {"has_password": admin_has_password(), "authed": self.is_authed()}
            body = json.dumps(info).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: token de API para integraciones (extensión)  (solo admin)
        if path == "/api/admin-info":
            if not self.require_auth(): return
            body = json.dumps({"api_token": get_api_token() or ""}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: obtener PIN activo para enlace  (solo admin: revela el PIN)
        if path == "/api/pin":
            if not self.require_auth(): return
            # Leer el PIN no lo cambia: regenerarlo es un POST (/api/pin/regenerate),
            # porque un GET lo puede disparar cualquier enlace o imagen de una web.
            pin = get_active_pin()
            expires_in = max(0, int(pin_state["expires_at"] - time.time()))
            info = {"pin": pin, "expires_in": expires_in, "blocked": time.time() < pin_state["blocked_until"]}
            body = json.dumps(info).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: obtener información del servidor (IP + puerto + mDNS)
        if path == "/api/info":
            ip = get_ip()
            info = {
                "version": APP_VERSION,
                "port": PORT,
                "ip": ip,
                "mdns_host": mdns_host(),
                "mdns_name": config.get("mdns_name", "signage"),
                "player_url": url_for("/player.html", host=ip),
                "pair_url": url_for("/pair"),               # nombre amigable (signage.local)
                "pair_url_ip": url_for("/pair", host=ip),   # respaldo por IP (siempre funciona)
                "disk": estado_disco()
            }
            body = json.dumps(info).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: obtener configuración  (solo admin)
        if path == "/api/config":
            if not self.require_auth(): return
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                # El valor de verdad es lo que diga Windows, no lo guardado: si
                # alguien borró la tarea a mano, o el instalador no la registró
                # porque se desmarcó esa casilla, config.json podía seguir
                # diciendo que sí sin que fuera cierto.
                cfg["autostart"] = bool(_tarea_autoarranque_estado().get("activa"))
                body = json.dumps(cfg).encode()
                self.send_response(200); self.send_header("Content-Type","application/json")
                self.cors(); self.end_headers(); self.wfile.write(body); return
            except Exception:
                self.send_response(500); self.end_headers(); return

        # ── API: obtener contenido  (solo admin)
        if path == "/api/content":
            if not self.require_auth(): return
            body = json.dumps(load_json(CONTENT_FILE)).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: ¿hay una version mas nueva publicada?
        if path == "/api/update-check":
            if not self.require_auth(): return
            url = url_actualizaciones()
            if not url:
                datos = {"enabled": False, "current": APP_VERSION,
                         "update_available": False}
            else:
                if qs.get("force", ["0"])[0] == "1":
                    _update_cache["datos"] = None      # el boton "comprobar ahora"
                datos = comprobar_actualizacion(url)
            body = json.dumps(datos).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: descargar una copia de seguridad
        if path == "/api/backup":
            if not self.require_auth(): return
            try:
                media = qs.get("media", ["1"])[0] != "0"
                datos = crear_backup(media)
                nombre = time.strftime("InTeks-Display-copia-%Y-%m-%d-%H%M.zip")
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{nombre}"')
                self.send_header("Content-Length", str(len(datos)))
                self.send_header("Cache-Control", "no-store")
                self.cors(); self.end_headers(); self.wfile.write(datos)
            except Exception as e:
                log(f"  [copia] error al generar: {e}")
                self.send_response(500); self.cors(); self.end_headers()
            return

        # ── API: televisores LG con la mini-app y lo que les queda de modo desarrollador
        if path == "/api/lg-tvs":
            if not self.require_auth(): return
            body = json.dumps({"tvs": lg_tvs_estado()}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: estado de la instalación de la mini-app en un LG (la pide el panel)
        if path == "/api/lg-instalar":
            if not self.require_auth(): return
            host = (self.headers.get("Host") or "").strip()
            nombre, _, puerto = host.partition(":")
            if not nombre or nombre in ("localhost", "127.0.0.1", "[::1]") or nombre.endswith(".localhost"):
                nombre = get_ip()
            sugerido = "http://" + nombre + (":" + puerto if puerto and puerto != "80" else "") + "/"
            d = lg_instalar_estado()
            d.update(disponible=lg_script_instalar() is not None, servidor_sugerido=sugerido)
            body = json.dumps(d).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: estado del acceso remoto (lo pide la tarjeta del panel)
        if path == "/api/acceso-remoto":
            if not self.require_auth(): return
            body = json.dumps(acceso_estado()).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: pantallas encendidas esperando a que se les ponga nombre
        if path == "/api/pair-pending":
            if not self.require_auth(): return
            body = json.dumps({"pending": pending_list()}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

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

        # ── API: obtener pantallas registradas  (solo admin / extensión con token)
        if path == "/api/screens":
            if not self.require_auth(): return
            pantallas = load_json(SCREENS_FILE)
            for sid, p in pantallas.items():
                if isinstance(p, dict) and sid in ahora_pantalla:
                    p["now"] = ahora_pantalla[sid]
                if isinstance(p, dict) and sid in fallos_video:
                    p["video_fallo"] = fallos_video[sid]
            body = json.dumps(pantallas).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── Videowall: estado de la pantalla que manda, para la que la sigue. Público
        #    como /api/playlist; solo da qué contenido y qué segundo, nada más.
        if path == "/api/wall-sync":
            sid = qs.get("screen", [""])[0]
            scr = load_json(CONTENT_FILE).get("screens", {}).get(sid, {})
            est = None
            if scr.get("mode") == "wall":
                ids, pos = wall_de(scr, sid)
                if pos > 0:
                    est = wall_estado.get(ids[0])
            body = json.dumps({"ok": True, "estado": est, "ahora": time.time()}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: obtener playlist de una pantalla
        if path == "/api/playlist":
            sid = qs.get("screen",["default"])[0]
            content = load_json(CONTENT_FILE)
            screens_cfg = content.get("screens", {})
            scr = screens_cfg.get(sid, {})
            mode = scr.get("mode", "independent")
            playlist = []
            # Los paquetes se resuelven aquí, en el único sitio por el que pasan
            # todas las pantallas. Lo que sale por esta puerta ya son contenidos.
            # Primero se expanden los paquetes y DESPUÉS se filtra por fechas:
            # así una promo caducada que vive dentro de un paquete también
            # desaparece. Al revés, el paquete entraría entero sin mirar.
            origen = scr.get("playlist", [])
            muro_ids, muro_pos = wall_de(scr, sid) if mode == "wall" else ([], 0)
            if mode == "wall" and muro_pos > 0:
                # Videowall: las que siguen enseñan lo mismo que la primera, sincronizadas con
                # ella; su propia playlist no se usa (y así nunca se desfasan los contenidos).
                maestra = screens_cfg.get(muro_ids[0], {})
                if maestra.get("mode") == "wall" and maestra.get("playlist"):
                    origen = maestra.get("playlist", [])
            resuelta = filtrar_vigentes(
                expandir_paquetes(origen, content),
                time.strftime("%Y-%m-%d"))
            if mode == "wall":
                wall_pos = scr.get("wall_pos", "left")
                playlist = [dict(item, wall_mode=True, wall_pos=wall_pos,
                                 wall_idx=muro_pos, wall_n=len(muro_ids)) for item in resuelta]
            else:
                playlist = resuelta
            # La versión viaja aquí para que la pantalla note que el servidor se
            # ha actualizado y recargue: el archivo del disco cambia al
            # instalar, pero la página que el televisor lleva horas abierta
            # sigue ejecutando el código viejo. Ver debeRecargarPorVersion() en
            # player.html.
            cfg_pantalla = dict(scr, wall_idx=muro_pos, wall_n=len(muro_ids)) if mode == "wall" else scr
            result = {"playlist": playlist, "mode": mode, "screen_id": sid,
                      "config": cfg_pantalla, "version": APP_VERSION}
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(json.dumps(result).encode()); return

        # ── SSE: stream de actualizaciones
        if path == "/api/events":
            sid = qs.get("screen",["default"])[0]
            self.send_response(200)
            self.send_header("Content-Type","text/event-stream")
            self.send_header("Cache-Control","no-cache")
            self.send_header("Connection","keep-alive")
            self.cors(); self.end_headers()
            # Anti-resurrección: si la pantalla no existe (borrada o nunca creada/emparejada),
            # pedir al player que vaya a emparejar en vez de re-crearla. 'admin' siempre permitido.
            screens = load_json(SCREENS_FILE)
            content_screens = load_json(CONTENT_FILE).get("screens", {})
            if sid != "admin" and sid not in screens and sid not in content_screens:
                try:
                    self.wfile.write(f"data: deleted:{sid}\n\n".encode()); self.wfile.flush()
                except Exception: pass
                return
            # Desenlace pendiente: se pidio soltar el aparato mientras estaba
            # apagado, asi que el aviso no llego a nadie y quedo apuntado. Es la
            # primera oportunidad de darselo. Se borra la marca al entregarla: si
            # no, un aparato reenlazado a este mismo nombre se desenlazaria solo
            # una y otra vez.
            if sid != "admin" and screens.get(sid, {}).get("unlink_pending"):
                try:
                    self.wfile.write(f"data: unlink:{sid}\n\n".encode()); self.wfile.flush()
                except Exception: pass
                screens[sid].pop("unlink_pending", None)
                screens[sid]["connected"] = False
                save_json(SCREENS_FILE, screens)
                log(f"  [enlace] '{sid}' encendio: se le entrega el desenlace pendiente")
                return
            # Registrar cliente
            with sse_lock:
                if sid not in sse_clients: sse_clients[sid] = []
                sse_clients[sid].append(self.wfile)
            # Registrar/actualizar la pantalla en el registro.
            #
            # 'admin' NO es una pantalla: es el panel, que escucha por aquí para
            # enterarse de los cambios. Se le deja escuchar (arriba) pero no se
            # le inscribe, o aparecería en su propia lista de pantallas como una
            # tele fantasma que nadie ha enchufado nunca.
            if sid != "admin":
                if sid not in screens:
                    screens[sid] = {"id": sid, "connected": True, "last_seen": time.time()}
                else:
                    screens[sid]["connected"] = True; screens[sid]["last_seen"] = time.time()
                save_json(SCREENS_FILE, screens)
            try:
                self.wfile.write(b"data: connected\n\n"); self.wfile.flush()
                while True:
                    time.sleep(10)
                    self.wfile.write(b": ping\n\n"); self.wfile.flush()
                    # Solo se escribe si hay algo que escribir. Antes se
                    # reescribía screens.json cada 10 s por cada cliente
                    # conectado, aunque no cambiara nada.
                    screens = load_json(SCREENS_FILE)
                    if sid in screens:
                        screens[sid]["last_seen"] = time.time()
                        save_json(SCREENS_FILE, screens)
            except Exception:
                with sse_lock:
                    if sid in sse_clients and self.wfile in sse_clients[sid]:
                        sse_clients[sid].remove(self.wfile)
                    # Esta conexion murio, pero puede no ser la unica: un
                    # EventSource reconecta solo, y la reconexion puede llegar
                    # -y quedar registrada aqui- ANTES de que este hilo se
                    # entere de que la suya se cayo (hasta 10 s, el intervalo
                    # del ping). Si ya hay otra conexion viva para esta
                    # pantalla, marcarla caida ahora pisaria el connected=True
                    # que puso esa conexion nueva, y se quedaria marcada
                    # offline para siempre aunque siguiera respondiendo -es
                    # justo lo que sufria "Pantalla Exterior (LG)": el panel
                    # la daba por caida mientras seguia sirviendo contenido.
                    sigue_viva = bool(sse_clients.get(sid))
                if not sigue_viva:
                    screens = load_json(SCREENS_FILE)
                    if sid in screens:
                        screens[sid]["connected"] = False
                        save_json(SCREENS_FILE, screens)
            return

        # ── Servir uploads (con soporte de HTTP Range -> vídeo en streaming + seeking)
        if path.startswith("/uploads/"):
            # Los subidos viven en DATA_DIR, no junto al programa.
            fp = os.path.join(DATA_DIR, *path.lstrip("/").split("/"))
            # Seguridad: la ruta resuelta debe quedar dentro de uploads/ (evita ../ traversal)
            uploads_base = os.path.realpath(UPLOAD_DIR)
            if not os.path.realpath(fp).startswith(uploads_base + os.sep) or not os.path.isfile(fp):
                self.send_response(404); self.end_headers(); return
            mime,_ = mimetypes.guess_type(fp)
            mime = mime or "application/octet-stream"
            file_size = os.path.getsize(fp)
            range_header = self.headers.get("Range")
            try:
                if range_header and range_header.startswith("bytes="):
                    # Petición parcial (vídeo pide trozos): responder 206 Partial Content
                    rng = range_header.split("=",1)[1].split(",")[0].strip()
                    start_s, _, end_s = rng.partition("-")
                    start = int(start_s) if start_s else 0
                    end = int(end_s) if end_s else file_size - 1
                    start = max(0, start); end = min(end, file_size - 1)
                    if start > end:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.end_headers(); return
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Cache-Control", "public, max-age=604800")  # caché del navegador (resiliencia offline)
                    self.cors(); self.end_headers()
                    with open(fp,"rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk: break
                            self.wfile.write(chunk); remaining -= len(chunk)
                else:
                    # Petición completa: 200 en streaming, anunciando que aceptamos Range
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "public, max-age=604800")  # caché del navegador (resiliencia offline)
                    self.cors(); self.end_headers()
                    with open(fp,"rb") as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk: break
                            self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # el navegador cortó la descarga (cambio de slide/seek); es normal con vídeo
            return

        # ── Página de emparejamiento
        if path == "/pair":
            # Anclado a APP_DIR, no al directorio de trabajo. Este handler se
            # quedó con la ruta relativa cuando se anclaron los demás estáticos:
            # arrancado desde otra carpeta devolvía 404 y la pantalla no podía
            # ni pedir su código.
            fp = os.path.join(APP_DIR, "pair.html")
            if os.path.exists(fp):
                mime,_ = mimetypes.guess_type(fp)
                with open(fp,"rb") as f: data=f.read()
                self.send_response(200); self.send_header("Content-Type", mime or "text/html")
                self.send_header("Content-Length", str(len(data)))
                # no-cache y no no-store, igual que el resto: "revalida" en vez
                # de "prohibido guardar copia". Ver la resiliencia del player.
                self.send_header("Cache-Control", "no-cache")
                self.cors(); self.end_headers(); self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers(); self.wfile.write(b"404 - pair.html no encontrado")
            return

        # ── El panel de control exige sesión: sin ella, a la pantalla de login.
        #    (Sólo protege la PÁGINA admin.html; las APIs ya se protegen una a una.)
        if path in ("/admin.html", "/admin"):
            if not self.is_authed():
                dest = "/login.html" if admin_has_password() else "/login.html?setup=1"
                self.send_response(302); self.send_header("Location", dest)
                self.cors(); self.end_headers(); return

        # ── Archivos estáticos — SÓLO extensiones web públicas (nunca .py/.json/.log/etc.)
        #    y siempre dentro del directorio de la app (evita ../ traversal y fuga de pin.json/config/código)
        #    Raíz "/" → index.html (router de pantallas), NO el panel admin.
        fp = path.lstrip("/") or "index.html"
        ALLOWED_EXT = (".html",".css",".js",".png",".jpg",".jpeg",".gif",".webp",".svg",".ico",".woff",".woff2",".ttf",".map")
        # Anclado a APP_DIR y no al directorio de trabajo: así los estáticos se
        # sirven igual arranque quien arranque el servidor y desde donde sea.
        base = os.path.realpath(APP_DIR)
        target = os.path.realpath(os.path.join(APP_DIR, *fp.split("/")))
        inside = (target == base or target.startswith(base + os.sep))
        if inside and fp.lower().endswith(ALLOWED_EXT) and os.path.isfile(target):
            mime,_ = mimetypes.guess_type(target)
            with open(target,"rb") as f: data=f.read()
            self.send_response(200); self.send_header("Content-Type", mime or "text/html")
            self.send_header("Content-Length", str(len(data)))
            # HTML/JS/CSS: revalidar SIEMPRE contra el servidor, pero permitir
            # que el navegador conserve una copia. Antes iba con "no-store", que
            # no significa "revalida" sino "prohibido guardar": con el servidor
            # caído la pantalla no tenía ni la página anterior que mostrar.
            # "no-cache" da lo mismo en caliente y salva la pantalla en frío.
            if fp.lower().endswith((".html",".js",".css")):
                self.send_header("Cache-Control", "no-cache")
            self.cors(); self.end_headers(); self.wfile.write(data)
        else: self.send_response(404); self.end_headers(); self.wfile.write(b"404")

    def _subida_raw(self, parsed, length):
        """POST /api/upload-raw?name=... El cuerpo es el archivo. La sesión ya se
        comprobó en do_POST."""
        nombre = (parse_qs(parsed.query).get("name", [""])[0])
        lector = _Lector(self.rfile)
        # Solo aquí: un cliente parado no puede retener el hilo (y su .part) para
        # siempre. En todo el manejador no, porque /api/events es de larga vida.
        self.connection.settimeout(120)
        try:
            item = guardar_subida_raw(lector, length, nombre)
            codigo, cuerpo = 200, {"ok": True, "item": item}
        except SubidaRechazada as e:
            codigo, cuerpo = e.codigo, {"ok": False, "error": e.mensaje}
            sin_leer = length - lector.leido
            # Cerrar con cuerpo sin leer provoca un reset TCP que puede borrar la
            # respuesta (el panel vería «se perdió la conexión» en vez del motivo).
            # Se vacía el cuerpo entero salvo el 413 (ya filtrado en el panel) o
            # si pasa del tope.
            if sin_leer > 0:
                if e.codigo != 413 and sin_leer <= 4 * 1024 ** 3:
                    try:
                        while sin_leer > 0:
                            d = self.rfile.read(min(SUBIDA_TROZO, sin_leer))
                            if not d:
                                self.close_connection = True
                                break
                            sin_leer -= len(d)
                    except OSError:
                        self.close_connection = True; return
                else:
                    self.close_connection = True    # no se lee, se corta
        except (TimeoutError, socket.timeout, ConnectionError):
            # Cliente parado o desconectado: como una subida cortada. El .part ya
            # lo borró guardar_subida_raw; no hay a quién contestar ni traza que dar.
            self.close_connection = True
            return
        except Exception as e:
            codigo, cuerpo = 500, {"ok": False, "error": f"Error del servidor: {e}"}
            self.close_connection = True
        self.send_response(codigo); self.send_header("Content-Type", "application/json")
        if self.close_connection: self.send_header("Connection", "close")
        self.cors(); self.end_headers()
        self.wfile.write(json.dumps(cuerpo).encode())

    def do_POST(self):
        parsed = urlparse(self.path)
        path = ruta_decodificada(parsed.path)
        # Content-Length mentiroso: uno negativo hace que rfile.read espere
        # hasta que el cliente cierre, y uno no numérico lanzaba excepción.
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length < 0: raise ValueError
        except ValueError:
            self.send_response(400); self.send_header("Content-Type","application/json")
            self.send_header("Connection","close")
            self.cors(); self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "Content-Length no válido"}).encode())
            return
        # Quién llama se comprueba ANTES de leer el cuerpo: si no, cualquiera de
        # la red mandaba 512 MB sin sesión y se cargaban en RAM. Las rutas
        # públicas sí se leen, pero con un techo pequeño.
        if path not in POST_PUBLICOS and not self.require_auth():
            return
        # Techo de seguridad: el cuerpo se carga ENTERO en memoria, así que un
        # envío gigante (una restauración con vídeos, una subida equivocada)
        # tumbaría el servidor de la tienda. Se rechaza antes de leerlo.
        if path in POST_PUBLICOS and length > MAX_BODY_PUBLICO:
            self.send_response(413)
            self.send_header("Content-Type","application/json")
            self.send_header("Connection","close")
            self.cors(); self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "Envío demasiado grande"}).encode())
            return
        # La subida en bruto se lee por trozos, no se carga en RAM: no le
        # aplica MAX_BODY_BYTES (manda upload_max_mb).
        if path == "/api/upload-raw":
            self._subida_raw(parsed, length)
            return
        if length > MAX_BODY_BYTES:
            self.send_response(413)
            self.send_header("Content-Type","application/json")
            self.send_header("Connection","close")
            self.cors(); self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error":
                f"El envío es demasiado grande ({length // (1024*1024)} MB). "
                f"El máximo son {MAX_BODY_BYTES // (1024*1024)} MB."}).encode())
            return
        body = self.rfile.read(length)

        def ok(extra={}):
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers()
            self.wfile.write(json.dumps({"ok":True,**extra}).encode())
        def err(e):
            self.send_response(500); self.cors(); self.end_headers()
            self.wfile.write(json.dumps({"error":str(e)}).encode())
        def jresp(code, obj):
            self.send_response(code); self.send_header("Content-Type","application/json")
            self.cors(); self.end_headers(); self.wfile.write(json.dumps(obj).encode())

        # ── Autenticación: iniciar sesión
        if path == "/api/login":
            try:
                d = json.loads(body or "{}")
                if not admin_has_password():
                    jresp(409, {"ok": False, "error": "no_password", "setup_required": True}); return
                ip = self.ip_cliente()
                espera = login_bloqueado(ip)
                if espera:
                    self.send_response(429); self.send_header("Content-Type","application/json")
                    self.send_header("Retry-After", str(espera)); self.cors(); self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error":
                        f"Demasiados intentos. Prueba de nuevo en {espera} segundos."}).encode())
                    return
                if verify_admin_password(d.get("password", "")):
                    login_acierto(ip)
                    self.send_response(200); self.send_header("Content-Type","application/json")
                    self._set_session_cookie(make_session_token()); self.cors(); self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode())
                else:
                    login_fallo(ip)
                    jresp(401, {"ok": False, "error": "Contraseña incorrecta"})
            except Exception as e: err(e)
            return

        # ── Autenticación: crear/cambiar contraseña
        #    Permitido si aún no hay contraseña (primer arranque) o si hay sesión válida.
        if path == "/api/set-password":
            try:
                d = json.loads(body or "{}")
                new = (d.get("password", "") or "").strip()
                if admin_has_password() and not self.is_authed():
                    jresp(401, {"ok": False, "error": "no autorizado"}); return
                if len(new) < PASSWORD_MIN:
                    jresp(400, {"ok": False, "error": f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres"}); return
                a = set_admin_password(new)
                self.send_response(200); self.send_header("Content-Type","application/json")
                self._set_session_cookie(make_session_token()); self.cors(); self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "api_token": a.get("api_token")}).encode())
            except Exception as e: err(e)
            return

        # ── Autenticación: cerrar sesión
        if path == "/api/logout":
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0")
            self.cors(); self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            return

        # ── La pantalla pide un código de emparejamiento. Público a la fuerza:
        #    una pantalla sin enlazar no tiene sesión ni token. No expone nada,
        #    solo devuelve un número al azar que no sirve de nada sin que un
        #    administrador autenticado lo reclame desde el panel.
        if path == "/api/pair-request":
            try:
                known_as = str(json.loads(body or "{}").get("known_as", "") or "")
            except Exception:
                known_as = ""          # cuerpo vacío o mal formado: sin pista, y ya está
            code, token = pending_new(known_as)
            jresp(200, {"ok": True, "code": code, "token": token}); return

        # ── La pantalla pregunta si ya la han enlazado, y con qué nombre.
        if path == "/api/pair-status":
            try:
                d = json.loads(body or "{}")
                nombre = pending_status(d.get("token", ""))
                if nombre is None and d.get("token", "") not in pending_screens:
                    jresp(200, {"ok": True, "expired": True}); return
                jresp(200, {"ok": True, "claimed": bool(nombre), "screen": nombre or ""}); return
            except Exception as e: err(e)
            return

        # ── La pantalla avisa de qué diapositiva está mostrando ahora. Público como
        #    el resto de lo que hacen las pantallas, y solo en MEMORIA: escribir
        #    screens.json en cada cambio de diapositiva gastaría el disco por un
        #    dato que no vale la pena conservar. Solo vale para pantallas ya
        #    registradas, para que nadie llene la memoria con nombres inventados.
        if path == "/api/wall-sync":
            try:
                d = json.loads(body or "{}")
                sid = str(d.get("screen", "") or "") if isinstance(d, dict) else ""
                scr = load_json(CONTENT_FILE).get("screens", {}).get(sid, {})
                if scr.get("mode") != "wall" or wall_de(scr, sid)[1] != 0:
                    jresp(200, {"ok": False}); return        # solo manda la primera
                try: t = max(0.0, min(float(d.get("t", 0) or 0), 86400.0))
                except Exception: t = 0.0
                wall_estado[sid] = {"id": str(d.get("id", "") or "")[:200], "t": t,
                                    "video": d.get("video") is True, "at": time.time()}
                jresp(200, {"ok": True}); return
            except Exception as e: err(e); return

        if path == "/api/screen-now":
            try:
                d = json.loads(body or "{}")
                if not isinstance(d, dict):
                    jresp(400, {"ok": False, "error": "Cuerpo no válido"}); return
                sid = str(d.get("screen", "") or "")
                if sid not in load_json(SCREENS_FILE):
                    jresp(404, {"ok": False, "error": "Pantalla desconocida"}); return
                # Vídeo que esta pantalla no consigue reproducir (o que ya se ve bien).
                # Va aparte de «ahora» porque ese se sobrescribe en cada diapositiva y el
                # aviso tiene que seguir en el panel hasta que el vídeo funcione.
                vf = d.get("video_fallo")
                if isinstance(vf, dict):
                    fallos_video[sid] = {"id": str(vf.get("id", "") or "")[:200],
                                         "name": str(vf.get("name", "") or "")[:80],
                                         "motivo": str(vf.get("motivo", "") or "")[:80],
                                         "at": time.time()}
                    log(f"  [video] {sid}: no reproduce «{fallos_video[sid]['name']}» ({fallos_video[sid]['motivo']})")
                    jresp(200, {"ok": True}); return
                vok = d.get("video_ok")
                if vok is not None:
                    if sid in fallos_video and fallos_video[sid]["id"] == str(vok)[:200]:
                        del fallos_video[sid]
                    jresp(200, {"ok": True}); return
                ahora_pantalla[sid] = {
                    "id": str(d.get("id", "") or "")[:200],
                    "name": str(d.get("name", "") or "")[:80],
                    "type": str(d.get("type", "") or "")[:20],
                    "at": time.time(),
                }
                # Con la pantalla apagada o en una fecha especial: la imagen que se ve.
                img = str(d.get("img", "") or "")[:300]
                if img:
                    ahora_pantalla[sid]["img"] = img
                # Versión del APK de la caja (solo la manda el reproductor dentro del APK).
                apk = str(d.get("apk", "") or "")[:20]
                if apk:
                    ahora_pantalla[sid]["apk"] = apk
                jresp(200, {"ok": True}); return
            except Exception as e: err(e)
            return

        # ── PUERTA DE CONTROL: todo lo que sigue exige sesión válida (cookie) o api_token.
        #    Excepción: /api/pair es público (las pantallas se enlazan con el PIN).
        if path != "/api/pair" and not self.require_auth():
            return

        # ── Fusión de filas de divisas conservando el orden del admin ──────
        # El usuario ordena su tablero a mano y ese orden es suyo: una
        # actualización de tasas no puede reordenarlo aunque la extensión mande
        # las filas en otro orden, que es lo que hacía al sustituirlas en bloque.
        # La clave es país + moneda, no solo la moneda: un tablero de remesas
        # lleva varias filas en dólares (Ecuador, Venezuela...) y confundirlas
        # mezclaría sus tasas.
        def fusionar_filas(existentes, entrantes):
            def clave(r):
                return (str(r.get("country", "")).strip().lower(),
                        str(r.get("code", "")).strip().upper())
            pendientes = {}
            for r in entrantes:
                pendientes.setdefault(clave(r), r)
            out = []
            for e in existentes or []:            # primero, en el orden del admin
                k = clave(e)
                if k in pendientes:
                    out.append(pendientes.pop(k))
            for r in entrantes:                   # las nuevas, al final
                k = clave(r)
                if k in pendientes:
                    out.append(pendientes.pop(k))
            return out

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
                # El guardián se abre aquí y no arriba a propósito: entre la
                # lectura y este punto hay cuatro 'return' de validación, y
                # envolverlos subiría rev en un emparejamiento rechazado.
                with contenido_en_edicion() as content:
                    content.setdefault("screens", {}).setdefault(
                        nombre, {"mode": "independent", "playlist": []})
                verbo = "reenlazada" if modo == "reenlazar" else "enlazada"
                log(f"  [enlace] pantalla '{nombre}' {verbo} con el código {code}")
                ok({"screen_name": nombre, "modo": modo})
            except Exception as e: err(e)
            return

        # ── Subir archivo a librería global
        if path == "/api/upload":
            try:
                d = json.loads(body)
                raw_data = d["data"]
                if "," in raw_data: raw_data = raw_data.split(",",1)[1]
                raw = base64.b64decode(raw_data)
                # Solo el nombre, sin carpetas: "../../x" no sale de uploads/.
                name = nombre_seguro(d["name"])
                # Primer número libre bajo candado (y sin chocar con un .part).
                filename, destino, parcial = reservar_nombre(name)
                try:
                    with open(parcial, "wb") as f: f.write(raw)
                    os.replace(parcial, destino)
                except BaseException:
                    try: os.remove(parcial)
                    except OSError: pass
                    raise
                item = {"id": filename, "name": name, "type": d["type"],
                        "src": f"/uploads/{filename}", "size": len(raw)}
                with contenido_en_edicion() as content:
                    content.setdefault("items",[]).append(item)
                ok({"item": item})
            except Exception as e: err(e)
            return

        # ── Guardar contenido completo (items de librería + screens)
        if path == "/api/content":
            try:
                d = json.loads(body)
                enviado = d.get("rev")
                try:
                    with contenido_en_edicion() as content:
                        # La comprobación va DENTRO del guardián: si se hiciera
                        # fuera, entre comprobar y escribir cabría la escritura
                        # del otro equipo, que es el hueco que esto cierra.
                        actual = int(content.get("rev", 0))
                        if enviado is None or int(enviado) != actual:
                            raise RevConflicto(actual)
                        if isinstance(d.get("items"), list): content["items"] = d["items"]
                        if isinstance(d.get("screens"), dict): content["screens"] = d["screens"]
                        if isinstance(d.get("packages"), list): content["packages"] = d["packages"]
                except RevConflicto as c:
                    if enviado is None:
                        # Pestaña con un admin.html cacheado de antes de esta
                        # versión: no puede colarse saltándose la comprobación.
                        # Al recibir esto el panel recarga y se cura solo.
                        log("  [contenido] guardado rechazado: el panel no manda rev "
                            "(admin.html cacheado de una version anterior)")
                        jresp(409, {"ok": False, "error": "rev_stale_client"}); return
                    log(f"  [contenido] guardado rechazado: el panel traia rev {enviado}, "
                        f"en disco hay {c.actual}")
                    jresp(409, {"ok": False, "error": "rev_conflict", "rev": c.actual}); return
                notify_all()
                ok()
            except Exception as e: err(e)
            return

        # ── Guardar configuración completa de pantallas
        if path == "/api/screens/config":
            try:
                d = json.loads(body)
                enviado = d.get("rev")
                try:
                    with contenido_en_edicion() as content:
                        # Mismo hueco que /api/content: 'd' es una foto completa
                        # de content["screens"], así que sin esta comprobación un
                        # panel con datos viejos borra en silencio lo que guardó
                        # otro (playlist asignada, videowall...).
                        actual = int(content.get("rev", 0))
                        if enviado is None or int(enviado) != actual:
                            raise RevConflicto(actual)
                        nuevo = d.get("screens", {})
                        content["screens"] = nuevo
                except RevConflicto as c:
                    if enviado is None:
                        jresp(409, {"ok": False, "error": "rev_stale_client"}); return
                    jresp(409, {"ok": False, "error": "rev_conflict", "rev": c.actual}); return
                # Notificar a las pantallas afectadas y a otros paneles admin:
                # el panel escucha en sse_clients["admin"], que queda fuera de
                # 'nuevo' porque nunca es un id de pantalla real.
                for sid in nuevo.keys(): notify_screen(sid)
                notify_screen("admin")
                ok()
            except Exception as e: err(e)
            return

        # ── Eliminar una pantalla (del registro Y de la configuración)
        if path == "/api/screens/delete":
            try:
                d = json.loads(body)
                sid = d["id"]
                # Quitar del registro de pantallas conectadas (screens.json)
                screens = load_json(SCREENS_FILE)
                if sid in screens:
                    del screens[sid]
                    save_json(SCREENS_FILE, screens)
                # Quitar de la configuración de contenido (content.json -> screens)
                # Solo se entra al guardián si hay algo que quitar: subir rev en un
                # borrado que no borra nada invalidaría a los paneles abiertos y les
                # provocaría un 409 espurio en su siguiente guardado.
                if sid in load_json(CONTENT_FILE).get("screens", {}):
                    with contenido_en_edicion() as content:
                        content.get("screens", {}).pop(sid, None)
                # Avisar a la tablet de esa pantalla para que se desconecte (vuelva a emparejar)
                notify_deleted(sid)
                notify_screen("admin")  # que otros paneles abiertos refresquen la lista
                # Soltar cualquier conexión SSE asociada a esa pantalla
                with sse_lock:
                    sse_clients.pop(sid, None)
                ok()
            except Exception as e: err(e)
            return

        # ── Mandar un mensaje de prueba, para saber si los avisos funcionan
        if path == "/api/alert-test":
            try:
                enviado = enviar_telegram(
                    f"🔔 {_nombre_instalacion()}\n\n"
                    "Prueba de avisos. Si lees esto, está bien configurado.")
                ok({"enviado": bool(enviado)})
            except Exception as e: err(e)
            return

        # ── Restaurar una copia de seguridad (el cuerpo es el zip en crudo)
        if path == "/api/restore":
            try:
                ok_r, msg = restaurar_backup(body)
                if not ok_r:
                    jresp(400, {"ok": False, "error": msg}); return
                # Las pantallas tienen que recoger la configuración restaurada
                notify_all()
                ok({"mensaje": msg})
            except Exception as e: err(e)
            return

        # ── Soltar el dispositivo de una pantalla, sin borrar la pantalla
        if path == "/api/screen-unlink":
            try:
                d = json.loads(body or "{}")
                sid = str(d.get("screen", "")).strip()
                screens = load_json(SCREENS_FILE)
                content = load_json(CONTENT_FILE)
                if not sid or (sid not in screens and sid not in content.get("screens", {})):
                    jresp(400, {"ok": False, "error": "Esa pantalla no existe"}); return
                entregados = notify_unlink(sid)
                with sse_lock:
                    sse_clients.pop(sid, None)
                if sid in screens:
                    screens[sid]["connected"] = False
                    # Se apunta SIEMPRE, aunque el aviso pareciera entregado.
                    #
                    # No se puede confiar en el recuento: el servidor no sabe que
                    # una conexion esta muerta hasta que le falla una escritura, y
                    # las primeras se limitan a encolarse en el buffer del sistema
                    # sin error (ver tests/test_sse_reconexion.py). Una tele cuyo
                    # wifi acaba de caerse contaria como "entregado" y el desenlace
                    # se perderia igual.
                    #
                    # Dejarlo puesto no molesta: "desenlazada" es un estado que
                    # dura hasta que alguien reenlace ese nombre, y pair-claim
                    # rehace la entrada entera, con lo que la marca desaparece.
                    screens[sid]["unlink_pending"] = True
                    save_json(SCREENS_FILE, screens)
                log(f"  [enlace] '{sid}' desenlazada"
                    + (": su dispositivo volvera a pedir codigo" if entregados
                       else ": estaba apagada, se le dira al encender"))
                ok({"screen": sid})
            except Exception as e: err(e)
            return

        # ── Reiniciar el reproductor de una pantalla (recarga su página)
        if path == "/api/screen-reload":
            try:
                d = json.loads(body or "{}")
                sid = str(d.get("id", "")).strip()
                if not sid:
                    jresp(400, {"ok": False, "error": "Falta la pantalla"}); return
                if sid not in load_json(SCREENS_FILE) and sid not in load_json(CONTENT_FILE).get("screens", {}):
                    jresp(404, {"ok": False, "error": "Esa pantalla no existe"}); return
                entregados = notify_reload(sid)
                log(f"  [reproductor] reinicio pedido para '{sid}' ({entregados} conexión/es)")
                ok({"screen": sid, "entregado": entregados > 0})
            except Exception as e: err(e)
            return

        # ── Actualizar SOLO el módulo de divisas de las pantallas (desde la extensión Chrome)
        if path == "/api/fx-update":
            try:
                d = json.loads(body)
                rows = d.get("rows", [])
                screen_ids = d.get("screen_ids", [])
                # Sin valor por defecto a propósito: None significa "el cliente
                # no lo envía, no lo toques". La extensión manda solo las filas.
                title = d.get("title")
                base_currency = d.get("base_currency")
                # Qué módulo tocar cuando una pantalla tiene más de uno (p.ej. Western
                # Union y Ria en la misma pantalla). Antes, sin esto, se actualizaban
                # TODOS los módulos tipo fx de la pantalla con las mismas filas: cada
                # envío para uno pisaba también al otro.
                item_id = str(d.get("item_id") or "").strip()
                updated_at = time.time()
                if not rows:
                    err("rows requerido y no puede estar vacío"); return
                updated_screens = []
                with contenido_en_edicion() as content:
                    screens = content.get("screens", {})
                    targets = screen_ids if screen_ids else list(screens.keys())
                    touched_ids = set()
                    for sid in targets:
                        if sid not in screens: continue
                        playlist = screens[sid].get("playlist", [])
                        fx_items = [it for it in playlist if it.get("type") == "fx"]
                        # Sin item_id y con más de un módulo en la pantalla no hay forma
                        # de saber cuál quería el usuario: mejor no tocar ninguno que
                        # adivinar y pisar el que no era.
                        if not item_id and len(fx_items) > 1:
                            continue
                        target_items = [it for it in fx_items if it.get("id") == item_id] if item_id else fx_items
                        for item in target_items:
                            touched_ids.add(item.get("id"))
                            # Actualizar SOLO las tasas y lo que venga explícito.
                            # Antes se pisaban siempre título y moneda base, así que
                            # cada envío desde la extensión borraba lo que el usuario
                            # había configurado en el admin.
                            item["rows"] = fusionar_filas(item.get("rows"), rows)
                            if title: item["title"] = title
                            if base_currency: item["base_currency"] = base_currency
                            item["updated_at"] = updated_at
                        if not target_items:
                            # Módulo nuevo: aquí sí hacen falta valores por defecto.
                            new_title = title or "Tipos de cambio"
                            new_id = item_id or f"fx_{int(updated_at)}"
                            playlist.append({
                                "id": new_id, "name": new_title, "type": "fx",
                                "title": new_title, "base_currency": base_currency or "EUR", "rows": rows,
                                "duration": 15, "bg": "#07182b", "color": "#ffffff", "updated_at": updated_at
                            })
                            touched_ids.add(new_id)
                        screens[sid]["playlist"] = playlist
                        updated_screens.append(sid)
                    # Sincronizar la copia de la LIBRERÍA de los módulos tocados.
                    # El contenido vive duplicado: content["items"] es la librería y
                    # cada playlist guarda su propia copia. El admin propaga de la
                    # librería hacia las pantallas al guardar, así que si la librería
                    # se queda con las tasas viejas, la primera edición en el admin
                    # deshace silenciosamente lo que acaba de hacer la extensión.
                    for item in content.get("items", []):
                        if item.get("type") == "fx" and item.get("id") in touched_ids:
                            item["rows"] = fusionar_filas(item.get("rows"), rows)
                            if title: item["title"] = title
                            if base_currency: item["base_currency"] = base_currency
                            item["updated_at"] = updated_at
                    content["screens"] = screens
                for sid in updated_screens: notify_screen(sid)
                # El panel escucha en sse_clients["admin"], y "admin" nunca está en
                # updated_screens porque está excluido del registro de pantallas. Sin
                # esta línea el panel no se entera de las tasas nuevas y, al guardar
                # cualquier cosa, sube su copia caducada encima.
                notify_screen("admin")
                ok({"updated_screens": updated_screens, "rows_count": len(rows)})
            except Exception as e: err(e)
            return

        # ── Mandar archivos de la Librería a varias pantallas
        if path == "/api/send-to-screens":
            try:
                try:
                    d = json.loads(body)
                except Exception:
                    d = None
                ids = d.get("ids") if isinstance(d, dict) else None
                pantallas = d.get("screens") if isinstance(d, dict) else None
                listas_ok = (isinstance(ids, list) and isinstance(pantallas, list)
                             and 0 < len(ids) <= 200 and 0 < len(pantallas) <= 100
                             and all(isinstance(x, str) and x for x in ids + pantallas))
                if not listas_ok:
                    jresp(400, {"ok": False, "error": "Elige al menos un archivo y una pantalla"}); return
                dur = d.get("duration", 8)
                if (isinstance(dur, bool) or not isinstance(dur, (int, float))
                        or not (1 <= dur <= 3600)):
                    jresp(400, {"ok": False, "error": "Duración no válida (1 a 3600 s)"}); return
                ids = list(dict.fromkeys(ids)); pantallas = list(dict.fromkeys(pantallas))
                registro = load_json(SCREENS_FILE)
                if not isinstance(registro, dict): registro = {}
                añadidos = saltados = 0
                try:
                    with contenido_en_edicion() as content:
                        por_id = {i.get("id"): i for i in content.get("items", [])}
                        for iid in ids:
                            if iid not in por_id:
                                raise DestinoNoExiste(f"No existe el archivo {iid}")
                        scr_all = content.setdefault("screens", {})
                        # Vale una pantalla del registro o una creada a mano (solo en content).
                        for sid in pantallas:
                            if sid not in registro and sid not in scr_all:
                                raise DestinoNoExiste(f"No existe la pantalla {sid}")
                        # Un videowall es UNA pantalla a efectos de contenido: lo que se manda a
                        # cualquiera de las del muro va a la que manda (la primera).
                        def _destino(sid):
                            s0 = scr_all.get(sid)
                            if isinstance(s0, dict) and s0.get("mode") == "wall":
                                ids_m, pos_m = wall_de(s0, sid)
                                if pos_m > 0 and ids_m[0] in scr_all:
                                    return ids_m[0]
                            return sid
                        for sid in list(dict.fromkeys(_destino(x) for x in pantallas)):
                            scr = scr_all.get(sid)
                            if not isinstance(scr, dict):
                                scr = scr_all[sid] = {"mode": "independent", "playlist": []}
                            pl = scr.setdefault("playlist", [])
                            for iid in ids:
                                if any(p.get("id") == iid for p in pl):
                                    saltados += 1
                                else:
                                    pl.append({**por_id[iid], "duration": dur}); añadidos += 1
                        if añadidos == 0:
                            # Nada nuevo: se sale por excepción para no guardar
                            # ni subir 'rev' (los demás paneles no se enterarían
                            # y su siguiente cambio rebotaría con 409).
                            raise NadaQueAnadir()
                except DestinoNoExiste as e:
                    jresp(404, {"ok": False, "error": str(e)}); return
                except NadaQueAnadir:
                    pass
                if añadidos > 0: notify_all()
                jresp(200, {"ok": True, "added": añadidos, "skipped": saltados})
            except Exception as e: err(e)
            return

        # ── Carpetas y etiquetas de la Librería (varios archivos a la vez)
        if path == "/api/organize":
            try:
                try:
                    d = json.loads(body)
                except Exception:
                    d = None
                malo = lambda m: jresp(400, {"ok": False, "error": m})
                ids = d.get("ids") if isinstance(d, dict) else None
                if not (isinstance(ids, list) and 0 < len(ids) <= 200
                        and all(isinstance(x, str) and x for x in ids)):
                    malo("Petición no válida"); return
                hay_carpeta = "folder" in d
                carpeta = d.get("folder")
                alta, baja = d.get("addTags"), d.get("removeTags")
                for lst in (alta, baja):
                    if lst is not None and not (isinstance(lst, list) and len(lst) <= 100
                                                and all(isinstance(x, str) for x in lst)):
                        malo("Petición no válida"); return
                if hay_carpeta and carpeta is not None and not isinstance(carpeta, str):
                    malo("Petición no válida"); return
                if not (hay_carpeta or alta or baja):
                    malo("Petición no válida"); return
                if isinstance(carpeta, str):
                    carpeta = carpeta.strip()
                    if not 1 <= len(carpeta) <= 40:
                        malo("Carpeta no válida (1 a 40 caracteres)"); return
                alta = [t.strip() for t in (alta or [])]
                if any(not 1 <= len(t) <= 30 for t in alta):
                    malo("Etiqueta no válida (1 a 30 caracteres)"); return
                # Sin repetidas: manda la primera aparición y se conserva el orden.
                vistas = set(); sin_rep = []
                for t in alta:
                    k = _clave_nombre(t)
                    if k not in vistas: vistas.add(k); sin_rep.append(t)
                alta = sin_rep
                if len(alta) > 10:
                    malo("Máximo 10 etiquetas por archivo"); return
                quitar = {_clave_nombre(t) for t in (baja or [])}
                ids = list(dict.fromkeys(ids))
                cambiados = 0
                try:
                    with contenido_en_edicion() as content:
                        items = content.get("items", [])
                        por_id = {i.get("id"): i for i in items}
                        for iid in ids:
                            if iid not in por_id:
                                raise DestinoNoExiste(f"No existe el archivo {iid}")
                        # Grafías ya en uso: la primera que aparece manda.
                        carpetas, etiquetas = {}, {}
                        for it in items:
                            if isinstance(it.get("folder"), str):
                                carpetas.setdefault(_clave_nombre(it["folder"]), it["folder"])
                            for t in _lista_tags(it):
                                if isinstance(t, str):
                                    etiquetas.setdefault(_clave_nombre(t), t)
                        if isinstance(carpeta, str):
                            carpeta = carpetas.get(_clave_nombre(carpeta), carpeta)
                        alta = [etiquetas.get(_clave_nombre(t), t) for t in alta]
                        for iid in ids:
                            it = por_id[iid]
                            previas = _lista_tags(it)
                            antes = (it.get("folder"), list(previas))
                            if hay_carpeta:
                                if carpeta is None: it.pop("folder", None)
                                else: it["folder"] = carpeta
                            tags = [t for t in previas
                                    if isinstance(t, str) and _clave_nombre(t) not in quitar]
                            claves = {_clave_nombre(t) for t in tags}
                            for t in alta:
                                if _clave_nombre(t) not in claves:
                                    tags.append(t); claves.add(_clave_nombre(t))
                            # Solo se rechaza si pasa de 10 Y crece: quitar etiquetas o
                            # tocar la carpeta de uno que ya tenía de más debe poder.
                            if len(tags) > 10 and len(tags) > len(previas):
                                raise EtiquetasDeMas()
                            if tags: it["tags"] = tags
                            else: it.pop("tags", None)
                            if (it.get("folder"), _lista_tags(it)) != antes:
                                cambiados += 1
                        if cambiados == 0:
                            # Nada cambió: se sale por excepción para no guardar
                            # ni subir 'rev'.
                            raise NadaQueAnadir()
                except DestinoNoExiste as e:
                    jresp(404, {"ok": False, "error": str(e)}); return
                except EtiquetasDeMas:
                    malo("Máximo 10 etiquetas por archivo"); return
                except NadaQueAnadir:
                    pass
                if cambiados > 0: notify_all()
                jresp(200, {"ok": True, "changed": cambiados})
            except Exception as e: err(e)
            return

        # ── Renombrar un contenido (solo el nombre que se ve)
        if path == "/api/rename":
            try:
                try:
                    d = json.loads(body)
                except Exception:
                    d = None
                if not isinstance(d, dict) or not isinstance(d.get("id"), str) or not d.get("id"):
                    jresp(400, {"ok": False, "error": "Petición no válida"}); return
                item_id = d["id"]
                nombre = d.get("name")
                nombre = nombre.strip() if isinstance(nombre, str) else ""
                if not nombre or len(nombre) > 120:
                    jresp(400, {"ok": False, "error": "Nombre no válido (1 a 120 caracteres)"}); return
                try:
                    with contenido_en_edicion() as content:
                        for it in content.get("items", []):
                            if it.get("id") == item_id:
                                it["name"] = nombre; break
                        else:
                            raise ArchivoNoExiste()
                except ArchivoNoExiste:
                    jresp(404, {"ok": False, "error": "No existe ese archivo"}); return
                notify_all()
                ok()
            except Exception as e: err(e)
            return

        # ── Eliminar item de librería
        if path == "/api/delete":
            try:
                d = json.loads(body)
                # Uno ("id") o varios ("ids"): una selección entera se borra en una
                # sola operación, con una sola pasada por el contenido.
                if isinstance(d.get("ids"), list):
                    ids = {str(x) for x in d["ids"]}
                else:
                    ids = {str(d["id"])}
                with contenido_en_edicion() as content:
                    for item in [i for i in content.get("items",[]) if i["id"] in ids]:
                        # Sólo los archivos subidos tienen 'src'; los módulos (fx, weather, qr...) no
                        # Los archivos viven en UPLOAD_DIR (DATA_DIR), no en el cwd.
                        if item.get("src"):
                            fp = os.path.join(UPLOAD_DIR, os.path.basename(str(item["id"])))
                            if os.path.realpath(fp).startswith(os.path.realpath(UPLOAD_DIR) + os.sep):
                                try: os.remove(fp)
                                except OSError: pass
                    content["items"] = [i for i in content.get("items",[]) if i["id"] not in ids]
                    # Eliminar de todas las playlists de pantallas
                    for sid, scr in content.get("screens",{}).items():
                        scr["playlist"] = [p for p in scr.get("playlist",[]) if p.get("id") not in ids]
                    # Y de los paquetes: un paquete con un id que ya no existe
                    # se reproduciría saltándose huecos.
                    for pkg in content.get("packages", []):
                        pkg["itemIds"] = [i for i in pkg.get("itemIds", []) if i not in ids]
                        if isinstance(pkg.get("items"), list):
                            pkg["items"] = [x for x in pkg["items"]
                                            if not (isinstance(x, dict) and x.get("id") in ids)]
                notify_all()
                ok()
            except Exception as e: err(e)
            return

        # ── Guardar configuración
        if path == "/api/config":
            try:
                d = json.loads(body)
                if not isinstance(d, dict):
                    # Sin esto, mandar una lista escribia una lista en
                    # config.json y se llevaba por delante la configuracion
                    # entera: puerto, nombre mDNS, todo.
                    jresp(400, {"ok": False, "error": "Configuración no válida"}); return
                # Fusionar, NO reemplazar. El formulario de Ajustes solo conoce
                # cinco claves; si se guardara el cuerpo tal cual, todo lo demás
                # —mdns_name, update_url, el token de avisos— desaparecería en
                # silencio la primera vez que alguien pulsa Guardar.
                actual = load_json(CONFIG_FILE)
                actual.update(d)
                save_json(CONFIG_FILE, actual)
                extra = {}
                if "autostart" in d:
                    # Tocar la tarea de Windows es lo que de verdad enciende o
                    # apaga el arranque; guardarlo en config.json de arriba es
                    # solo un rastro. Si esto falla (falta ser administrador,
                    # normalmente) el resto de Ajustes se guardó igual: no se
                    # aborta el guardado completo por esto.
                    autostart_ok, autostart_msg = _fijar_autoarranque(bool(d["autostart"]))
                    extra["autostart_ok"] = autostart_ok
                    if not autostart_ok:
                        extra["autostart_msg"] = autostart_msg
                ok(extra)
            except Exception as e: err(e)
            return

        # ── TV LG: «ya renové el modo desarrollador» / quitar el televisor de la lista
        if path in ("/api/lg-tvs/renovado", "/api/lg-tvs/borrar", "/api/lg-tvs/vigilar"):
            try:
                d = json.loads(body or "{}")
                tv_id = str(d.get("id", "")).strip() if isinstance(d, dict) else ""
                if not tv_id:
                    jresp(400, {"ok": False, "error": "Falta el televisor"}); return
                accion = path.rsplit("/", 1)[1]
                if accion == "vigilar" and not isinstance(d.get("activo"), bool):
                    jresp(400, {"ok": False, "error": "Falta si se activa o se apaga"}); return
                if not lg_tv_cambiar(tv_id, accion, activo=d.get("activo")):
                    jresp(404, {"ok": False, "error": "No existe ese televisor"}); return
                ok()
            except Exception as e: err(e)
            return

        # ── Instalar la mini-app en un televisor LG (lo lanza el panel)
        if path == "/api/lg-instalar":
            try:
                d = json.loads(body or "{}")
                if not isinstance(d, dict): d = {}
                ok_, motivo = lg_instalar_iniciar(str(d.get("ip", "")).strip(), str(d.get("passphrase", "")).strip(),
                                                  str(d.get("servidor", "")).strip(), d.get("vigilar") is True)
                if not ok_:
                    jresp(409 if "en marcha" in motivo else 400, {"ok": False, "error": motivo}); return
                ok()
            except Exception as e: err(e)
            return

        # ── Acceso remoto: canjear el PIN de la cuenta e instalar la conexión
        if path == "/api/acceso-remoto/activar":
            try:
                d = json.loads(body or "{}")
                if not isinstance(d, dict): d = {}
                ok_, motivo = acceso_activar(str(d.get("pin", "")).strip(), PORT)
                if not ok_:
                    jresp(409 if "en marcha" in motivo else 400, {"ok": False, "error": motivo}); return
                ok()
            except Exception as e: err(e)
            return
        if path == "/api/acceso-remoto/desactivar":
            try:
                acceso_desactivar()
                ok()
            except Exception as e: err(e)
            return

        # ── Reiniciar el servidor (re-ejecuta el proceso; aplica cambios de puerto, etc.)
        if path == "/api/restart":
            ok()
            def _restart():
                time.sleep(0.7)
                # Aquí había una salida especial para cuando Electron gestionaba
                # el proceso y su watchdog lo relanzaba. Esa vía se abandonó: hoy
                # solo existe la tarea programada, que ya reinicia sola si el
                # proceso se cae.
                try:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                except Exception:
                    os._exit(0)
            threading.Thread(target=_restart, daemon=True).start()
            return

        # ── Instalar la versión nueva (solo admin: la puerta de control ya lo exige)
        if path == "/api/update-install":
            url_v = url_actualizaciones()
            if not url_v:
                jresp(400, {"ok": False, "error": "No hay dirección de actualizaciones configurada"}); return
            if not _update_lock.acquire(blocking=False):
                jresp(409, {"ok": False, "error": "Ya hay una actualización en marcha"}); return
            try:
                _update_cache["datos"] = None                  # siempre lo último publicado
                datos = comprobar_actualizacion(url_v)
                if datos.get("error"):
                    jresp(502, {"ok": False, "error": datos["error"]}); return
                if not datos.get("update_available"):
                    jresp(409, {"ok": False, "error": "Ya tienes la última versión"}); return
                try:
                    ruta = preparar_instalador(datos)
                except ValueError as e:
                    log(f"  [actualizar] rechazada: {e}")
                    jresp(502, {"ok": False, "error": str(e)}); return
                ok({"version": datos["latest"]})               # primero se responde...
                lanzar_instalador(ruta)                        # ...y luego el instalador para el servidor
            except Exception as e:
                log(f"  [actualizar] error: {e}")
            finally:
                _update_lock.release()
            return

        # ── Pedir un PIN nuevo (solo admin: la puerta de control ya lo exige)
        if path == "/api/pin/regenerate":
            generate_pin()
            ok({"pin": pin_state["pin"], "expires_in": 600}); return

        # ── Emparejar pantalla con PIN
        if path == "/api/pair":
            try:
                d = json.loads(body)
                pin_input = d.get("pin", "")
                screen_name = d.get("screen_name", "").strip()

                if not screen_name:
                    err("screen_name requerido")
                    return

                # Validar PIN
                valid, msg = validate_pin(pin_input)
                if not valid:
                    self.send_response(400); self.cors(); self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": msg}).encode())
                    return

                # Registrar pantalla
                screens = load_json(SCREENS_FILE)
                screens[screen_name] = {"id": screen_name, "connected": True, "last_seen": time.time()}
                save_json(SCREENS_FILE, screens)

                # Crear config inicial para la pantalla
                with contenido_en_edicion() as content:
                    if not content.get("screens"):
                        content["screens"] = {}
                    if screen_name not in content["screens"]:
                        content["screens"][screen_name] = {
                            "mode": "independent",
                            "playlist": [],
                            "vertical": False,
                            "schedule": {}
                        }

                # Notificar a todas las conexiones SSE
                notify_all()

                # Devolver respuesta exitosa
                player_url = url_for(f"/player.html?screen={screen_name}", host=get_ip())
                ok({"screen_name": screen_name, "player_url": player_url})
            except Exception as e: err(e)
            return

        self.send_response(404); self.end_headers()

if __name__ == "__main__":
    ip = get_ip()
    # Reutilizar el PIN persistido si sigue vigente; sólo generar uno nuevo si falta o expiró
    get_active_pin()

    # ThreadingHTTPServer: cada conexión en su propio hilo. Imprescindible porque
    # las conexiones SSE (/api/events) son de vida infinita y con un server
    # single-threaded bloquearían TODAS las demás peticiones (PIN, pair, etc.).
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    # Anunciar el nombre mDNS (http://signage.local) en la red local
    start_mdns_responder()
    log("\n" + "="*56)
    log("  INTEKS DISPLAY — SERVIDOR DIGITAL SIGNAGE")
    log("="*56)
    log(f"  Admin:           {url_for('/admin.html', host='localhost')}")
    log(f"  Enlazar (nombre): {url_for('/pair')}")
    log(f"  Enlazar (IP):     {url_for('/pair', host=ip)}")
    log(f"  Player tablet 1:  {url_for('/player.html?screen=pantalla1', host=ip)}")
    log("="*56)
    log(f"  PIN de enlace:   {pin_state['pin']} (válido 10 min)")
    log("="*56)
    # Vigilante de avisos y bot de /estado. Solo cuando el programa se
    # ejecuta de verdad: si arrancaran al importar server.py, los tests que
    # lo importan tendrian un hilo suelto mandando mensajes por su cuenta.
    threading.Thread(target=_vigilante, daemon=True).start()
    threading.Thread(target=_bot_loop, daemon=True).start()

    _disco = estado_disco()
    if _disco.get("aviso"):
        log(f"  AVISO: disco al {_disco['pct_usado']}% "
            f"({_disco['libre_mb']} MB libres). Si se llena, fallaran las "
            f"subidas y puede corromperse la configuracion.")
        log("="*56)
    log("  Ctrl+C para detener\n")
    try: srv.serve_forever()
    except KeyboardInterrupt: log("\nDetenido.")
