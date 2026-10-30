"""
/api/delete debe borrar el archivo de uploads/ aunque el servidor se haya
arrancado con otro directorio de trabajo (como el servicio instalado: los datos
viven en ProgramData y el cwd es la carpeta del programa).

Ejecutar:
    py tests/test_borrar_archivo.py
"""
import http.client, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8119
TOKEN = "token-de-pruebas-0123456789"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def peticion(metodo, ruta, cuerpo=None, cabeceras=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    h = {"X-SignalOS-Token": TOKEN, **(cabeceras or {})}
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
    work = tempfile.mkdtemp(prefix="signalos_del_")
    otro_cwd = tempfile.mkdtemp(prefix="signalos_cwd_")
    proc = None
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        up = os.path.join(work, "uploads")
        # cwd distinto de donde viven los datos: así falla el borrado relativo.
        proc = subprocess.Popen([sys.executable, os.path.join(work, "server.py"), "--port", str(PORT)],
                                cwd=otro_cwd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/auth-status", timeout=1); break
            except Exception: pass

        cod, r = peticion("POST", "/api/upload-raw?name=borrame.png", PNG,
                          {"Content-Type": "application/octet-stream"})
        item = r.get("item", {})
        fallos += comprobar("subida correcta en uploads/ de los datos",
                            cod == 200 and os.path.isfile(os.path.join(up, item.get("id", "x"))), f"{cod} {r}")
        cod, r = peticion("POST", "/api/delete", json.dumps({"id": item.get("id")}).encode(),
                          {"Content-Type": "application/json"})
        fallos += comprobar("delete -> 200", cod == 200, f"{cod} {r}")
        fallos += comprobar("el archivo desaparece de uploads/",
                            not os.path.exists(os.path.join(up, item.get("id", "x"))))
        _, contenido = peticion("GET", "/api/content")
        fallos += comprobar("y sale de la Librería",
                            not any(i["id"] == item.get("id") for i in contenido.get("items", [])))
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(otro_cwd, ignore_errors=True)
    print("OK test_borrar_archivo" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
