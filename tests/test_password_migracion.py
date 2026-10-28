"""
Contraseña del admin: más iteraciones sin dejar a nadie fuera.

Una instalación vieja tiene admin.json sin el campo "iter" (hash con 100.000
iteraciones). Tiene que seguir entrando, y al entrar el hash se rehace con las
nuevas. Una contraseña nueva ya nace con ellas y exige 8 caracteres.

Ejecutar:
    python tests/test_password_migracion.py
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8112
TOKEN = "token-de-pruebas-0123456789"
CLAVE = "clave-de-siempre"
SAL = "11" * 16
BASE = f"http://127.0.0.1:{PORT}"


def post(path, payload, token=None):
    cab = {"Content-Type": "application/json"}
    if token: cab["X-SignalOS-Token"] = token
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers=cab, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    work = tempfile.mkdtemp(prefix="signalos_pwd_")
    proc = None
    fallos = 0
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        ruta = os.path.join(work, "admin.json")
        viejo = hashlib.pbkdf2_hmac("sha256", CLAVE.encode(), bytes.fromhex(SAL), 100000).hex()
        json.dump({"api_token": TOKEN, "secret": "s" * 64, "salt": SAL, "pwd_hash": viejo}, open(ruta, "w"))
        json.dump({"items": [], "screens": {}, "rev": 0}, open(os.path.join(work, "content.json"), "w"))
        proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                                cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(BASE + "/api/auth-status", timeout=1); break
            except Exception:
                pass

        fallos += comprobar("contraseña mala -> 401", post("/api/login", {"password": "otra-cosa-mala"}) == 401)
        a = json.load(open(ruta))
        fallos += comprobar("una mala no toca el hash", a["pwd_hash"] == viejo and "iter" not in a)

        fallos += comprobar("la de siempre entra (hash antiguo)", post("/api/login", {"password": CLAVE}) == 200)
        a = json.load(open(ruta))
        fallos += comprobar("al entrar se rehace con 600.000", a.get("iter") == 600000 and a["pwd_hash"] != viejo,
                            str(a.get("iter")))
        fallos += comprobar("y sigue entrando con el hash nuevo", post("/api/login", {"password": CLAVE}) == 200)

        fallos += comprobar("7 caracteres -> 400", post("/api/set-password", {"password": "1234567"}, TOKEN) == 400)
        fallos += comprobar("8 caracteres -> 200", post("/api/set-password", {"password": "12345678"}, TOKEN) == 200)
        a = json.load(open(ruta))
        fallos += comprobar("la nueva nace con 600.000 y otra sal", a.get("iter") == 600000 and a["salt"] != SAL)
        fallos += comprobar("la nueva entra", post("/api/login", {"password": "12345678"}) == 200)
        fallos += comprobar("la vieja ya no", post("/api/login", {"password": CLAVE}) == 401)
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_password_migracion" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
