"""
«Ahora en pantalla»: el panel ve qué está reproduciendo cada pantalla.

El reproductor avisa (POST /api/screen-now, público como el resto de lo que hacen
las pantallas sin sesión) cada vez que cambia de diapositiva. El servidor lo
guarda SOLO en memoria: escribir en disco en cada cambio de diapositiva, en cada
tienda, sería gastar el disco por un dato que no vale la pena conservar.

Ejecutar:
    python tests/test_pantalla_ahora.py
"""
import json, os, shutil, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8117
TOKEN = "token-de-pruebas-0123456789"
BASE = f"http://127.0.0.1:{PORT}"


def llamar(path, payload=None, token=None):
    cab = {"Content-Type": "application/json"}
    if token: cab["X-SignalOS-Token"] = token
    req = urllib.request.Request(BASE + path, headers=cab, method="POST" if payload is not None else "GET",
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or "{}")
        except ValueError: return e.code, {}


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_now_")
    proc = None
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        json.dump({"TV": {"id": "TV", "connected": True, "last_seen": time.time()}},
                  open(os.path.join(work, "screens.json"), "w"))
        proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=work,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(BASE + "/api/auth-status", timeout=1); break
            except Exception: pass
        antes = open(os.path.join(work, "screens.json")).read()

        cod, _ = llamar("/api/screen-now", {"screen": "TV", "id": "0001_oferta.png", "name": "Oferta de otoño", "type": "image"})
        fallos += comprobar("una pantalla avisa sin sesion -> 200", cod == 200, str(cod))

        cod, pantallas = llamar("/api/screens", token=TOKEN)
        ahora = (pantallas.get("TV") or {}).get("now") or {}
        fallos += comprobar("el panel ve lo que reproduce", ahora.get("name") == "Oferta de otoño" and ahora.get("type") == "image", str(ahora))
        fallos += comprobar("con la hora del aviso", abs((ahora.get("at") or 0) - time.time()) < 10)

        cod, _ = llamar("/api/screens")
        fallos += comprobar("sin sesion no se ve nada -> 401", cod == 401, str(cod))

        fallos += comprobar("no se escribe en disco", open(os.path.join(work, "screens.json")).read() == antes)

        cod, _ = llamar("/api/screen-now", {"screen": "NoExiste", "name": "x"})
        fallos += comprobar("pantalla desconocida -> 404", cod == 404, str(cod))
        _, pantallas = llamar("/api/screens", token=TOKEN)
        fallos += comprobar("y no aparece", "NoExiste" not in pantallas)

        llamar("/api/screen-now", {"screen": "TV", "name": "x" * 500, "type": ["raro"], "id": 7})
        _, pantallas = llamar("/api/screens", token=TOKEN)
        ahora = pantallas["TV"]["now"]
        fallos += comprobar("un nombre enorme se recorta", len(ahora["name"]) <= 80, str(len(ahora["name"])))
        fallos += comprobar("tipos raros no rompen nada", isinstance(ahora["type"], str) and isinstance(ahora["id"], str))

        cod, _ = llamar("/api/screen-now", ["no", "es", "un", "objeto"])
        fallos += comprobar("cuerpo que no es un objeto -> 400", cod == 400, str(cod))
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_pantalla_ahora" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
