#!/usr/bin/env python3
"""
InTeks Display — Servidor Digital Signage
Ejecutar: python server.py [--port PUERTO]
Admin:    http://localhost/admin.html   (puerto 80 por defecto)
Player:   http://TU_IP/player.html?screen=NOMBRE
Enlazar:  http://signage.local/pair     (nombre mDNS, configurable en config.json)
"""
import json, os, base64, mimetypes, threading, time, socket, sys, random, struct
import hmac, hashlib, secrets, shutil, io, zipfile, contextlib, subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request

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
APP_VERSION = "1.0.34"

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
            code = f"{random.randint(0, 9999):04d}"
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
    except:
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
    pin_state["pin"] = str(random.randint(100000, 999999))
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

def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()

def set_admin_password(password):
    """Crea/actualiza la contraseña del admin y garantiza secret + api_token."""
    a = _load_admin()
    salt = a.get("salt") or secrets.token_hex(16)
    a["salt"] = salt
    a["pwd_hash"] = _hash_password(password, salt)
    if not a.get("secret"):    a["secret"] = secrets.token_hex(32)
    if not a.get("api_token"): a["api_token"] = secrets.token_hex(24)
    save_json(ADMIN_FILE, a)
    return a

def verify_admin_password(password):
    a = _load_admin()
    if not a.get("pwd_hash") or not a.get("salt"): return False
    return hmac.compare_digest(_hash_password(password, a["salt"]), a["pwd_hash"])

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
        except:
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
            except: dead.append(wfile)
        if dead:
            sse_clients[screen_id] = [c for c in sse_clients.get(screen_id,[]) if c not in dead]

def notify_all():
    with sse_lock:
        all_ids = list(sse_clients.keys())
    for sid in all_ids: notify_screen(sid)

def notify_deleted(screen_id):
    """Avisa a la pantalla (vía SSE) de que fue eliminada para que se desconecte."""
    with sse_lock:
        for wfile in list(sse_clients.get(screen_id, [])):
            try:
                wfile.write(f"data: deleted:{screen_id}\n\n".encode())
                wfile.flush()
            except: pass

# ── Aviso de version nueva ─────────────────────────────────────────────────
# Esto NO instala nada solo. En una pantalla de escaparate, actualizarse sin
# permiso es la peor idea posible: el momento lo eliges tú, no el programa.
# Solo avisa en el panel.
#
# Viene apagado: `update_url` vacía en config.json. Mientras no se rellene, el
# servidor no habla con nadie de fuera.
_update_cache = {"cuando": 0, "datos": None}
UPDATE_TTL = 3600                  # no molestar al servidor de versiones cada rato

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
        })
    except Exception as e:
        base["error"] = f"No se pudo consultar: {e}"
    _update_cache.update({"cuando": ahora, "datos": base})
    return base

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
                    completa = os.path.join(raiz, f)
                    rel = os.path.relpath(completa, UPLOAD_DIR).replace("\\", "/")
                    z.write(completa, f"uploads/{rel}")
    return buf.getvalue()

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
            except: pass
    return entregados

def load_json(path):
    with file_lock:
        try:
            with open(path, encoding="utf-8") as f: return json.load(f)
        except: return {}

def save_json(path, data):
    # Escritura atómica + lock: evita corrupción si dos peticiones escriben a la vez
    with file_lock:
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
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
    except: return "127.0.0.1"

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
            if "regenerate" in qs:
                generate_pin()
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
            except:
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
            url = str(load_config().get("update_url", "") or "").strip()
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

        # ── API: pantallas encendidas esperando a que se les ponga nombre
        if path == "/api/pair-pending":
            if not self.require_auth(): return
            body = json.dumps({"pending": pending_list()}).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.cors(); self.end_headers(); self.wfile.write(body); return

        # ── API: obtener pantallas registradas  (solo admin / extensión con token)
        if path == "/api/screens":
            if not self.require_auth(): return
            body = json.dumps(load_json(SCREENS_FILE)).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
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
            resuelta = filtrar_vigentes(
                expandir_paquetes(scr.get("playlist", []), content),
                time.strftime("%Y-%m-%d"))
            if mode == "wall":
                partner = scr.get("partner","")
                wall_pos = scr.get("wall_pos","left")
                playlist = [dict(item, wall_mode=True, wall_pos=wall_pos) for item in resuelta]
            else:
                playlist = resuelta
            # La versión viaja aquí para que la pantalla note que el servidor se
            # ha actualizado y recargue: el archivo del disco cambia al
            # instalar, pero la página que el televisor lleva horas abierta
            # sigue ejecutando el código viejo. Ver debeRecargarPorVersion() en
            # player.html.
            result = {"playlist": playlist, "mode": mode, "screen_id": sid,
                      "config": scr, "version": APP_VERSION}
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
                except: pass
                return
            # Desenlace pendiente: se pidio soltar el aparato mientras estaba
            # apagado, asi que el aviso no llego a nadie y quedo apuntado. Es la
            # primera oportunidad de darselo. Se borra la marca al entregarla: si
            # no, un aparato reenlazado a este mismo nombre se desenlazaria solo
            # una y otra vez.
            if sid != "admin" and screens.get(sid, {}).get("unlink_pending"):
                try:
                    self.wfile.write(f"data: unlink:{sid}\n\n".encode()); self.wfile.flush()
                except: pass
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
            except:
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

    def do_POST(self):
        parsed = urlparse(self.path)
        path = ruta_decodificada(parsed.path)
        length = int(self.headers.get("Content-Length",0))
        # Techo de seguridad: el cuerpo se carga ENTERO en memoria, así que un
        # envío gigante (una restauración con vídeos, una subida equivocada)
        # tumbaría el servidor de la tienda. Se rechaza antes de leerlo.
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
                if verify_admin_password(d.get("password", "")):
                    self.send_response(200); self.send_header("Content-Type","application/json")
                    self._set_session_cookie(make_session_token()); self.cors(); self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode())
                else:
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
                if len(new) < 6:
                    jresp(400, {"ok": False, "error": "La contraseña debe tener al menos 6 caracteres"}); return
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
                name = d["name"]
                idx = len(os.listdir(UPLOAD_DIR))
                filename = f"{idx:04d}_{name}"
                with open(os.path.join(UPLOAD_DIR, filename),"wb") as f: f.write(raw)
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

        # ── Eliminar item de librería
        if path == "/api/delete":
            try:
                d = json.loads(body)
                item_id = d["id"]
                with contenido_en_edicion() as content:
                    item = next((i for i in content.get("items",[]) if i["id"]==item_id), None)
                    if item:
                        # Sólo los archivos subidos tienen 'src'; los módulos (fx, weather, qr...) no
                        fp = item.get("src", "").lstrip("/")
                        if fp and os.path.exists(fp): os.remove(fp)
                    content["items"] = [i for i in content.get("items",[]) if i["id"]!=item_id]
                    # Eliminar de todas las playlists de pantallas
                    for sid, scr in content.get("screens",{}).items():
                        scr["playlist"] = [p for p in scr.get("playlist",[]) if p.get("id")!=item_id]
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
