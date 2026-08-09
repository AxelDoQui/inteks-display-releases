"""
Espacio en disco.

Nada lo vigilaba. Cuando el disco de la tienda se llena fallan las subidas
y -peor- puede fallar la escritura de content.json y quedarse la
configuracion a medias. Es un desastre silencioso: no hay ningun sintoma
hasta que ya paso.

Ejecutar:  python tests/test_disco.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8104
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_disk_")
    datos = tempfile.mkdtemp(prefix="signalos_diskd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
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

        info = json.load(urllib.request.urlopen(base + "/api/info", timeout=5))
        d = info.get("disk") or {}
        check(isinstance(d.get("libre_mb"), (int, float)) and d["libre_mb"] > 0,
              f"informa del espacio libre -> {d.get('libre_mb')} MB")
        check(isinstance(d.get("total_mb"), (int, float)) and d["total_mb"] >= d.get("libre_mb", 0),
              "y del total, que no puede ser menor que el libre")
        check(0 <= d.get("pct_usado", -1) <= 100,
              f"el porcentaje usado esta entre 0 y 100 -> {d.get('pct_usado')}")
        check(d.get("aviso") in (True, False),
              "dice si hay que avisar o no")
        # En la maquina de pruebas hay sitio de sobra; el aviso debe estar apagado.
        check(d.get("aviso") is False or d.get("pct_usado", 0) >= 90,
              "no avisa si hay espacio de sobra")
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
