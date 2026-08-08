"""
El registro del servidor no puede crecer sin fin.

server.log se abria en modo "anadir" y nunca se recortaba. En el PC de una
tienda, encendido a diario durante anos, eso es un archivo que solo crece: con
un error que se repita en bucle puede comerse el disco, y justo entonces el
servidor deja de poder escribir nada.

Se guarda una sola vuelta anterior (server.log.1). Suficiente para mirar que
paso ayer, sin llenarle el disco a nadie.

Ejecutar:  python tests/test_log_rotacion.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8100
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def arrancar(app, datos, port):
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(port)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(base + "/api/auth-status", timeout=1)
            return p
        except Exception:
            pass
    p.terminate()
    return None


def main():
    app = tempfile.mkdtemp(prefix="signalos_log_")
    datos = tempfile.mkdtemp(prefix="signalos_logd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)

    lpath = os.path.join(datos, "server.log")
    anterior = lpath + ".1"

    try:
        # ── Un registro ya enorme se aparta al arrancar ─────────────────────
        marca = "ESTA-LINEA-VENIA-DE-ANTES"
        with open(lpath, "w", encoding="utf-8") as f:
            f.write(marca + "\n")
            f.write("relleno de un PC que lleva anos encendido\n" * 60000)
        tam_antes = os.path.getsize(lpath)
        check(tam_antes > 2 * 1024 * 1024, f"el registro de partida es grande -> {tam_antes} bytes")

        p = arrancar(app, datos, PORT)
        if not p:
            print("FALLO: el servidor no arranco")
            return 1
        try:
            check(os.path.exists(anterior), "el registro viejo se aparta a server.log.1")
            check(os.path.getsize(lpath) < 100 * 1024,
                  f"y el nuevo empieza pequeno -> {os.path.getsize(lpath)} bytes")
            check(marca in open(anterior, encoding="utf-8", errors="replace").read(1000),
                  "lo apartado se conserva entero, no se tira")
            check("INTEKS DISPLAY" in open(lpath, encoding="utf-8", errors="replace").read(),
                  "y el arranque nuevo si queda registrado")
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

        # ── Solo se guarda UNA vuelta anterior ─────────────────────────────
        # Si se acumularan, el problema seria el mismo pero con mas archivos.
        with open(anterior, "w", encoding="utf-8") as f:
            f.write("VUELTA-VIEJA-QUE-DEBE-DESAPARECER\n")
        with open(lpath, "w", encoding="utf-8") as f:
            f.write("segunda vuelta\n" * 200000)

        p = arrancar(app, datos, PORT + 1)
        if not p:
            print("FALLO: el servidor no arranco la segunda vez")
            return 1
        try:
            check(not os.path.exists(lpath + ".2"),
                  "no se van acumulando vueltas (.2, .3, ...)")
            check("VUELTA-VIEJA-QUE-DEBE-DESAPARECER"
                  not in open(anterior, encoding="utf-8", errors="replace").read(1000),
                  "la vuelta anterior se sustituye por la ultima")
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

        # ── Un registro pequeno se deja en paz ─────────────────────────────
        shutil.rmtree(datos, ignore_errors=True)
        os.makedirs(datos, exist_ok=True)
        with open(lpath, "w", encoding="utf-8") as f:
            f.write("apenas cuatro lineas\n")
        p = arrancar(app, datos, PORT + 2)
        if not p:
            print("FALLO: el servidor no arranco la tercera vez")
            return 1
        try:
            check(not os.path.exists(anterior),
                  "un registro pequeno no se aparta")
            check("apenas cuatro lineas" in open(lpath, encoding="utf-8", errors="replace").read(),
                  "y lo que ya habia sigue ahi")
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
    finally:
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
