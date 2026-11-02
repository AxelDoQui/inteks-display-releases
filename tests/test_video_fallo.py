"""
El reproductor avisa de un vídeo que no puede reproducir (video_fallo) y de que ya se ve (video_ok):
el servidor lo guarda aparte de «ahora» y lo entrega con /api/screens hasta que el vídeo funcione.

Ejecutar:  python tests/test_video_fallo.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8140
TOKEN = "tok-prueba-video"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html", "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_vf_"); datos = tempfile.mkdtemp(prefix="signalos_vfd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    json.dump({"rev": 1, "screens": {}}, open(os.path.join(datos, "content.json"), "w"))
    json.dump({"HI": {"name": "HI", "connected": True}}, open(os.path.join(datos, "screens.json"), "w"))
    env = dict(os.environ, SIGNALOS_DATA=datos)
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def pedir(ruta, payload=None):
        r = urllib.request.Request(base + ruta, data=None if payload is None else json.dumps(payload).encode(),
                                   headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN},
                                   method="GET" if payload is None else "POST")
        try:
            with urllib.request.urlopen(r, timeout=8) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1); break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco"); return 1
        st, d = pedir("/api/screen-now", {"screen": "HI", "video_fallo": {"id": "v1", "name": "mi.mp4", "motivo": "no llega a arrancar"}})
        check(st == 200 and d.get("ok"), "acepta el aviso de fallo")
        f = pedir("/api/screens")[1]["HI"].get("video_fallo")
        check(f and f["name"] == "mi.mp4" and f["motivo"] == "no llega a arrancar", "el panel lo recibe con /api/screens")
        pedir("/api/screen-now", {"screen": "HI", "id": "x", "name": "otra", "type": "image"})
        check(pedir("/api/screens")[1]["HI"].get("video_fallo") is not None, "cambiar de diapositiva no lo borra")
        pedir("/api/screen-now", {"screen": "HI", "video_ok": "otro"})
        check(pedir("/api/screens")[1]["HI"].get("video_fallo") is not None, "el ok de OTRO vídeo no lo borra")
        pedir("/api/screen-now", {"screen": "HI", "video_ok": "v1"})
        check("video_fallo" not in pedir("/api/screens")[1]["HI"], "cuando ese vídeo ya se ve, desaparece")
        st, _ = pedir("/api/screen-now", {"screen": "NOEXISTE", "video_fallo": {"id": "a", "name": "b", "motivo": "c"}})
        check(st == 404, "una pantalla inventada no llena la memoria")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
