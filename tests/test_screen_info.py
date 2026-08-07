"""
Comprueba que POST /api/screen-info guarda la geometría en screens.json.

Arranca el servidor en un directorio temporal para no tocar los datos reales.
Ejecutar:  python tests/test_screen_info.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8096


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(req, timeout=5))


def main():
    work = tempfile.mkdtemp(prefix="signalos_screeninfo_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)

    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
    screens_path = os.path.join(work, "screens.json")
    failed = 0
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

        # El endpoint es publico (las pantallas no tienen sesion), asi que NO
        # debe poder crear entradas: solo actualizar las ya registradas.
        try:
            post(base + "/api/screen-info",
                 {"screen": "Fantasma", "w": 1920, "h": 1080, "dpr": 1})
            print("  FALLO una pantalla no registrada no deberia crearse")
            failed += 1
        except urllib.error.HTTPError as e:
            # screens.json ya existe (init_file lo crea vacio al arrancar); lo
            # que importa es que la pantalla inventada no haya entrado.
            existentes = json.load(open(screens_path)) if os.path.exists(screens_path) else {}
            ok = e.code == 404 and "Fantasma" not in existentes
            print(f"  {'ok  ' if ok else 'FALLO'} pantalla desconocida -> {e.code}, sin crear entrada")
            failed += not ok

        # Registrar dos pantallas como lo haria el SSE al conectarse
        json.dump({"TV": {"id": "TV", "connected": True, "last_seen": time.time()},
                   "Tablet": {"id": "Tablet", "connected": True, "last_seen": time.time()}},
                  open(screens_path, "w"))

        # Pantalla horizontal
        post(base + "/api/screen-info",
             {"screen": "TV", "w": 1920, "h": 1080, "dpr": 1})
        v = json.load(open(screens_path))["TV"]["viewport"]
        ok = v["w"] == 1920 and v["h"] == 1080 and v["orientation"] == "landscape"
        print(f"  {'ok  ' if ok else 'FALLO'} horizontal -> {v}")
        failed += not ok

        # Pantalla vertical
        post(base + "/api/screen-info",
             {"screen": "Tablet", "w": 800, "h": 1280, "dpr": 2})
        v = json.load(open(screens_path))["Tablet"]["viewport"]
        ok = v["orientation"] == "portrait" and v["dpr"] == 2
        print(f"  {'ok  ' if ok else 'FALLO'} vertical   -> {v}")
        failed += not ok

        # Sin identificador de pantalla -> 400, y sin crear entradas basura
        try:
            post(base + "/api/screen-info", {"w": 100, "h": 100})
            print("  FALLO sin screen deberia dar 400")
            failed += 1
        except urllib.error.HTTPError as e:
            ok = e.code == 400
            print(f"  {'ok  ' if ok else 'FALLO'} sin screen -> {e.code}")
            failed += not ok

        # Reportar dos veces actualiza en vez de duplicar
        post(base + "/api/screen-info",
             {"screen": "TV", "w": 1280, "h": 720, "dpr": 1})
        screens = json.load(open(screens_path))
        ok = screens["TV"]["viewport"]["w"] == 1280 and len(screens) == 2
        print(f"  {'ok  ' if ok else 'FALLO'} actualiza sin duplicar ({len(screens)} pantallas)")
        failed += not ok
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)

    print("TODO OK" if failed == 0 else f"{failed} FALLO(S)")
    return 1 if failed else 0


sys.exit(main())
