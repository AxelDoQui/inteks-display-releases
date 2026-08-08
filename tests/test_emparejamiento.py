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

        # ── known_as: la pista que permite el reenlace de un clic ──────────
        # Cuando un televisor se desenlaza, recuerda como se llamaba y lo manda
        # al pedir codigo. Es un dato SIN autoridad -lo envia un cliente sin
        # autenticar- y solo sirve para que el panel sugiera; quien decide es el
        # administrador.
        d3 = req("/api/pair-request", {"known_as": "TV-Escaparate"})
        pend = req("/api/pair-pending", tok=TOKEN)["pending"]
        fila = next((x for x in pend if x["code"] == d3["code"]), None)
        check(fila is not None and fila.get("known_as") == "TV-Escaparate",
              "el panel ve de que pantalla venia el codigo")

        d4 = req("/api/pair-request", {})
        fila4 = next((x for x in req("/api/pair-pending", tok=TOKEN)["pending"]
                      if x["code"] == d4["code"]), None)
        check(fila4 is not None and fila4.get("known_as") == "",
              "sin pista, known_as viene vacio y no rompe el panel")

        # ── Reenlazar: devolverle su identidad a una pantalla existente ─────
        # Es el caso que dejaba sin salida: el televisor perdio su memoria (o
        # arranco por /pair) y hay que devolverle SU pantalla, con su playlist,
        # su horario y su rotacion intactos.
        cpath = os.path.join(datos, "content.json")
        cont = json.load(open(cpath))
        cont["screens"]["TV-Escaparate"] = {
            "mode": "independent", "rotation": 90,
            "playlist": [{"id": "x1", "type": "text", "title": "HOLA"}],
            "schedule": {"lunes": {"enabled": True, "start": "09:00", "end": "21:00"}},
        }
        json.dump(cont, open(cpath, "w"))

        d5 = req("/api/pair-request", {"known_as": "TV-Escaparate"})
        r5 = req("/api/pair-claim",
                 {"code": d5["code"], "screen_name": "TV-Escaparate", "modo": "reenlazar"},
                 tok=TOKEN)
        check(r5.get("ok"), "se puede reenlazar a una pantalla que ya existe")

        st5 = req("/api/pair-status", {"token": d5["token"]})
        check(st5["claimed"] and st5["screen"] == "TV-Escaparate",
              "y la pantalla recibe su nombre de siempre")

        cont = json.load(open(cpath))["screens"]["TV-Escaparate"]
        check(len(cont.get("playlist", [])) == 1 and cont["playlist"][0]["title"] == "HOLA",
              "reenlazar NO toca la playlist")
        check(cont.get("rotation") == 90, "ni la rotacion")
        check(cont.get("schedule", {}).get("lunes", {}).get("start") == "09:00",
              "ni el horario")

        d6 = req("/api/pair-request", {})
        try:
            req("/api/pair-claim",
                {"code": d6["code"], "screen_name": "No-Existe", "modo": "reenlazar"},
                tok=TOKEN)
            check(False, "reenlazar a una inexistente deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "reenlazar a una pantalla inexistente da error")

        # Retrocompatibilidad: sin modo, se comporta como "nueva"
        try:
            req("/api/pair-claim", {"code": d6["code"], "screen_name": "TV-Escaparate"},
                tok=TOKEN)
            check(False, "sin modo, un nombre duplicado deberia seguir fallando")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "sin modo se sigue comportando como 'nueva'")

        check(req("/api/pair-claim",
                  {"code": d6["code"], "screen_name": "TV-Caja", "modo": "nueva"},
                  tok=TOKEN).get("ok"),
              "crear una pantalla nueva sigue funcionando")

        # ── Desenlazar: soltar el dispositivo sin borrar la pantalla ────────
        # Es lo contrario de eliminar. La pantalla sigue ahi con todo lo suyo;
        # solo el televisor olvida quien era, para poder reenlazarlo desde el
        # panel sin levantarse a tocarlo.
        r7 = req("/api/screen-unlink", {"screen": "TV-Escaparate"}, tok=TOKEN)
        check(r7.get("ok"), "se puede desenlazar una pantalla")

        cont = json.load(open(cpath))["screens"].get("TV-Escaparate", {})
        check(len(cont.get("playlist", [])) == 1,
              "desenlazar NO borra la playlist")
        check(cont.get("rotation") == 90, "ni la rotacion")
        scr = json.load(open(os.path.join(datos, "screens.json")))
        check("TV-Escaparate" in scr, "y la pantalla sigue en el registro")

        try:
            req("/api/screen-unlink", {"screen": "Fantasma"}, tok=TOKEN)
            check(False, "desenlazar una inexistente deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "desenlazar una pantalla inexistente da error")

        try:
            req("/api/screen-unlink", {"screen": "TV-Escaparate"})
            check(False, "desenlazar sin autenticacion deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 401, "desenlazar exige autenticacion")

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
