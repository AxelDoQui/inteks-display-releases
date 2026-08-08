"""
Flujo completo de emparejamiento inverso.

La PANTALLA pide un codigo y lo muestra; el ADMIN le pone nombre. Antes era al
reves: el admin generaba un PIN y habia que teclearlo en el televisor con el
mando, que es justo lo incomodo.

Ejecutar:  python tests/test_emparejamiento.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8086
TOKEN = "tok-prueba-enlace"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_pair_")
    datos = tempfile.mkdtemp(prefix="signalos_paird_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(datos, "admin.json"), "w"))
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def req(path, data=None, tok=None):
        h = {"Content-Type": "application/json"}
        if tok:
            h["X-SignalOS-Token"] = tok
        r = urllib.request.Request(
            base + path, data=json.dumps(data).encode() if data is not None else None,
            headers=h, method="POST" if data is not None else "GET")
        return json.load(urllib.request.urlopen(r, timeout=5))

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass

        d = req("/api/pair-request", {})
        codigo, token = d["code"], d["token"]
        check(len(codigo) == 4 and codigo.isdigit(), f"la pantalla recibe un codigo: {codigo}")
        check(req("/api/pair-status", {"token": token})["claimed"] is False,
              "y espera, sin enlazar todavia")

        pend = req("/api/pair-pending", tok=TOKEN)["pending"]
        check(any(x["code"] == codigo for x in pend), "el admin la ve en la lista de espera")
        try:
            req("/api/pair-pending")
            check(False, "la lista deberia exigir autenticacion")
        except urllib.error.HTTPError as ex:
            check(ex.code == 401, "la lista exige autenticacion")

        check(req("/api/pair-claim", {"code": codigo, "screen_name": "TV-Escaparate"},
                  tok=TOKEN).get("ok"), "el admin le pone nombre")

        st = req("/api/pair-status", {"token": token})
        check(st["claimed"] and st["screen"] == "TV-Escaparate",
              "la pantalla se entera de como se llama")

        scr = json.load(open(os.path.join(datos, "screens.json")))
        check("TV-Escaparate" in scr, "queda registrada")
        cont = json.load(open(os.path.join(datos, "content.json")))
        check("TV-Escaparate" in cont.get("screens", {}), "y con su playlist lista")

        try:
            req("/api/pair-claim", {"code": "0000", "screen_name": "X"}, tok=TOKEN)
            check(False, "un codigo inexistente deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "un codigo que no espera da error")

        d2 = req("/api/pair-request", {})
        try:
            req("/api/pair-claim", {"code": d2["code"], "screen_name": "TV-Escaparate"}, tok=TOKEN)
            check(False, "un nombre duplicado deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "un nombre ya usado da error")

        check(req("/api/pair-status", {"token": "inventado"}).get("expired") is True,
              "un token desconocido hace que la pantalla pida otro codigo")
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
