"""
Videowall: las imágenes del tamaño de UNA pantalla van en parejas (la 1.ª a la pantalla izquierda,
la 2.ª a la derecha); lo que sobra sale entero en todas; las del tamaño del muro no se juntan.

Ejecutar:  py tests/test_wall_parejas.py
"""
import json, os, shutil, struct, subprocess, sys, tempfile, time, urllib.request, zlib

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8142
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html", "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def png(ruta, w, h):
    def trozo(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    crudo = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    open(ruta, "wb").write(b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + trozo(b"IDAT", zlib.compress(crudo)) + trozo(b"IEND", b""))


def main():
    app = tempfile.mkdtemp(prefix="signalos_par_"); datos = tempfile.mkdtemp(prefix="signalos_pard_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    up = os.path.join(datos, "uploads"); os.makedirs(up)
    for n, (w, h) in {"a.png": (160, 90), "b.png": (160, 90), "c.png": (160, 90), "muro.png": (320, 90)}.items():
        png(os.path.join(up, n), w, h)
    json.dump({"api_token": "t", "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    im = lambda i, n: {"id": i, "type": "image", "name": n, "src": "/uploads/" + n, "duration": 5}
    lista = [im("a", "a.png"), im("b", "b.png"), im("m", "muro.png"), im("c", "c.png")]
    json.dump({"rev": 1, "items": [], "screens": {
        "L": {"mode": "wall", "wall_ids": ["L", "R"], "wall_pos": "left", "partner": "R", "playlist": lista},
        "R": {"mode": "wall", "wall_ids": ["L", "R"], "wall_pos": "right", "partner": "L", "playlist": []}}},
        open(os.path.join(datos, "content.json"), "w"))
    json.dump({n: {"name": n, "connected": True} for n in "LR"}, open(os.path.join(datos, "screens.json"), "w"))
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app,
                         env=dict(os.environ, SIGNALOS_DATA=datos), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/player.html"); break
            except Exception: time.sleep(0.2)
        pl = lambda s: json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/playlist?screen={s}"))["playlist"]
        izq, der = pl("L"), pl("R")
        check([i["id"] for i in izq] == ["a", "m", "c"], f"izquierda: pareja a+b, la del muro y la suelta ({[i['id'] for i in izq]})")
        check([i["id"] for i in der] == ["a", "m", "c"], "derecha: mismos ids, para sincronizarse")
        check(izq[0]["src"].endswith("a.png") and der[0]["src"].endswith("b.png"), "la pareja: a a la izquierda y b a la derecha")
        check(izq[1]["src"].endswith("muro.png") and der[1]["src"].endswith("muro.png"), "la del tamaño del muro no se junta")
        check(izq[2]["src"].endswith("c.png") and der[2]["src"].endswith("c.png"), "la suelta sale entera en las dos")
    finally:
        p.terminate()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


main()
