"""
El nombre para mostrar de una pantalla (cfg.label) sobrevive a guardar y recargar.

El panel lo guarda con /api/screens/config dentro de content.screens[id]; si el
servidor descartara campos desconocidos, «Renombrar» se perderia al recargar.

Ejecutar:  python tests/test_pantalla_nombre.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8133
TOKEN = "tok-prueba-nombre"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_nom_")
    datos = tempfile.mkdtemp(prefix="signalos_nomd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def pedir(ruta, payload=None):
        r = urllib.request.Request(
            base + ruta, data=None if payload is None else json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN},
            method="GET" if payload is None else "POST")
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, json.load(resp)

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1); break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco"); return 1
        _, c = pedir("/api/content")
        c["screens"] = {"TV": {"mode": "independent", "playlist": [], "label": "Entrada"}}
        st, _ = pedir("/api/screens/config", {"rev": c.get("rev", 0), "screens": c["screens"]})
        _, c2 = pedir("/api/content")
        check(st == 200 and c2["screens"]["TV"].get("label") == "Entrada", "el nombre para mostrar se guarda y se recarga")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
