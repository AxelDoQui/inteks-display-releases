"""
Un paquete tiene que ser un grupo VIVO, no un "pegar varios de golpe".

Antes, aplicar un paquete copiaba sus contenidos dentro de la playlist de la
pantalla sin dejar ninguna huella de donde venian. Editar el paquete despues no
cambiaba nada en las pantallas, y no habia forma de arreglarlo: no existia
ningun dato que dijera que esas diapositivas salieron de ese paquete.

Ahora la playlist guarda una referencia y el servidor la expande al servirla.
Asi no hay copias que puedan quedarse viejas: es imposible por construccion.

Ejecutar:  python tests/test_paquetes.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8097
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_pkg_")
    datos = tempfile.mkdtemp(prefix="signalos_pkgd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)

    cpath = os.path.join(datos, "content.json")
    contenido = {
        "items": [
            {"id": "it_a", "name": "Cartel A", "type": "image", "src": "/uploads/a.png"},
            {"id": "it_b", "name": "Cartel B", "type": "image", "src": "/uploads/b.png"},
            {"id": "it_c", "name": "Suelto",   "type": "image", "src": "/uploads/c.png"},
        ],
        "packages": [
            {"id": "pkg_1", "name": "Mañana",
             "items": [{"id": "it_a", "duration": 10}, {"id": "it_b", "duration": 5}]},
        ],
        "screens": {
            "TV": {"mode": "independent", "playlist": [
                {"type": "package", "pkg_id": "pkg_1"},
                {"id": "it_c", "name": "Suelto", "type": "image",
                 "src": "/uploads/c.png", "duration": 7},
            ]},
        },
    }
    json.dump(contenido, open(cpath, "w"))

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def playlist(sid="TV"):
        r = urllib.request.urlopen(f"{base}/api/playlist?screen={sid}", timeout=5)
        return json.load(r)["playlist"]

    def guardar(c):
        json.dump(c, open(cpath, "w"))

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

        pl = playlist()
        check([x.get("id") for x in pl] == ["it_a", "it_b", "it_c"],
              f"el paquete se expande en su sitio -> {[x.get('id') for x in pl]}")
        check(not any(x.get("type") == "package" for x in pl),
              "y la pantalla no ve la referencia, solo contenidos")
        check([x.get("duration") for x in pl] == [10, 5, 7],
              "cada contenido conserva la duracion que le puso el paquete")
        check(pl[0].get("name") == "Cartel A" and pl[0].get("src") == "/uploads/a.png",
              "con todos los datos del contenido original")

        # ── LO QUE MOTIVA TODO ESTO ────────────────────────────────────────
        # Editar el paquete tiene que verse en la pantalla sin tocar la
        # pantalla. Antes habia que volver a aplicarlo a mano, una por una.
        contenido["packages"][0]["items"] = [{"id": "it_b", "duration": 3}]
        guardar(contenido)
        pl = playlist()
        check([x.get("id") for x in pl] == ["it_b", "it_c"],
              f"quitar un contenido del paquete llega a la pantalla -> {[x.get('id') for x in pl]}")
        check(pl[0].get("duration") == 3,
              "y cambiar su duracion tambien")

        contenido["packages"][0]["items"] = [
            {"id": "it_b", "duration": 3}, {"id": "it_a", "duration": 9}]
        guardar(contenido)
        check([x.get("id") for x in playlist()] == ["it_b", "it_a", "it_c"],
              "anadir un contenido al paquete tambien llega")

        # ── Que no se rompa nada ───────────────────────────────────────────
        # Un contenido borrado de la libreria pero aun listado en el paquete.
        contenido["packages"][0]["items"] = [
            {"id": "it_a", "duration": 9}, {"id": "fantasma", "duration": 4}]
        guardar(contenido)
        check([x.get("id") for x in playlist()] == ["it_a", "it_c"],
              "un contenido que ya no existe se salta sin romper la playlist")

        # Un paquete borrado y una referencia huerfana: la pantalla sigue
        # reproduciendo el resto en vez de quedarse en negro.
        contenido["packages"] = []
        guardar(contenido)
        check([x.get("id") for x in playlist()] == ["it_c"],
              "una referencia a un paquete borrado no tumba la pantalla")

        # Sin paquetes de por medio, todo sigue exactamente igual que antes.
        contenido["screens"]["TV"]["playlist"] = [
            {"id": "it_c", "name": "Suelto", "type": "image", "src": "/uploads/c.png",
             "duration": 7}]
        guardar(contenido)
        pl = playlist()
        check(len(pl) == 1 and pl[0]["id"] == "it_c" and pl[0]["duration"] == 7,
              "una playlist sin paquetes pasa intacta")

        # ── Videowall: los contenidos expandidos tambien llevan su marca ────
        contenido["packages"] = [
            {"id": "pkg_1", "name": "Mañana", "items": [{"id": "it_a", "duration": 10}]}]
        contenido["screens"]["W"] = {"mode": "wall", "wall_pos": "left", "partner": "W2",
                                     "playlist": [{"type": "package", "pkg_id": "pkg_1"}]}
        guardar(contenido)
        pl = playlist("W")
        check(len(pl) == 1 and pl[0].get("id") == "it_a"
              and pl[0].get("wall_mode") is True and pl[0].get("wall_pos") == "left",
              f"en videowall los contenidos expandidos llevan su marca -> {pl}")

        # ── Paquete vacio ──────────────────────────────────────────────────
        contenido["packages"] = [{"id": "pkg_1", "name": "Vacio", "items": []}]
        contenido["screens"]["TV"]["playlist"] = [
            {"type": "package", "pkg_id": "pkg_1"},
            {"id": "it_c", "name": "Suelto", "type": "image", "src": "/uploads/c.png"}]
        guardar(contenido)
        check([x.get("id") for x in playlist()] == ["it_c"],
              "un paquete vacio no deja huecos")

        # ── Formato antiguo de paquete (itemIds) ───────────────────────────
        # Los paquetes creados antes guardaban solo una lista de ids.
        contenido["packages"] = [{"id": "pkg_1", "name": "Viejo",
                                  "itemIds": ["it_a", "it_b"]}]
        guardar(contenido)
        check([x.get("id") for x in playlist()] == ["it_a", "it_b", "it_c"],
              "los paquetes en formato antiguo tambien se expanden")
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
