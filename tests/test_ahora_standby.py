"""
Con la pantalla apagada o en una fecha de «solo esta imagen», el reproductor avisa de
que lo que se ve es el standby (con su imagen) y el panel lo enseña en la miniatura,
en vez de seguir diciendo que reproduce la playlist.

Ejecutar:  python tests/test_ahora_standby.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8137
TOKEN = "tok-prueba-standby"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    player = open(os.path.join(SRC, "player.html"), encoding="utf-8").read()
    admin = open(os.path.join(SRC, "admin.html"), encoding="utf-8").read()
    check('type:"standby"' in player and 'dataset.img' in player, "el player cuenta el standby")
    check('n.type==="standby"' in admin, "el panel dibuja la miniatura del standby")

    app = tempfile.mkdtemp(prefix="signalos_sb_")
    datos = tempfile.mkdtemp(prefix="signalos_sbd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    json.dump({"rev": 1, "screens": {"TV": {"mode": "independent", "playlist": []}}},
              open(os.path.join(datos, "content.json"), "w"))
    json.dump({"TV": {"id": "TV", "connected": True, "last_seen": time.time()}},
              open(os.path.join(datos, "screens.json"), "w"))
    env = dict(os.environ, SIGNALOS_DATA=datos)
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def pedir(ruta, payload=None):
        r = urllib.request.Request(base + ruta, data=None if payload is None else json.dumps(payload).encode(),
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
        st, d = pedir("/api/screen-now", {"screen": "TV", "id": "", "name": "Solo una imagen (fecha especial)",
                                          "type": "standby", "img": "/uploads/cerrado.png"})
        check(st == 200 and d.get("ok"), "el servidor acepta el aviso de standby")
        st, pantallas = pedir("/api/screens")
        ahora = (pantallas.get("TV") or {}).get("now") or {}
        check(ahora.get("type") == "standby" and ahora.get("img") == "/uploads/cerrado.png",
              "el panel recibe el tipo y la imagen")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
