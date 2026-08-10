"""
Copia de seguridad y restauracion.

Toda la configuracion de una tienda -pantallas, playlists, modulos de divisas,
imagenes y videos- vivia solo en el disco de ese PC. Si el equipo moria, se
perdia entera y habia que rehacerla a mano. Y montar una segunda tienda
significaba repetir todo el trabajo desde cero.

Lo que NO va en la copia: admin.json y pin.json. Llevan el hash de la
contrasena, el secreto de sesion y el token de la extension. Un archivo que
viaja por correo o en un pendrive no puede llevar eso dentro.

Ejecutar:  python tests/test_backup.py
"""
import io, json, os, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request, zipfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8098
TOKEN = "tok-prueba-copia"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_bk_")
    datos = tempfile.mkdtemp(prefix="signalos_bkd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)

    json.dump({"api_token": TOKEN, "secret": "s" * 64, "pwd_hash": "no-deberia-viajar"},
              open(os.path.join(datos, "admin.json"), "w"))
    cpath = os.path.join(datos, "content.json")
    json.dump({"items": [{"id": "it_1", "name": "Cartel", "type": "image",
                          "src": "/uploads/cartel.png"}],
               "packages": [],
               "screens": {"TV": {"mode": "independent", "playlist": []}}},
              open(cpath, "w"))
    spath = os.path.join(datos, "screens.json")
    json.dump({"TV": {"id": "TV", "connected": False, "last_seen": 1}}, open(spath, "w"))
    os.makedirs(os.path.join(datos, "uploads"), exist_ok=True)
    upath = os.path.join(datos, "uploads", "cartel.png")
    open(upath, "wb").write(b"\x89PNG\r\n\x1a\n" + b"x" * 200)

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def get(path, tok=TOKEN):
        h = {"X-SignalOS-Token": tok} if tok else {}
        return urllib.request.urlopen(
            urllib.request.Request(base + path, headers=h), timeout=20).read()

    def post_raw(path, data, tipo="application/zip", tok=TOKEN):
        h = {"Content-Type": tipo}
        if tok:
            h["X-SignalOS-Token"] = tok
        r = urllib.request.Request(base + path, data=data, headers=h, method="POST")
        return json.load(urllib.request.urlopen(r, timeout=20))

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

        # ── Descargar la copia ─────────────────────────────────────────────
        crudo = get("/api/backup")
        z = zipfile.ZipFile(io.BytesIO(crudo))
        nombres = set(z.namelist())
        check("content.json" in nombres and "screens.json" in nombres
              and "config.json" in nombres,
              f"la copia lleva la configuracion -> {sorted(nombres)}")
        check("uploads/cartel.png" in nombres, "y los archivos subidos")
        check("inteks-backup.json" in nombres, "con una ficha que identifica la copia")

        # ── Lo que NO puede viajar ─────────────────────────────────────────
        check(not any("admin.json" in n for n in nombres),
              "admin.json NO viaja en la copia (lleva el hash y el token)")
        check(not any("pin.json" in n for n in nombres), "pin.json tampoco")
        check(b"no-deberia-viajar" not in crudo,
              "y el hash de la contrasena no aparece por ningun lado")

        ficha = json.loads(z.read("inteks-backup.json"))
        check(ficha.get("app") == "InTeks Display" and "created_at" in ficha,
              f"la ficha dice de donde salio -> {ficha}")

        # ── Exige autenticacion ────────────────────────────────────────────
        try:
            get("/api/backup", tok=None)
            check(False, "la copia deberia exigir autenticacion")
        except urllib.error.HTTPError as ex:
            check(ex.code == 401, "descargar la copia exige autenticacion")

        # ── Copia sin multimedia, para poder mandarla por correo ───────────
        z2 = zipfile.ZipFile(io.BytesIO(get("/api/backup?media=0")))
        check("content.json" in z2.namelist()
              and not any(n.startswith("uploads/") for n in z2.namelist()),
              "se puede pedir la copia sin imagenes ni videos")

        # ── Restaurar ──────────────────────────────────────────────────────
        json.dump({"items": [], "packages": [], "screens": {}}, open(cpath, "w"))
        os.remove(upath)
        r = post_raw("/api/restore", crudo)
        check(r.get("ok"), f"se puede restaurar -> {r}")

        vuelto = json.load(open(cpath))
        check(len(vuelto.get("items", [])) == 1
              and vuelto["items"][0]["id"] == "it_1",
              "la configuracion vuelve tal cual")
        check(os.path.exists(upath) and open(upath, "rb").read().startswith(b"\x89PNG"),
              "y los archivos subidos tambien")

        adm = json.load(open(os.path.join(datos, "admin.json")))
        check(adm.get("api_token") == TOKEN and adm.get("pwd_hash") == "no-deberia-viajar",
              "restaurar NO pisa las credenciales de este equipo")

        # ── El contador de revision al restaurar ───────────────────────────
        # La copia trae el rev de OTRA instalacion. Si coincidiera con el que
        # tiene un panel abierto aqui, ese panel podria escribir encima de lo
        # recien restaurado creyendose al dia. Por eso el contador solo crece:
        # rev = max(el de aqui, el de la copia) + 1.
        def copia_con_rev(rev):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("inteks-backup.json",
                            json.dumps({"app": "InTeks Display", "created_at": 1}))
                zf.writestr("content.json", json.dumps(
                    {"items": [{"id": "it_1", "name": "Cartel", "type": "image",
                                "src": "/uploads/cartel.png"}],
                     "packages": [], "screens": {}, "rev": rev}))
            return buf.getvalue()

        local = int(json.load(open(cpath)).get("rev", 0))
        post_raw("/api/restore", copia_con_rev(local + 50))
        tras_alta = int(json.load(open(cpath)).get("rev", 0))
        check(tras_alta > local + 50,
              f"si la copia trae un rev mas alto, el de aqui lo supera "
              f"(aqui {local}, copia {local + 50} -> queda {tras_alta})")

        post_raw("/api/restore", copia_con_rev(0))
        tras_baja = int(json.load(open(cpath)).get("rev", 0))
        check(tras_baja > tras_alta,
              f"y si la copia trae uno mas bajo, el contador no retrocede "
              f"(aqui {tras_alta}, copia 0 -> queda {tras_baja})")

        # ── Que no se cuele nada raro ──────────────────────────────────────
        try:
            post_raw("/api/restore", b"esto no es un zip")
            check(False, "un archivo que no es zip deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "un archivo que no es un zip da error")

        malo = io.BytesIO()
        with zipfile.ZipFile(malo, "w") as zf:
            zf.writestr("inteks-backup.json", json.dumps({"app": "InTeks Display"}))
            zf.writestr("content.json", json.dumps({"items": [], "screens": {}}))
            zf.writestr("../../pwned.txt", "deberia quedarse fuera")
            zf.writestr("uploads/../../pwned2.txt", "y esto tambien")
        r = post_raw("/api/restore", malo.getvalue())
        fuera = os.path.dirname(datos)
        check(not os.path.exists(os.path.join(fuera, "pwned.txt"))
              and not os.path.exists(os.path.join(fuera, "pwned2.txt")),
              "un zip con rutas hacia fuera no escribe fuera de la carpeta de datos")

        try:
            zsin = io.BytesIO()
            with zipfile.ZipFile(zsin, "w") as zf:
                zf.writestr("cualquier.txt", "hola")
            post_raw("/api/restore", zsin.getvalue())
            check(False, "un zip que no es una copia deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 400, "un zip que no es una copia de InTeks da error")

        try:
            post_raw("/api/restore", crudo, tok=None)
            check(False, "restaurar sin autenticacion deberia fallar")
        except urllib.error.HTTPError as ex:
            check(ex.code == 401, "restaurar exige autenticacion")

        # ── Techo de tamano ────────────────────────────────────────────────
        # El cuerpo se carga entero en memoria; sin techo, un envio gigante
        # tumbaria el servidor de la tienda.
        try:
            req = urllib.request.Request(
                base + "/api/restore", data=b"x",
                headers={"Content-Type": "application/zip",
                         "X-SignalOS-Token": TOKEN,
                         "Content-Length": str(900 * 1024 * 1024)}, method="POST")
            urllib.request.urlopen(req, timeout=10)
            check(False, "un envio gigante deberia rechazarse")
        except urllib.error.HTTPError as ex:
            check(ex.code == 413, "un envio gigante se rechaza antes de leerlo")
        except Exception as ex:
            check(False, f"un envio gigante se rechaza antes de leerlo -> {type(ex).__name__}")
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
