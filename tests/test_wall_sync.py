"""
Videowall: la pantalla izquierda cuenta qué muestra (POST /api/wall-sync) y la derecha lo pregunta
(GET /api/wall-sync). La derecha recibe la playlist de la izquierda, para que nunca se desfasen.

Ejecutar:  py tests/test_wall_sync.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8141
TOKEN = "tok-prueba-video"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html", "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_wall_"); datos = tempfile.mkdtemp(prefix="signalos_walld_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    item = {"id": "a", "type": "text", "name": "UNO", "title": "UNO", "duration": 4}
    json.dump({"rev": 1, "items": [], "screens": {
        "L": {"mode": "wall", "wall_pos": "left", "partner": "R", "playlist": [item]},
        "R": {"mode": "wall", "wall_pos": "right", "partner": "L", "playlist": []},
        "S": {"mode": "independent", "playlist": []},
        "X": {"mode": "wall", "wall_ids": ["X", "Y", "Z"], "wall_idx": 0, "playlist": [item]},
        "Y": {"mode": "wall", "wall_ids": ["X", "Y", "Z"], "wall_idx": 1, "playlist": []},
        "Z": {"mode": "wall", "wall_ids": ["X", "Y", "Z"], "wall_idx": 2, "playlist": []}}}, open(os.path.join(datos, "content.json"), "w"))
    json.dump({n: {"name": n, "connected": True} for n in "LRSXYZ"}, open(os.path.join(datos, "screens.json"), "w"))
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
        st, d = pedir("/api/wall-sync?screen=R")
        check(st == 200 and d["estado"] is None, "sin nada de la izquierda, la derecha no recibe estado")
        pedir("/api/wall-sync", {"screen": "L", "id": "a", "t": 3.5, "video": True})
        st, d = pedir("/api/wall-sync?screen=R")
        e = d["estado"]
        check(e and e["id"] == "a" and e["t"] == 3.5 and e["video"] is True, "la derecha recibe qué contenido y qué segundo")
        check(abs(d["ahora"] - e["at"]) < 5, "estado y hora vienen del mismo reloj (el del servidor)")
        pedir("/api/wall-sync", {"screen": "R", "id": "zzz", "t": 1})
        check(pedir("/api/wall-sync?screen=R")[1]["estado"]["id"] == "a", "solo manda la izquierda: la derecha no puede cambiarlo")
        check(pedir("/api/wall-sync?screen=S")[1]["estado"] is None, "una pantalla independiente no recibe estado")
        pl = pedir("/api/playlist?screen=R")[1]["playlist"]
        check([i["id"] for i in pl] == ["a"] and pl[0]["wall_pos"] == "right", "la derecha usa la playlist de la izquierda")
        pl = pedir("/api/playlist?screen=L")[1]["playlist"]
        check([i["id"] for i in pl] == ["a"] and pl[0]["wall_pos"] == "left", "la izquierda sigue con la suya")
        # Muro de tres: manda la primera, las otras dos la siguen y llevan su trozo
        pedir("/api/wall-sync", {"screen": "X", "id": "a", "t": 2})
        check(pedir("/api/wall-sync?screen=Y")[1]["estado"]["t"] == 2, "la 2.ª de 3 recibe el estado de la 1.ª")
        check(pedir("/api/wall-sync?screen=Z")[1]["estado"]["t"] == 2, "la 3.ª de 3 recibe el estado de la 1.ª")
        pedir("/api/wall-sync", {"screen": "Y", "id": "zzz", "t": 9})
        check(pedir("/api/wall-sync?screen=Z")[1]["estado"]["id"] == "a", "la del medio no puede mandar")
        for sid, idx in (("X", 0), ("Y", 1), ("Z", 2)):
            r = pedir("/api/playlist?screen=" + sid)[1]
            it = r["playlist"][0]
            check([i["id"] for i in r["playlist"]] == ["a"] and it["wall_idx"] == idx and it["wall_n"] == 3 and r["config"]["wall_idx"] == idx,
                  f"la pantalla {idx + 1} de 3 usa la playlist de la 1.ª y sabe su sitio")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
