"""
Botón «Actualizar» del panel: baja el instalador anunciado, comprueba su huella
y lo lanza. Nunca instala algo que no cuadre.

El servidor corre en un directorio temporal con SIGNALOS_UPDATE_DRYRUN=1: hace
todo menos ejecutar el instalador, y en su lugar escribe actualizacion/lanzaria.txt
con la orden que habría ejecutado. Un servidor falso hace de «GitHub».

Ejecutar:
    python tests/test_update_install.py
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, threading, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT, FAKE = 8113, 8114
TOKEN = "token-de-pruebas-0123456789"
BASE = f"http://127.0.0.1:{PORT}"

INSTALADOR = b"MZ" + os.urandom(2048)
HUELLA = hashlib.sha256(INSTALADOR).hexdigest()
manifiesto = {}          # lo que sirve el servidor falso (se cambia en cada caso)


class Falso(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == "/version.json":
            cuerpo = json.dumps(manifiesto).encode()
        elif self.path == "/setup.exe":
            cuerpo = INSTALADOR
        elif self.path == "/roto.exe":
            cuerpo = b"esto no es un exe"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers(); self.wfile.write(cuerpo)


def post(path, payload=None, token=TOKEN):
    cab = {"Content-Type": "application/json"}
    if token: cab["X-SignalOS-Token"] = token
    req = urllib.request.Request(BASE + path, data=json.dumps(payload or {}).encode(), headers=cab, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or "{}")
        except ValueError: return e.code, {}


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    global manifiesto
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_upd_")
    proc = None
    srv = HTTPServer(("127.0.0.1", FAKE), Falso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    marca = os.path.join(work, "actualizacion", "lanzaria.txt")
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        cfg = json.load(open(os.path.join(work, "config.json")))
        cfg["update_url"] = f"http://127.0.0.1:{FAKE}/version.json"
        json.dump(cfg, open(os.path.join(work, "config.json"), "w"))
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        entorno = dict(os.environ, SIGNALOS_UPDATE_DRYRUN="1")
        proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=work, env=entorno,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(BASE + "/api/auth-status", timeout=1); break
            except Exception: pass

        def nuevo(**cambios):
            global manifiesto
            manifiesto = {"version": "99.0.0", "installer_url": f"http://127.0.0.1:{FAKE}/setup.exe",
                          "sha256": HUELLA, "notes": "x"}
            manifiesto.update(cambios)
            if os.path.exists(marca): os.remove(marca)

        print("1. sin sesion")
        nuevo()
        cod, _ = post("/api/update-install", token=None)
        fallos += comprobar("sin sesion -> 401", cod == 401, str(cod))

        print("2. huella distinta")
        nuevo(sha256="0" * 64)
        cod, r = post("/api/update-install")
        fallos += comprobar("502 y no se lanza", cod == 502 and not os.path.exists(marca), f"{cod} {r}")
        fallos += comprobar("no se queda el archivo", not [f for f in os.listdir(os.path.join(work, "actualizacion")) if f.endswith(".exe")])

        print("3. sin huella / sin direccion segura / no es un exe")
        nuevo(sha256="")
        fallos += comprobar("sin sha256 -> 502", post("/api/update-install")[0] == 502)
        nuevo(installer_url="http://ejemplo.com/setup.exe")
        fallos += comprobar("http fuera de esta maquina -> 502", post("/api/update-install")[0] == 502)
        nuevo(installer_url=f"http://127.0.0.1:{FAKE}/roto.exe", sha256=hashlib.sha256(b"esto no es un exe").hexdigest())
        fallos += comprobar("huella buena pero no es un programa -> 502", post("/api/update-install")[0] == 502
                            and not os.path.exists(marca))
        nuevo(version="99.0.0; calc")
        fallos += comprobar("version con caracteres raros -> 502", post("/api/update-install")[0] == 502)

        print("4. ya al dia")
        nuevo(version="0.0.1")
        cod, _ = post("/api/update-install")
        fallos += comprobar("version vieja -> 409", cod == 409 and not os.path.exists(marca), str(cod))

        print("5. todo bien")
        nuevo()
        cod, r = post("/api/update-install", {"installer_url": "https://evil.example/mal.exe"})
        fallos += comprobar("200 con la version", cod == 200 and r.get("version") == "99.0.0", f"{cod} {r}")
        orden = open(marca).read() if os.path.exists(marca) else ""
        fallos += comprobar("lanza el instalador descargado en silencio",
                            "InTeks_Display_Setup_99.0.0.exe" in orden and "/VERYSILENT" in orden, orden)
        fallos += comprobar("ignora la direccion que mande el navegador", "evil" not in orden)
        descargado = os.path.join(work, "actualizacion", "InTeks_Display_Setup_99.0.0.exe")
        fallos += comprobar("lo descargado es identico", os.path.exists(descargado)
                            and hashlib.sha256(open(descargado, "rb").read()).hexdigest() == HUELLA)
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        srv.shutdown()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_update_install" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
