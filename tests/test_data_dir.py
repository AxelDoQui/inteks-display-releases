"""
El programa y sus datos no pueden vivir en la misma carpeta.

Instalado en C:\\Program Files, Windows prohibe escribir junto al ejecutable, y
el servidor moria al arrancar con PermissionError al crear 'uploads'. Los datos
tienen que irse a una carpeta escribible, sin romper el modo de desarrollo,
donde todo convive en la carpeta del proyecto.

Ejecutar:  python tests/test_data_dir.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8090
ESTADO = ("uploads", "screens.json", "content.json", "config.json")
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")


def arrancar(cwd, env=None, port=PORT):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(port)],
                         cwd=cwd, env=e, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    for _ in range(40):
        time.sleep(0.25)
        if p.poll() is not None:
            return p, p.stdout.read()
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/auth-status", timeout=1)
            return p, None
        except Exception:
            pass
    return p, "no arranco a tiempo"


def parar(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()


def main():
    fallos = 0

    # ── 1. Desarrollo: todo junto en la carpeta del proyecto ────────────────
    dev = tempfile.mkdtemp(prefix="signalos_dev_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), dev)
    p, err = arrancar(dev)
    try:
        ok = err is None and all(os.path.exists(os.path.join(dev, n)) for n in ESTADO)
        print(f"  {'ok  ' if ok else 'FALLO'} en desarrollo los datos siguen junto al programa")
        if err:
            print("        " + str(err)[:200])
        fallos += not ok
    finally:
        parar(p)

    # ── 2. Instalado: programa en una carpeta, datos en otra ────────────────
    app = tempfile.mkdtemp(prefix="signalos_app_")
    datos = tempfile.mkdtemp(prefix="signalos_data_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    p, err = arrancar(app, {"SIGNALOS_DATA": datos}, PORT + 1)
    try:
        if err:
            print(f"  FALLO el servidor no arranco con SIGNALOS_DATA: {str(err)[:200]}")
            fallos += 1
        else:
            ok = all(os.path.exists(os.path.join(datos, n)) for n in ESTADO)
            print(f"  {'ok  ' if ok else 'FALLO'} el estado se crea en la carpeta de datos")
            fallos += not ok

            # Y NO se crea nada nuevo junto al programa
            intrusos = [n for n in ("uploads", "screens.json", "content.json",
                                    "admin.json", "pin.json")
                        if os.path.exists(os.path.join(app, n))]
            ok = not intrusos
            print(f"  {'ok  ' if ok else 'FALLO'} no se escribe nada junto al programa"
                  + (f" (aparecio: {intrusos})" if intrusos else ""))
            fallos += not ok

            # El servidor sigue sirviendo los estaticos desde la carpeta del programa
            r = urllib.request.urlopen(f"http://127.0.0.1:{PORT+1}/player.html", timeout=5)
            ok = r.status == 200 and len(r.read()) > 1000
            print(f"  {'ok  ' if ok else 'FALLO'} los estaticos se sirven desde el programa")
            fallos += not ok
    finally:
        parar(p)

    # ── 3. La config instalada sirve de plantilla la primera vez ────────────
    app2 = tempfile.mkdtemp(prefix="signalos_app2_")
    datos2 = tempfile.mkdtemp(prefix="signalos_data2_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app2)
    json.dump({"port": 8123, "port_fallback": 9123, "mdns_name": "prueba"},
              open(os.path.join(app2, "config.json"), "w"))
    p, err = arrancar(app2, {"SIGNALOS_DATA": datos2}, PORT + 2)
    try:
        if err:
            print(f"  FALLO no arranco: {str(err)[:200]}")
            fallos += 1
        else:
            cfg = json.load(open(os.path.join(datos2, "config.json")))
            ok = cfg.get("mdns_name") == "prueba"
            print(f"  {'ok  ' if ok else 'FALLO'} la config del instalador se copia como plantilla"
                  f" (mdns_name={cfg.get('mdns_name')!r})")
            fallos += not ok
    finally:
        parar(p)

    # ── 4. Al actualizar no se pierden las pantallas ya configuradas ────────
    # Las versiones anteriores guardaban el estado junto al programa. Si al
    # actualizar no se trae, el cliente pierde sus pantallas y su contenido.
    app3 = tempfile.mkdtemp(prefix="signalos_app3_")
    datos3 = tempfile.mkdtemp(prefix="signalos_data3_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app3)
    json.dump({"TV-Salon": {"id": "TV-Salon", "connected": False, "last_seen": 1}},
              open(os.path.join(app3, "screens.json"), "w"))
    json.dump({"items": [{"id": "fx_1", "type": "fx", "title": "WU", "rows": []}],
               "screens": {"TV-Salon": {"mode": "independent", "playlist": []}}},
              open(os.path.join(app3, "content.json"), "w"))
    json.dump({"salt": "aa", "pwd_hash": "bb", "secret": "cc"},
              open(os.path.join(app3, "admin.json"), "w"))
    os.makedirs(os.path.join(app3, "uploads"), exist_ok=True)
    open(os.path.join(app3, "uploads", "logo.png"), "wb").write(b"PNG")

    p, err = arrancar(app3, {"SIGNALOS_DATA": datos3}, PORT + 3)
    try:
        if err:
            print(f"  FALLO no arranco: {str(err)[:200]}")
            fallos += 1
        else:
            scr = json.load(open(os.path.join(datos3, "screens.json")))
            ok = "TV-Salon" in scr
            print(f"  {'ok  ' if ok else 'FALLO'} al actualizar se conservan las pantallas configuradas")
            fallos += not ok

            cont = json.load(open(os.path.join(datos3, "content.json")))
            ok = len(cont.get("items", [])) == 1
            print(f"  {'ok  ' if ok else 'FALLO'} y el contenido de la libreria")
            fallos += not ok

            ok = os.path.exists(os.path.join(datos3, "admin.json"))
            print(f"  {'ok  ' if ok else 'FALLO'} y la contrasena, para no obligar a crearla de nuevo")
            fallos += not ok

            ok = os.path.exists(os.path.join(datos3, "uploads", "logo.png"))
            print(f"  {'ok  ' if ok else 'FALLO'} y los archivos subidos")
            fallos += not ok
    finally:
        parar(p)

    # ── 5. No pisar datos ya existentes ─────────────────────────────────────
    app4 = tempfile.mkdtemp(prefix="signalos_app4_")
    datos4 = tempfile.mkdtemp(prefix="signalos_data4_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app4)
    json.dump({"VIEJA": {}}, open(os.path.join(app4, "screens.json"), "w"))
    json.dump({"NUEVA": {}}, open(os.path.join(datos4, "screens.json"), "w"))
    p, err = arrancar(app4, {"SIGNALOS_DATA": datos4}, PORT + 4)
    try:
        if err:
            print(f"  FALLO no arranco: {str(err)[:200]}")
            fallos += 1
        else:
            scr = json.load(open(os.path.join(datos4, "screens.json")))
            ok = "NUEVA" in scr and "VIEJA" not in scr
            print(f"  {'ok  ' if ok else 'FALLO'} la migracion no pisa datos que ya existen")
            fallos += not ok
    finally:
        parar(p)

    # ── 6. Al cambiar el nombre del producto tampoco se pierde nada ─────────
    # Los datos vivian en ProgramData\SignalOS Pro y ahora van a
    # ProgramData\InTeks Display. Sin traerlos, renombrar el producto le
    # borraria al cliente sus pantallas y su contrasena.
    app5 = tempfile.mkdtemp(prefix="signalos_app5_")
    raiz5 = tempfile.mkdtemp(prefix="signalos_pd_")          # simula ProgramData
    viejo5 = os.path.join(raiz5, "SignalOS Pro")
    os.makedirs(os.path.join(viejo5, "uploads"), exist_ok=True)
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app5)
    json.dump({"TV-Viejo": {"id": "TV-Viejo", "connected": False, "last_seen": 1}},
              open(os.path.join(viejo5, "screens.json"), "w"))
    json.dump({"items": [{"id": "fx_9", "type": "fx", "title": "WU", "rows": []}], "screens": {}},
              open(os.path.join(viejo5, "content.json"), "w"))
    json.dump({"salt": "aa", "pwd_hash": "bb"}, open(os.path.join(viejo5, "admin.json"), "w"))
    open(os.path.join(viejo5, "uploads", "foto.png"), "wb").write(b"PNG")

    nuevo5 = os.path.join(raiz5, "InTeks Display")
    p, err = arrancar(app5, {"SIGNALOS_DATA": nuevo5}, PORT + 5)
    try:
        if err:
            print(f"  FALLO no arranco: {str(err)[:200]}")
            fallos += 1
        else:
            scr = json.load(open(os.path.join(nuevo5, "screens.json")))
            ok = "TV-Viejo" in scr
            print(f"  {'ok  ' if ok else 'FALLO'} al renombrar el producto se conservan las pantallas")
            fallos += not ok
            ok = os.path.exists(os.path.join(nuevo5, "admin.json"))
            print(f"  {'ok  ' if ok else 'FALLO'} y la contrasena")
            fallos += not ok
            ok = os.path.exists(os.path.join(nuevo5, "uploads", "foto.png"))
            print(f"  {'ok  ' if ok else 'FALLO'} y los archivos subidos")
            fallos += not ok
    finally:
        parar(p)

    # ── 7. En Program Files los datos se van a ProgramData aunque SE PUEDA ───
    #      escribir junto al programa.
    #
    # La prueba de escritura de pick_data_dir() se escribio pensando en un
    # proceso de usuario normal, que no puede escribir en Archivos de programa.
    # Pero el servidor arranca desde la tarea programada como SYSTEM, y SYSTEM
    # SI puede: la prueba pasa y los datos acaban dentro de Program Files, que
    # es justo donde el manual jura que no estan. Aqui no se mira si se puede
    # escribir, se mira DONDE esta instalado el programa.
    raiz6 = tempfile.mkdtemp(prefix="signalos_win_")
    pf6 = os.path.join(raiz6, "Program Files")
    app6 = os.path.join(pf6, "InTeks Display")
    pd6 = os.path.join(raiz6, "ProgramData")
    os.makedirs(app6, exist_ok=True)
    os.makedirs(pd6, exist_ok=True)
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app6)
    # Datos de una version anterior, ya escritos dentro de Program Files: son
    # los que hay hoy en el equipo de una tienda instalada.
    json.dump({"TV-Caja": {"id": "TV-Caja", "connected": False, "last_seen": 1}},
              open(os.path.join(app6, "screens.json"), "w"))
    json.dump({"salt": "aa", "pwd_hash": "bb"}, open(os.path.join(app6, "admin.json"), "w"))
    os.makedirs(os.path.join(app6, "uploads"), exist_ok=True)
    open(os.path.join(app6, "uploads", "cartel.png"), "wb").write(b"PNG")
    # Mientras los datos vivieron en Program Files, esta config.json no era la
    # plantilla del instalador: era la CONFIGURACION VIVA del cliente, con su
    # puerto, su nombre de instalacion y su token de Telegram. No viaja en
    # ESTADO, viaja por la via de la plantilla; si alguien la toca, una tienda
    # actualizada se queda sin avisos y sin saber por que.
    json.dump({"port": 8080, "installation_name": "Tienda Norte",
               "telegram_token": "12345:secreto"},
              open(os.path.join(app6, "config.json"), "w"))
    # La carpeta de datos ya existe y con un uploads vacio dentro: es el estado
    # real del equipo de desarrollo, y una migracion que mire la carpeta en vez
    # de los archivos se saltaria las imagenes.
    os.makedirs(os.path.join(pd6, "InTeks Display", "uploads"), exist_ok=True)

    # EN MAYUSCULAS a proposito: en Windows os.environ pone las claves en
    # mayusculas, asi que un {"ProgramFiles": ...} no reemplaza al heredado,
    # se suma. Llegarian las dos al hijo y ganaria la de verdad.
    entorno6 = {"PROGRAMFILES": pf6, "PROGRAMFILES(X86)": pf6,
                "PROGRAMW6432": pf6, "PROGRAMDATA": pd6}
    p, err = arrancar(app6, entorno6, PORT + 6)
    destino6 = os.path.join(pd6, "InTeks Display")
    try:
        if err:
            print(f"  FALLO no arranco: {str(err)[:200]}")
            fallos += 1
        else:
            ok = os.path.exists(os.path.join(destino6, "content.json"))
            print(f"  {'ok  ' if ok else 'FALLO'} instalado en Program Files, los datos van a ProgramData")
            fallos += not ok

            scr_path = os.path.join(destino6, "screens.json")
            ok = os.path.exists(scr_path) and "TV-Caja" in json.load(open(scr_path))
            print(f"  {'ok  ' if ok else 'FALLO'} y se traen las pantallas que ya estaban en Program Files")
            fallos += not ok

            ok = os.path.exists(os.path.join(destino6, "admin.json"))
            print(f"  {'ok  ' if ok else 'FALLO'} y la contrasena")
            fallos += not ok

            ok = os.path.exists(os.path.join(destino6, "uploads", "cartel.png"))
            print(f"  {'ok  ' if ok else 'FALLO'} y los archivos subidos, aunque el uploads de destino ya existiera")
            fallos += not ok

            cfg6 = json.load(open(os.path.join(destino6, "config.json")))
            ok = cfg6.get("telegram_token") == "12345:secreto" and \
                 cfg6.get("installation_name") == "Tienda Norte"
            print(f"  {'ok  ' if ok else 'FALLO'} y la configuracion viva: puerto, nombre y token de avisos")
            fallos += not ok
    finally:
        parar(p)

    # ── 8. Fuera de Program Files no cambia nada ────────────────────────────
    # El modo de desarrollo no puede depender de que exista o no un ProgramData.
    raiz7 = tempfile.mkdtemp(prefix="signalos_dev2_")
    dev7 = os.path.join(raiz7, "proyecto")
    pd7 = os.path.join(raiz7, "ProgramData")
    os.makedirs(dev7, exist_ok=True)
    os.makedirs(pd7, exist_ok=True)
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), dev7)
    pf7 = os.path.join(raiz7, "Program Files")
    p, err = arrancar(dev7, {"PROGRAMFILES": pf7, "PROGRAMFILES(X86)": pf7,
                             "PROGRAMW6432": pf7, "PROGRAMDATA": pd7}, PORT + 7)
    try:
        ok = err is None and os.path.exists(os.path.join(dev7, "content.json"))
        print(f"  {'ok  ' if ok else 'FALLO'} fuera de Program Files los datos siguen junto al programa")
        if err:
            print("        " + str(err)[:200])
        fallos += not ok
    finally:
        parar(p)

    for d in (dev, app, datos, app2, datos2, app3, datos3, app4, datos4, app5,
              raiz5, raiz6, raiz7):
        shutil.rmtree(d, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
