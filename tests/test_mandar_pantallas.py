"""
Mandar a pantallas, parte servidor: POST /api/send-to-screens.

Ejecutar:
    py tests/test_mandar_pantallas.py
"""
import http.client, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8124
TOKEN = "token-de-pruebas-0123456789"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JSON = {"Content-Type": "application/json"}


def peticion(metodo, ruta, cuerpo=None, cabeceras=None, con_token=True):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    h = {**({"X-SignalOS-Token": TOKEN} if con_token else {}), **(cabeceras or {})}
    c.request(metodo, ruta, body=cuerpo, headers=h)
    r = c.getresponse(); datos = r.read(); c.close()
    try: return r.status, json.loads(datos or b"{}")
    except ValueError: return r.status, {}


def enviar(cuerpo, con_token=True):
    return peticion("POST", "/api/send-to-screens", json.dumps(cuerpo).encode(), JSON, con_token)


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def ids(pl): return [p.get("id") for p in pl]


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_mandar_")
    proc = None
    A, B, V = "0001_a.png", "0002_b.png", "0003_v.mp4"
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        up = os.path.join(work, "uploads"); os.makedirs(up, exist_ok=True)
        for n in (A, B, V): open(os.path.join(up, n), "wb").write(PNG)
        json.dump({"items": [
            {"id": A, "type": "image", "name": "a.png", "src": "/uploads/" + A},
            {"id": B, "type": "image", "name": "b.png", "src": "/uploads/" + B},
            {"id": V, "type": "video", "name": "v.mp4", "src": "/uploads/" + V}],
          "screens": {"s1": {"mode": "independent", "playlist": [{"id": A, "duration": 10}]}},
          "rev": 0}, open(os.path.join(work, "content.json"), "w"))
        json.dump({"s1": {"name": "Centro"}, "s2": {"name": "Norte"}, "s3": {"name": "Sur"}},
                  open(os.path.join(work, "screens.json"), "w"))
        proc = subprocess.Popen([sys.executable, os.path.join(work, "server.py"), "--port", str(PORT)],
                                cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/auth-status", timeout=1); break
            except Exception: pass

        # 1. envío normal
        cod, r = enviar({"ids": [A, B], "screens": ["s1", "s2"]})
        fallos += comprobar("envío -> 200", cod == 200, f"{cod} {r}")
        fallos += comprobar("added 3 skipped 1", r.get("added") == 3 and r.get("skipped") == 1, str(r))
        _, c = peticion("GET", "/api/content")
        p1, p2 = c["screens"]["s1"]["playlist"], c["screens"]["s2"]["playlist"]
        fallos += comprobar("s1: A una vez y B al final", ids(p1) == [A, B], str(ids(p1)))
        fallos += comprobar("s2 == [A,B]", ids(p2) == [A, B], str(ids(p2)))
        fallos += comprobar("duración 8 y copia del item",
                            all(p.get("duration") == 8 for p in p2)
                            and p2[0].get("name") == "a.png" and p2[0].get("src") == "/uploads/" + A
                            and p2[0].get("type") == "image", str(p2))
        # 2. duración
        cod, r = enviar({"ids": [V], "screens": ["s2"], "duration": 15})
        _, c = peticion("GET", "/api/content")
        nueva = [p for p in c["screens"]["s2"]["playlist"] if p["id"] == V]
        fallos += comprobar("duration 15", cod == 200 and len(nueva) == 1 and nueva[0]["duration"] == 15, str(nueva))
        # 3. pantalla sin entrada en content
        fallos += comprobar("s3 sin entrada antes", "s3" not in c["screens"])
        cod, r = enviar({"ids": [A], "screens": ["s3"]})
        _, c = peticion("GET", "/api/content")
        fallos += comprobar("s3 creada independent",
                            cod == 200 and c["screens"].get("s3", {}).get("mode") == "independent"
                            and ids(c["screens"]["s3"]["playlist"]) == [A], str(c["screens"].get("s3")))
        # 4. repetir
        cod, r = enviar({"ids": [A, B], "screens": ["s1", "s2"]})
        fallos += comprobar("repetido added 0", cod == 200 and r.get("added") == 0 and r.get("skipped") == 4, str(r))
        # 5/6. inexistentes sin subir rev
        _, antes = peticion("GET", "/api/content")
        cod, r = enviar({"ids": [A], "screens": ["s1", "zz"]})
        _, despues = peticion("GET", "/api/content")
        fallos += comprobar("pantalla inexistente -> 404", cod == 404 and r.get("error") == "No existe la pantalla zz", f"{cod} {r}")
        fallos += comprobar("404 pantalla no sube rev", antes["rev"] == despues["rev"])
        cod, r = enviar({"ids": [B, "nope"], "screens": ["s3"]})
        _, despues = peticion("GET", "/api/content")
        fallos += comprobar("id inexistente -> 404", cod == 404 and r.get("error") == "No existe el archivo nope", f"{cod} {r}")
        fallos += comprobar("404 id no sube rev y no guarda",
                            antes["rev"] == despues["rev"] and ids(despues["screens"]["s3"]["playlist"]) == [A])
        # 7. 400
        for etiqueta, cuerpo in [
            ("ids vacío", {"ids": [], "screens": ["s1"]}),
            ("screens vacío", {"ids": [A], "screens": []}),
            ("screens cadena", {"ids": [A], "screens": "s1"}),
            ("201 ids", {"ids": [f"x{i}" for i in range(201)], "screens": ["s1"]}),
            ("101 pantallas", {"ids": [A], "screens": [f"p{i}" for i in range(101)]}),
            ("duración 0", {"ids": [A], "screens": ["s1"], "duration": 0}),
            ("duración 'x'", {"ids": [A], "screens": ["s1"], "duration": "x"}),
            ("duración 3601", {"ids": [A], "screens": ["s1"], "duration": 3601}),
        ]:
            cod, _ = enviar(cuerpo)
            fallos += comprobar(etiqueta + " -> 400", cod == 400, str(cod))
        _, fin = peticion("GET", "/api/content")
        fallos += comprobar("los 400 no suben rev", fin["rev"] == antes["rev"])
        # 8. sin token
        cod, _ = enviar({"ids": [A], "screens": ["s1"]}, con_token=False)
        fallos += comprobar("sin token -> 401", cod == 401, str(cod))
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_mandar_pantallas" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
