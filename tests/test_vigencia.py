"""
Vigencia por fechas.

Un contenido se quedaba en la pantalla hasta que alguien lo quitaba a mano.
Ahora una promo puede entrar y salir sola.

La regla importante es la del final: si TODO ha caducado no se deja la
pantalla en negro. Una promo vieja en el escaparate es malo; un escaparate
apagado es peor, y encima no se distingue de una averia.

Ejecutar:  python tests/test_vigencia.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8105
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def item(id_, desde="", hasta=""):
    return {"id": id_, "type": "image", "src": f"/uploads/{id_}.png",
            "duration": 8, "desde": desde, "hasta": hasta}


def main():
    app = tempfile.mkdtemp(prefix="signalos_vig_")
    datos = tempfile.mkdtemp(prefix="signalos_vigd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    cpath = os.path.join(datos, "content.json")

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def guardar(playlist):
        json.dump({"items": [], "packages": [],
                   "screens": {"TV": {"mode": "independent", "playlist": playlist}}},
                  open(cpath, "w"))

    def ids():
        r = urllib.request.urlopen(f"{base}/api/playlist?screen=TV", timeout=5)
        return [x.get("id") for x in json.load(r)["playlist"]]

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

        # Sin fechas, todo se ve. El comportamiento de siempre no cambia.
        guardar([item("a"), item("b")])
        check(ids() == ["a", "b"], f"sin fechas se ve todo -> {ids()}")

        # Caducado y todavia no empezado se ocultan.
        guardar([item("a"), item("viejo", hasta="2020-01-01"),
                 item("futuro", desde="2099-01-01")])
        check(ids() == ["a"], f"lo caducado y lo futuro no se ven -> {ids()}")

        # Los limites son inclusivos: el ultimo dia todavia se ve.
        hoy = time.strftime("%Y-%m-%d")
        guardar([item("hoy_fin", hasta=hoy)])
        check(ids() == ["hoy_fin"], "el ultimo dia de vigencia todavia se ve")
        guardar([item("hoy_ini", desde=hoy)])
        check(ids() == ["hoy_ini"], "el primer dia de vigencia ya se ve")

        # Solo un extremo.
        guardar([item("desde_ya", desde="2020-01-01"),
                 item("hasta_lejos", hasta="2099-01-01")])
        check(ids() == ["desde_ya", "hasta_lejos"],
              "con un solo extremo tambien funciona")

        # LA REGLA QUE IMPORTA: si todo ha caducado, no se apaga la pantalla.
        guardar([item("v1", hasta="2020-01-01"), item("v2", hasta="2020-02-01")])
        check(ids() == ["v1", "v2"],
              f"si TODO ha caducado se sigue mostrando -> {ids()}")

        # Una fecha con formato raro no puede ocultar contenido.
        guardar([item("raro", hasta="no-es-una-fecha"), item("b")])
        check(ids() == ["raro", "b"],
              "una fecha invalida se ignora en vez de esconder el contenido")

        # Una playlist vacia sigue vacia, sin inventarse nada.
        guardar([])
        check(ids() == [], "una playlist vacia sigue vacia")
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
