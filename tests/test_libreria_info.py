"""
Librería más útil, parte servidor: /api/library-info (tamaño, fecha y usos),
/api/rename (solo cambia el nombre visible) y /api/delete (limpia también
los paquetes).

Ejecutar:
    py tests/test_libreria_info.py
"""
import http.client, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8121
TOKEN = "token-de-pruebas-0123456789"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def peticion(metodo, ruta, cuerpo=None, cabeceras=None, con_token=True):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    h = {**({"X-SignalOS-Token": TOKEN} if con_token else {}), **(cabeceras or {})}
    c.request(metodo, ruta, body=cuerpo, headers=h)
    r = c.getresponse(); datos = r.read(); c.close()
    try: return r.status, json.loads(datos or b"{}")
    except ValueError: return r.status, {}


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_lib_")
    proc = None
    JSON = {"Content-Type": "application/json"}
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        up = os.path.join(work, "uploads"); os.makedirs(up, exist_ok=True)
        open(os.path.join(up, "0001_a.png"), "wb").write(PNG)
        open(os.path.join(up, "0002_b.png"), "wb").write(PNG + b"\x00" * 100)
        json.dump({"items": [
            {"id": "0001_a.png", "type": "image", "name": "a.png", "src": "/uploads/0001_a.png"},
            {"id": "0002_b.png", "type": "image", "name": "b.png", "src": "/uploads/0002_b.png"},
            {"id": "fx1", "type": "fx", "name": "Divisas"}],
          "screens": {"s1": {"mode": "independent", "playlist": [{"id": "0001_a.png", "duration": 10}]}},
          "packages": [{"id": "p1", "name": "Escaparate", "itemIds": ["0001_a.png", "fx1"]}],
          "rev": 0}, open(os.path.join(work, "content.json"), "w"))
        json.dump({"s1": {"name": "Tienda Centro"}}, open(os.path.join(work, "screens.json"), "w"))
        proc = subprocess.Popen([sys.executable, os.path.join(work, "server.py"), "--port", str(PORT)],
                                cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/auth-status", timeout=1); break
            except Exception: pass

        # 1. tamaño y fecha
        cod, info = peticion("GET", "/api/library-info")
        fallos += comprobar("library-info -> 200", cod == 200, f"{cod}")
        fallos += comprobar("tamaño de a", info.get("0001_a.png", {}).get("size") == len(PNG), str(info))
        fallos += comprobar("tamaño de b", info.get("0002_b.png", {}).get("size") == len(PNG) + 100)
        cr = info.get("0001_a.png", {}).get("created")
        fallos += comprobar("created es int > 0", isinstance(cr, int) and cr > 0, str(cr))
        fallos += comprobar("fx1 sin size", "size" not in info.get("fx1", {"size": 1}))
        # 2. usos
        usos_a = info.get("0001_a.png", {}).get("uses", [])
        fallos += comprobar("uso en pantalla",
                            {"kind": "screen", "id": "s1", "name": "Tienda Centro"} in usos_a, str(usos_a))
        fallos += comprobar("uso en paquete",
                            {"kind": "package", "id": "p1", "name": "Escaparate"} in usos_a, str(usos_a))
        fallos += comprobar("b sin usos", info.get("0002_b.png", {}).get("uses") == [])
        # 3. sin token
        cod, _ = peticion("GET", "/api/library-info", con_token=False)
        fallos += comprobar("sin token -> 401", cod == 401, f"{cod}")
        # 4. renombrar
        cod, r = peticion("POST", "/api/rename", json.dumps({"id": "0002_b.png", "name": "  Cartel nuevo  "}).encode(), JSON)
        fallos += comprobar("rename -> 200", cod == 200, f"{cod} {r}")
        _, cont = peticion("GET", "/api/content")
        b = next((i for i in cont.get("items", []) if i["id"] == "0002_b.png"), {})
        fallos += comprobar("nombre recortado y guardado", b.get("name") == "Cartel nuevo", str(b))
        fallos += comprobar("el archivo sigue en uploads/", os.path.isfile(os.path.join(up, "0002_b.png")))
        # 5. errores
        cod, _ = peticion("POST", "/api/rename", json.dumps({"id": "0002_b.png", "name": "   "}).encode(), JSON)
        fallos += comprobar("nombre vacío -> 400", cod == 400, f"{cod}")
        cod, _ = peticion("POST", "/api/rename", json.dumps({"id": "0002_b.png", "name": "x" * 121}).encode(), JSON)
        fallos += comprobar("121 caracteres -> 400", cod == 400, f"{cod}")
        cod, _ = peticion("POST", "/api/rename", json.dumps({"id": "nope", "name": "x"}).encode(), JSON)
        fallos += comprobar("id inexistente -> 404", cod == 404, f"{cod}")
        # 6. borrar limpia playlists y paquetes
        cod, r = peticion("POST", "/api/delete", json.dumps({"id": "0001_a.png"}).encode(), JSON)
        fallos += comprobar("delete -> 200", cod == 200, f"{cod} {r}")
        _, cont = peticion("GET", "/api/content")
        fallos += comprobar("playlist de s1 vacía", cont["screens"]["s1"]["playlist"] == [], str(cont.get("screens")))
        fallos += comprobar("paquete sin el id", cont["packages"][0]["itemIds"] == ["fx1"], str(cont.get("packages")))
        fallos += comprobar("archivo borrado de uploads/", not os.path.exists(os.path.join(up, "0001_a.png")))
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_libreria_info" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
