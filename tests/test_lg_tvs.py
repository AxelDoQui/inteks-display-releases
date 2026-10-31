"""
Aviso de caducidad del Developer Mode de los televisores LG.

instalar-lg.ps1 apunta cada TV en lg_tvs.json con el inicio de su sesion; el
servidor calcula lo que queda (1000 h) y el panel avisa 7 dias antes.

Ejecutar:  python tests/test_lg_tvs.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8132
TOKEN = "tok-prueba-lg-tvs"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    html = open(os.path.join(SRC, "admin.html"), encoding="utf-8").read()
    check('id="aviso-lg"' in html and 'id="card-lg"' in html, "el panel tiene el aviso y la tarjeta")
    check("cargarLgTvs();" in html, "el panel los pide al abrir")

    app = tempfile.mkdtemp(prefix="signalos_lg_")
    datos = tempfile.mkdtemp(prefix="signalos_lgd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    ahora = int(time.time())
    H = 3600
    json.dump({"tvs": [
        {"id": "10.0.0.1", "nombre": "Reciente", "ip": "10.0.0.1", "inicio": ahora - 2 * H},
        {"id": "10.0.0.2", "nombre": "Casi", "ip": "10.0.0.2", "inicio": ahora - (1000 - 100) * H},
        {"id": "10.0.0.3", "nombre": "Caducado", "ip": "10.0.0.3", "inicio": ahora - 1200 * H},
        {"id": "10.0.0.4", "nombre": "Roto", "ip": "10.0.0.4", "inicio": "no-es-numero"},
    ]}, open(os.path.join(datos, "lg_tvs.json"), "w"))

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def pedir(ruta, payload=None):
        r = urllib.request.Request(
            base + ruta, data=None if payload is None else json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN},
            method="GET" if payload is None else "POST")
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco")
            return 1

        try:
            urllib.request.urlopen(base + "/api/lg-tvs", timeout=3)
            check(False, "sin sesion no se puede ver la lista")
        except urllib.error.HTTPError as e:
            check(e.code in (401, 403), "sin sesion no se puede ver la lista")

        st, d = pedir("/api/lg-tvs")
        tvs = {t["id"]: t for t in d["tvs"]}
        check(st == 200 and len(tvs) == 3, "salen 3 TV (el de fecha rota se ignora)")
        check(997 <= tvs["10.0.0.1"]["restante_h"] <= 998 and not tvs["10.0.0.1"]["aviso"],
              "uno reciente: ~998 h y sin aviso")
        check(99 <= tvs["10.0.0.2"]["restante_h"] <= 100 and tvs["10.0.0.2"]["aviso"],
              "a 100 h (4 dias): dentro de la franja de aviso de 7 dias")
        check(tvs["10.0.0.3"]["restante_h"] == 0 and tvs["10.0.0.3"]["aviso"],
              "caducado: 0 h y con aviso")

        # 7 dias = 168 h: a 160 h avisa; a 180 h todavia no
        json.dump({"tvs": [{"id": "x", "nombre": "x", "ip": "x", "inicio": ahora - (1000 - 180) * H}]},
                  open(os.path.join(datos, "lg_tvs.json"), "w"))
        st, d = pedir("/api/lg-tvs")
        check(d["tvs"][0]["aviso"] is False, "a 180 h todavia no avisa")
        json.dump({"tvs": [{"id": "x", "nombre": "x", "ip": "x", "inicio": ahora - (1000 - 160) * H}]},
                  open(os.path.join(datos, "lg_tvs.json"), "w"))
        st, d = pedir("/api/lg-tvs")
        check(d["tvs"][0]["aviso"] is True, "a 160 h avisa (franja de 7 dias)")

        st, _ = pedir("/api/lg-tvs/renovado", {"id": "x"})
        st2, d = pedir("/api/lg-tvs")
        check(st == 200 and d["tvs"][0]["restante_h"] >= 998 and not d["tvs"][0]["aviso"],
              "«ya lo renove» reinicia la cuenta atras")
        st, _ = pedir("/api/lg-tvs/renovado", {"id": "no-existe"})
        check(st == 404, "renovar uno que no existe da 404")
        st, _ = pedir("/api/lg-tvs/renovado", {})
        check(st == 400, "sin id da 400")
        st, _ = pedir("/api/lg-tvs/vigilar", {"id": "x", "activo": True})
        st2, d = pedir("/api/lg-tvs")
        check(st == 200 and d["tvs"][0]["vigilar"] is True, "activar «mantener abierta» se guarda")
        st, _ = pedir("/api/lg-tvs/vigilar", {"id": "x", "activo": False})
        st2, d = pedir("/api/lg-tvs")
        check(st == 200 and d["tvs"][0]["vigilar"] is False, "desactivarla se guarda")
        st, _ = pedir("/api/lg-tvs/vigilar", {"id": "x"})
        check(st == 400, "vigilar sin activo da 400")
        st, _ = pedir("/api/lg-tvs/vigilar", {"id": "no-existe", "activo": True})
        check(st == 404, "vigilar uno que no existe da 404")
        st, _ = pedir("/api/lg-tvs/borrar", {"id": "x"})
        st2, d = pedir("/api/lg-tvs")
        check(st == 200 and d["tvs"] == [], "quitar lo borra de la lista")
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
