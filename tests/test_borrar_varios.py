"""
Borrar varios archivos de la Librería de una vez: /api/delete con "ids".

Quita los archivos de la librería, de las playlists de las pantallas y de los
paquetes (tanto el formato viejo itemIds como el nuevo items), y borra del disco
los subidos. Con "id" (uno solo) sigue funcionando como siempre.

Ejecutar:  python tests/test_borrar_varios.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8134
TOKEN = "tok-prueba-borrar"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_del_")
    datos = tempfile.mkdtemp(prefix="signalos_deld_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    os.makedirs(os.path.join(datos, "uploads"))
    for n in ("a.png", "b.png", "c.png"):
        open(os.path.join(datos, "uploads", n), "wb").write(b"x")
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    it = lambda i: {"id": i, "name": i, "type": "image", "src": "/uploads/" + i}
    json.dump({"rev": 1,
               "items": [it("a.png"), it("b.png"), it("c.png")],
               "screens": {"TV": {"mode": "independent", "playlist": [it("a.png"), it("c.png")]}},
               "packages": [{"id": "p1", "name": "P", "items": [{"id": "a.png", "duration": 5}, {"id": "b.png", "duration": 5}]},
                            {"id": "p2", "name": "Q", "itemIds": ["a.png", "c.png"]}]},
              open(os.path.join(datos, "content.json"), "w"))
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
        st, _ = pedir("/api/delete", {"ids": ["a.png", "b.png"]})
        _, c = pedir("/api/content")
        check(st == 200 and [i["id"] for i in c["items"]] == ["c.png"], "borra varios de la libreria de una vez")
        check([x["id"] for x in c["screens"]["TV"]["playlist"]] == ["c.png"], "los quita de las playlists")
        pk = {x["id"]: x for x in c["packages"]}
        check(pk["p1"]["items"] == [] and pk["p2"]["itemIds"] == ["c.png"], "los quita de los paquetes (formato nuevo y viejo)")
        up = os.listdir(os.path.join(datos, "uploads"))
        check(up == ["c.png"], "borra del disco los subidos")
        st, _ = pedir("/api/delete", {"id": "c.png"})
        _, c = pedir("/api/content")
        check(st == 200 and c["items"] == [], "con un solo id sigue funcionando")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
