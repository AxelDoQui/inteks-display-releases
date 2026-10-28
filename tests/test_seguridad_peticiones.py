"""
Puerta del servidor: lo que pasa ANTES de que se sepa quien llama.

Se arranca el servidor de verdad en un directorio temporal y se le habla con
sockets crudos, porque urllib no deja mandar un Content-Length mentiroso.

Fallos que cubre (los tests se escribieron antes del arreglo y se vieron fallar):
  1. Content-Length negativo o no numerico colgaba un hilo / lanzaba excepcion.
  2. El cuerpo se leia ENTERO antes de comprobar la sesion: un POST de 512 MB
     sin autenticar se cargaba en RAM.
  3. /api/login no limitaba intentos.
  4. El PIN y el codigo de pantalla salian de `random`, que no es criptografico.
  5. /api/upload usaba el nombre tal cual y reutilizaba numeros de archivo.

Ejecutar:
    python tests/test_seguridad_peticiones.py
"""
import base64, hashlib, json, os, re, shutil, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8110
TOKEN = "token-de-pruebas-0123456789"
CLAVE = "clave-correcta-123"
SAL = "00" * 16
BASE = f"http://127.0.0.1:{PORT}"


def arrancar():
    work = tempfile.mkdtemp(prefix="signalos_seg_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    hash_ = hashlib.pbkdf2_hmac("sha256", CLAVE.encode(), bytes.fromhex(SAL), 100000).hex()
    json.dump({"api_token": TOKEN, "secret": "s" * 64, "salt": SAL, "pwd_hash": hash_},
              open(os.path.join(work, "admin.json"), "w"))
    json.dump({"items": [], "screens": {}, "rev": 0}, open(os.path.join(work, "content.json"), "w"))
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(BASE + "/api/auth-status", timeout=1)
            return proc, work
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("el servidor no arranco")


def parar(proc, work):
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    shutil.rmtree(work, ignore_errors=True)


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def crudo(path, content_length, cuerpo=b"", extra="", espera=3.0):
    """POST con la cabecera Content-Length que se diga. Devuelve (codigo, segundos)
    o (None, segundos) si el servidor no contesto a tiempo."""
    t0 = time.time()
    s = socket.create_connection(("127.0.0.1", PORT), timeout=espera)
    try:
        s.sendall((f"POST {path} HTTP/1.0\r\nHost: x\r\nContent-Type: application/json\r\n"
                   f"Content-Length: {content_length}\r\n{extra}\r\n").encode() + cuerpo)
        datos = b""
        while b"\r\n" not in datos:
            trozo = s.recv(4096)
            if not trozo: break
            datos += trozo
        m = re.match(rb"HTTP/\S+ (\d+)", datos)
        return (int(m.group(1)) if m else 0), time.time() - t0
    except socket.timeout:
        return None, time.time() - t0
    finally:
        s.close()


def post_json(path, payload, token=TOKEN):
    cab = {"Content-Type": "application/json"}
    if token: cab["X-SignalOS-Token"] = token
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers=cab, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or "{}")
        except ValueError: return e.code, {}


def prueba_1_content_length_raro():
    fallos = 0
    for valor, etiqueta in (("-1", "negativo"), ("abc", "no numerico")):
        codigo, seg = crudo("/api/login", valor)
        fallos += comprobar(f"Content-Length {etiqueta} -> 400 sin colgarse",
                            codigo == 400, f"codigo={codigo} en {seg:.1f}s")
    # /api/logout y no /api/login: un login vacio gastaria un intento del limite
    codigo, _ = crudo("/api/logout", 2, b"{}")
    fallos += comprobar("el servidor sigue vivo despues", codigo == 200, str(codigo))
    return fallos


def prueba_2_no_lee_cuerpo_sin_sesion():
    """Dice que van 100 MB y no manda nada: si lo intenta leer, se cuelga."""
    fallos = 0
    codigo, seg = crudo("/api/content", 100 * 1024 * 1024, extra="")
    fallos += comprobar("ruta protegida sin sesion -> 401 sin esperar el cuerpo",
                        codigo == 401 and seg < 2, f"codigo={codigo} en {seg:.1f}s")
    codigo, seg = crudo("/api/login", 100 * 1024 * 1024)
    fallos += comprobar("ruta publica con cuerpo enorme -> 413 sin esperarlo",
                        codigo == 413 and seg < 2, f"codigo={codigo} en {seg:.1f}s")
    return fallos


def prueba_3_login_limitado():
    fallos = 0
    codigos = [post_json("/api/login", {"password": "mala"}, token=None)[0] for _ in range(5)]
    fallos += comprobar("5 intentos malos dan 401", codigos == [401] * 5, str(codigos))
    cod, cuerpo = post_json("/api/login", {"password": "mala"}, token=None)
    fallos += comprobar("el sexto intento se bloquea (429)", cod == 429, str(cod))
    cod, _ = post_json("/api/login", {"password": CLAVE}, token=None)
    fallos += comprobar("bloqueado, ni la clave buena entra", cod == 429, str(cod))
    return fallos


def prueba_4_aleatoriedad_segura():
    fuente = open(os.path.join(SRC, "server.py"), encoding="utf-8").read()
    return comprobar("server.py no usa random.randint para PIN ni codigos",
                     "random.randint" not in fuente)


def prueba_5_subidas():
    fallos = 0
    work = WORK
    datos = lambda t: base64.b64encode(t).decode()
    cod, r = post_json("/api/upload", {"name": "../../evil.png", "type": "image", "data": datos(b"1")})
    item = r.get("item", {})
    fallos += comprobar("nombre con ../ se limpia",
                        cod == 200 and "/" not in item.get("id", "/") and "\\" not in item.get("id", "\\")
                        and ".." not in item.get("id", ".."), str(item.get("id")))
    ids = [item.get("id")]
    for i in range(2, 4):
        _, r = post_json("/api/upload", {"name": "x.png", "type": "image", "data": datos(b"c%d" % i)})
        ids.append(r["item"]["id"])
    # Borrar el primer archivo del disco y subir otro: no debe pisar a ninguno
    os.remove(os.path.join(work, "uploads", ids[0]))
    _, r = post_json("/api/upload", {"name": "x.png", "type": "image", "data": datos(b"nuevo")})
    ids.append(r["item"]["id"])
    fallos += comprobar("los ids son distintos", len(set(ids)) == len(ids), str(ids))
    contenidos = [open(os.path.join(work, "uploads", i), "rb").read() for i in ids[1:]]
    fallos += comprobar("ninguna subida pisa a otra", contenidos == [b"c2", b"c3", b"nuevo"], str(contenidos))
    return fallos


def prueba_6_pin_no_cambia_con_get():
    fallos = 0
    def leer(url):
        req = urllib.request.Request(BASE + url, headers={"X-SignalOS-Token": TOKEN})
        return json.loads(urllib.request.urlopen(req, timeout=5).read())["pin"]
    p0 = leer("/api/pin")
    fallos += comprobar("GET con ?regenerate ya no cambia el PIN", leer("/api/pin?regenerate=1") == p0)
    cod, r = post_json("/api/pin/regenerate", {})
    fallos += comprobar("POST /api/pin/regenerate da uno nuevo", cod == 200 and r.get("pin") != p0, str(cod))
    cod, _ = post_json("/api/pin/regenerate", {}, token=None)
    fallos += comprobar("sin sesion -> 401", cod == 401, str(cod))
    return fallos


if __name__ == "__main__":
    proc, WORK = arrancar()
    fallos = 0
    try:
        for p in (prueba_1_content_length_raro, prueba_2_no_lee_cuerpo_sin_sesion,
                  prueba_5_subidas, prueba_6_pin_no_cambia_con_get, prueba_3_login_limitado):
            print(p.__name__)
            fallos += p()
        print("prueba_4_aleatoriedad_segura")
        fallos += prueba_4_aleatoriedad_segura()
    finally:
        parar(proc, WORK)
    print("OK test_seguridad_peticiones" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)
