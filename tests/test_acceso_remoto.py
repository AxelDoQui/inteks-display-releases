"""
Acceso remoto: el panel canjea un PIN de la cuenta (aquí un Worker de mentira) y con el token
que devuelve instala cloudflared como servicio (aquí un cloudflared de mentira que apunta sus
argumentos). El token no debe verse nunca en lo que cuenta la API ni en lo que se guarda.
También: el límite de intentos de login usa la IP real (CF-Connecting-IP) tras el túnel.

Ejecutar:  python tests/test_acceso_remoto.py
"""
import json, os, shutil, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT, PORT_CUENTA = 8138, 8139
TOKEN_API = "tok-prueba-acceso"
TOKEN_TUNEL = "TOKENFALSO" + "abcdefghij0123456789" * 3
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
recibidos = []
fallos = 0


class Cuenta(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        recibidos.append(d)
        pin = d.get("pin")
        if pin == "333333": time.sleep(2)
        if pin in ("123456", "333333"):
            cuerpo, code = {"ok": True, "token": TOKEN_TUNEL, "hostname": "tienda1.inteksdisplay.com"}, 200
        elif pin == "222222":
            cuerpo, code = {"ok": True, "token": "raro; calc & más", "hostname": "tienda1.inteksdisplay.com"}, 200
        else:
            cuerpo, code = {"ok": False, "error": "PIN no válido o caducado"}, 400
        b = json.dumps(cuerpo).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    if sys.platform != "win32":
        print("TODO OK (solo Windows)"); return 0
    cuenta = HTTPServer(("127.0.0.1", PORT_CUENTA), Cuenta)
    threading.Thread(target=cuenta.serve_forever, daemon=True).start()

    app = tempfile.mkdtemp(prefix="signalos_acc_")
    datos = tempfile.mkdtemp(prefix="signalos_accd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    falso = os.path.join(app, "falso-cloudflared.cmd")
    registro = os.path.join(app, "llamadas.txt")
    open(falso, "w").write('@echo off\r\necho %* >> "%~dp0llamadas.txt"\r\nexit /b 0\r\n')
    json.dump({"api_token": TOKEN_API, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    json.dump({"rev": 1, "screens": {}}, open(os.path.join(datos, "content.json"), "w"))
    env = dict(os.environ, SIGNALOS_DATA=datos, SIGNALOS_CLOUDFLARED=falso,
               SIGNALOS_CUENTA_URL=f"http://127.0.0.1:{PORT_CUENTA}")
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
    token = {"v": TOKEN_API}

    def pedir(ruta, payload=None, con_token=True, extra=None):
        cab = {"Content-Type": "application/json", **(extra or {})}
        if con_token: cab["X-SignalOS-Token"] = token["v"]
        r = urllib.request.Request(base + ruta, data=None if payload is None else json.dumps(payload).encode(),
                                   headers=cab, method="GET" if payload is None else "POST")
        try:
            with urllib.request.urlopen(r, timeout=8) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def esperar_fin(segundos=20):
        t0 = time.time()
        while time.time() - t0 < segundos:
            d = pedir("/api/acceso-remoto")[1]
            if d.get("estado") != "activando":
                return d
            time.sleep(0.3)
        return d

    def llamadas():
        try: return open(registro, encoding="utf-8", errors="replace").read()
        except OSError: return ""

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1); break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco"); return 1

        check(pedir("/api/acceso-remoto", con_token=False)[0] == 401, "el estado exige sesión")
        check(pedir("/api/acceso-remoto/activar", {"pin": "123456"}, con_token=False)[0] == 401, "activar exige sesión")
        st, d = pedir("/api/acceso-remoto")
        check(st == 200 and d.get("disponible") is True and d.get("estado") == "libre" and d.get("activo") is False,
              "empieza libre, disponible y sin activar")
        check(d.get("password") is False, "avisa de que no hay contraseña de administrador")

        st, d = pedir("/api/acceso-remoto/activar", {"pin": "123456"})
        check(st == 400 and "contraseña" in d.get("error", ""), "sin contraseña de admin no activa")
        check(recibidos == [], "y no llegó a hablar con la cuenta")

        st, d = pedir("/api/set-password", {"password": "una-clave-larga-1"})
        token["v"] = d.get("api_token") or TOKEN_API

        for malo in ("12345", "1234567", "abcdef", "", "12 456"):
            st, d = pedir("/api/acceso-remoto/activar", {"pin": malo})
            check(st == 400 and d.get("ok") is False, f"rechaza el PIN «{malo}»")
        check(recibidos == [], "un PIN mal formado no sale a la red")

        pedir("/api/acceso-remoto/activar", {"pin": "999999"})
        fin = esperar_fin()
        check(fin.get("estado") == "error" and "PIN no válido" in fin.get("error", ""), "PIN que la cuenta rechaza - error con su motivo")
        check("service install" not in llamadas(), "y no instaló nada")

        st, d = pedir("/api/acceso-remoto/activar", {"pin": "222222"})
        fin = esperar_fin()
        check(fin.get("estado") == "error" and "service install" not in llamadas(), "token con signos raros: no se usa")

        st, d = pedir("/api/acceso-remoto/activar", {"pin": "123456"})
        check(st == 200 and d.get("ok") is True, "acepta un PIN bueno")
        fin = esperar_fin()
        check(fin.get("estado") == "ok" and fin.get("activo") is True and fin.get("hostname") == "tienda1.inteksdisplay.com",
              "termina bien y queda activo en su dirección")
        ll = llamadas()
        check("service uninstall" in ll and f"service install {TOKEN_TUNEL}" in ll, "reinstala el servicio con el token recibido")
        check(recibidos[-1] == {"pin": "123456", "puerto": PORT}, "manda a la cuenta el PIN y el puerto de este servidor")
        todo = json.dumps(fin) + open(os.path.join(datos, "acceso-remoto.json"), encoding="utf-8").read()
        check(TOKEN_TUNEL not in todo, "el token no sale en la API ni se guarda en el archivo")

        pedir("/api/acceso-remoto/activar", {"pin": "333333"})
        time.sleep(0.5)
        st, d = pedir("/api/acceso-remoto/activar", {"pin": "123456"})
        check(st == 409, "no deja lanzar dos a la vez")
        esperar_fin()

        st, d = pedir("/api/acceso-remoto/desactivar", {})
        d = pedir("/api/acceso-remoto")[1]
        check(st == 200 and d.get("activo") is False and d.get("estado") == "libre", "desactivar lo deja libre")
        check(llamadas().count("service uninstall") >= 2, "y quita el servicio")

        # Límite de login por IP real: una IP que falla no bloquea a otra.
        malo = lambda ip: pedir("/api/login", {"password": "no-es"}, con_token=False, extra={"CF-Connecting-IP": ip})[0]
        codigos = [malo("1.1.1.1") for _ in range(6)]
        check(codigos[-1] == 429, "6 fallos desde una IP real la bloquean")
        check(malo("2.2.2.2") == 401, "otra IP real no queda bloqueada por la primera")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        cuenta.shutdown()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
