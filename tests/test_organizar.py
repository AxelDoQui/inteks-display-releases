"""
Carpetas y etiquetas, parte servidor: POST /api/organize.

Ejecutar:
    py tests/test_organizar.py
"""
import http.client, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8126
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


def organizar(cuerpo, con_token=True):
    return peticion("POST", "/api/organize", json.dumps(cuerpo).encode(), JSON, con_token)


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def item(c, iid): return next(i for i in c["items"] if i["id"] == iid)


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_organizar_")
    proc = None
    A, B, C, D = "0001_a.png", "0002_b.png", "0003_c.png", "0004_d.png"
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        up = os.path.join(work, "uploads"); os.makedirs(up, exist_ok=True)
        for n in (A, B, C, D): open(os.path.join(up, n), "wb").write(PNG)
        json.dump({"items": [
            {"id": A, "type": "image", "name": "a.png", "src": "/uploads/" + A},
            {"id": B, "type": "image", "name": "b.png", "src": "/uploads/" + B},
            {"id": C, "type": "image", "name": "c.png", "src": "/uploads/" + C},
            {"id": D, "type": "image", "name": "d.png", "src": "/uploads/" + D,
             "folder": "Verano", "tags": ["Oferta"]}],
          "screens": {}, "rev": 0}, open(os.path.join(work, "content.json"), "w"))
        json.dump({}, open(os.path.join(work, "screens.json"), "w"))
        proc = subprocess.Popen([sys.executable, os.path.join(work, "server.py"), "--port", str(PORT)],
                                cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/auth-status", timeout=1); break
            except Exception: pass

        def contenido(): return peticion("GET", "/api/content")[1]

        # 1. carpeta a varios
        cod, r = organizar({"ids": [A, B], "folder": "Tienda"})
        c = contenido()
        fallos += comprobar("carpeta a dos -> changed 2", cod == 200 and r.get("ok") is True and r.get("changed") == 2, f"{cod} {r}")
        fallos += comprobar("A y B en Tienda", item(c, A).get("folder") == "Tienda" and item(c, B).get("folder") == "Tienda")
        # 2. etiquetas y no duplicar
        cod, r = organizar({"ids": [A], "addTags": ["rebajas", "Nuevo"]})
        c = contenido()
        fallos += comprobar("addTags A", cod == 200 and r.get("changed") == 1 and item(c, A).get("tags") == ["rebajas", "Nuevo"], f"{r} {item(c, A).get('tags')}")
        rev0 = c["rev"]
        cod, r = organizar({"ids": [A], "addTags": ["REBAJAS"]})
        c = contenido()
        fallos += comprobar("REBAJAS no duplica, changed 0, rev igual",
                            cod == 200 and r.get("changed") == 0 and item(c, A)["tags"] == ["rebajas", "Nuevo"] and c["rev"] == rev0, f"{r}")
        # 3. equivalencia
        cod, r = organizar({"ids": [B], "folder": "verano", "addTags": ["oferta"]})
        c = contenido()
        fallos += comprobar("reutiliza Verano y Oferta",
                            item(c, B).get("folder") == "Verano" and item(c, B).get("tags") == ["Oferta"], str(item(c, B)))
        cod, r = organizar({"ids": [C], "folder": "  VERANO  "})
        fallos += comprobar("recorta y reutiliza", item(contenido(), C).get("folder") == "Verano")
        organizar({"ids": [C], "folder": "Épica"})
        organizar({"ids": [A], "folder": "epica"})
        fallos += comprobar("equivalencia sin acentos", item(contenido(), A).get("folder") == "Épica")
        # 4. folder null
        cod, r = organizar({"ids": [C], "folder": None})
        c = contenido()
        fallos += comprobar("folder null quita la clave", cod == 200 and r.get("changed") == 1 and "folder" not in item(c, C), str(item(c, C)))
        # 5. removeTags
        cod, r = organizar({"ids": [A], "removeTags": ["nuevo"]})
        c = contenido()
        fallos += comprobar("removeTags sin mayúsculas", cod == 200 and r.get("changed") == 1 and item(c, A).get("tags") == ["rebajas"], str(item(c, A).get("tags")))
        # 6. no-cambio
        rev0 = contenido()["rev"]
        cod, r = organizar({"ids": [B], "folder": "Verano"})
        fallos += comprobar("misma carpeta -> changed 0 y rev igual", cod == 200 and r.get("changed") == 0 and contenido()["rev"] == rev0, str(r))
        # 7. id inexistente
        antes = contenido()
        cod, r = organizar({"ids": [A, "nope"], "folder": "Otra"})
        fallos += comprobar("id inexistente -> 404", cod == 404 and r.get("error") == "No existe el archivo nope", f"{cod} {r}")
        fallos += comprobar("404 no toca nada ni rev", contenido() == antes)
        # 8. 400
        for etiqueta, cuerpo in [
            ("carpeta 41", {"ids": [A], "folder": "x" * 41}),
            ("carpeta vacía", {"ids": [A], "folder": "   "}),
            ("etiqueta 31", {"ids": [A], "addTags": ["x" * 31]}),
            ("11 etiquetas", {"ids": [A], "addTags": [f"t{i}" for i in range(11)]}),
            ("ids vacío", {"ids": [], "folder": "X"}),
            ("sin acción", {"ids": [A]}),
            ("folder 5", {"ids": [A], "folder": 5}),
            ("201 ids", {"ids": [f"x{i}" for i in range(201)], "folder": "X"}),
        ]:
            cod, r = organizar(cuerpo)
            fallos += comprobar(etiqueta + " -> 400", cod == 400 and r.get("ok") is False, f"{cod} {r}")
        fallos += comprobar("los 400 no suben rev ni modifican", contenido() == antes)
        # más de 10 acumuladas
        organizar({"ids": [C], "addTags": [f"u{i}" for i in range(8)]})
        antes = contenido()
        cod, r = organizar({"ids": [C], "addTags": ["v1", "v2", "v3"]})
        fallos += comprobar("acumular >10 -> 400 sin tocar",
                            cod == 400 and r.get("error") == "Máximo 10 etiquetas por archivo" and contenido() == antes, f"{cod} {r}")
        # 9. sin token
        cod, _ = organizar({"ids": [A], "folder": "X"}, con_token=False)
        fallos += comprobar("sin token -> 401", cod == 401, str(cod))
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_organizar" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
