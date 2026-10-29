"""
Subida en bruto: POST /api/upload-raw.

El archivo llega como cuerpo, se escribe a disco por trozos en un .part y solo
se renombra al validar. Una subida rechazada o cortada no deja nada.

Ejecutar:
    python tests/test_subida_raw.py
"""
import hashlib, http.client, json, os, shutil, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8118
TOKEN = "token-de-pruebas-0123456789"
MAX_MB = 40

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def peticion(metodo, ruta, cuerpo=None, token=TOKEN, cabeceras=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    h = dict(cabeceras or {})
    if token: h["X-SignalOS-Token"] = token
    c.request(metodo, ruta, body=cuerpo, headers=h)
    r = c.getresponse()
    datos = r.read()
    c.close()
    try: return r.status, json.loads(datos or b"{}")
    except ValueError: return r.status, {}


def subir(nombre, datos, token=TOKEN):
    from urllib.parse import quote
    return peticion("POST", "/api/upload-raw?name=" + quote(nombre), datos, token,
                    {"Content-Type": "application/octet-stream"})


def a_medias(nombre, declarar, enviar):
    """Declara `declarar` bytes, manda `enviar` y cierra el socket."""
    from urllib.parse import quote
    s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
    s.sendall((f"POST /api/upload-raw?name={quote(nombre)} HTTP/1.1\r\nHost: x\r\n"
               f"X-SignalOS-Token: {TOKEN}\r\nContent-Type: application/octet-stream\r\n"
               f"Content-Length: {declarar}\r\n\r\n").encode() + enviar)
    s.close()


def declarar_de_mas(nombre, declarar):
    """Declara un tamaño y NO manda cuerpo: el servidor debe rechazar por la cabecera."""
    from urllib.parse import quote
    s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
    s.sendall((f"POST /api/upload-raw?name={quote(nombre)} HTTP/1.1\r\nHost: x\r\n"
               f"X-SignalOS-Token: {TOKEN}\r\nContent-Type: application/octet-stream\r\n"
               f"Content-Length: {declarar}\r\n\r\n").encode())
    s.settimeout(10)
    resp = s.recv(4096).decode("latin-1")
    s.close()
    return int(resp.split(" ", 2)[1])


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_raw_")
    proc = None
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html",
                  "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        cfg = json.load(open(os.path.join(work, "config.json")))
        cfg["upload_max_mb"] = MAX_MB
        json.dump(cfg, open(os.path.join(work, "config.json"), "w"))
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        up = os.path.join(work, "uploads")
        os.makedirs(up, exist_ok=True)
        open(os.path.join(up, "9999_huerfano.mp4.part"), "wb").write(b"resto de una subida vieja")
        proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=work,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/auth-status", timeout=1); break
            except Exception: pass

        fallos += comprobar("al arrancar se limpia el .part huérfano",
                            not os.path.exists(os.path.join(up, "9999_huerfano.mp4.part")))

        cod, r = subir("logo.png", PNG)
        fallos += comprobar("PNG correcto -> 200 y tipo image",
                            cod == 200 and r.get("item", {}).get("type") == "image", f"{cod} {r}")
        item = r.get("item", {})
        fallos += comprobar("el archivo existe con su tamaño",
                            os.path.getsize(os.path.join(up, item.get("id", "x"))) == len(PNG))
        _, contenido = peticion("GET", "/api/content")
        fallos += comprobar("queda en la Librería", any(i["id"] == item.get("id") for i in contenido.get("items", [])))
        fallos += comprobar("un nombre normal no se toca", item.get("name") == "logo.png", str(item.get("name")))

        # Nombres que Windows no admite: se limpian en vez de dar 500.
        prohibidos = set('<>:"/\\|?*') | {chr(i) for i in range(32)}
        antes = set(os.listdir(up))
        for etiqueta, nombre_malo in (("a:b*c?.png", "a:b*c?.png"), ("300 letras", "x" * 300 + ".png")):
            cod, r = subir(nombre_malo, PNG)
            it = r.get("item", {})
            n = it.get("name", "")
            fallos += comprobar(f"nombre {etiqueta} -> 200", cod == 200, f"{cod} {r}")
            fallos += comprobar(f"nombre {etiqueta}: archivo en disco",
                                os.path.isfile(os.path.join(up, it.get("id", "x"))))
            fallos += comprobar(f"nombre {etiqueta}: sin caracteres prohibidos, <=120 y .png",
                                n and not (set(n) & prohibidos) and len(n) <= 120 and n.endswith(".png"), n)
        nuevos = set(os.listdir(up)) - antes
        fallos += comprobar("solo aparecen los 2 archivos esperados (sin restos)", len(nuevos) == 2, str(nuevos))

        cod, r = subir("clip.mp4", MP4)
        fallos += comprobar("MP4 -> video", cod == 200 and r["item"]["type"] == "video", f"{cod} {r}")
        cod, r = subir("clip.webm", WEBM)
        fallos += comprobar("WEBM -> video", cod == 200 and r["item"]["type"] == "video", f"{cod} {r}")

        antes = sorted(os.listdir(up))
        cod, r = subir("falso.png", b"esto no es una imagen, es texto" * 10)
        fallos += comprobar("texto disfrazado de .png -> 415", cod == 415 and "imagen" in r.get("error", ""), f"{cod} {r}")
        cod, r = subir("foto.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
        fallos += comprobar("HEIC (ftyp de imagen) no se toma por vídeo -> 415", cod == 415, f"{cod} {r}")
        cod, r = subir("vacio.png", b"")
        fallos += comprobar("archivo vacío -> 400", cod == 400, f"{cod} {r}")
        fallos += comprobar("lo rechazado no deja archivos", sorted(os.listdir(up)) == antes)

        grande = PNG + os.urandom(30 * 1024 * 1024)
        cod, r = subir("grande.png", grande)
        fallos += comprobar("30 MB suben enteros",
                            cod == 200 and os.path.getsize(os.path.join(up, r["item"]["id"])) == len(grande), f"{cod} {r}")
        h = hashlib.sha256(open(os.path.join(up, r["item"]["id"]), "rb").read()).hexdigest()
        fallos += comprobar("y sin alterar un byte", h == hashlib.sha256(grande).hexdigest())

        antes = sorted(os.listdir(up))
        fallos += comprobar(f"más que el máximo ({MAX_MB} MB) -> 413 sin leer el cuerpo",
                            declarar_de_mas("enorme.png", (MAX_MB + 1) * 1024 * 1024) == 413)

        a_medias("cortado.png", 5 * 1024 * 1024, PNG + b"\x00" * (1024 * 1024))
        time.sleep(1.5)
        fallos += comprobar("subida cortada a mitad: sin .part ni archivo", sorted(os.listdir(up)) == antes,
                            str(sorted(set(os.listdir(up)) - set(antes))))
        _, contenido = peticion("GET", "/api/content")
        fallos += comprobar("ni elemento en la Librería", not any(i["name"] == "cortado.png" for i in contenido.get("items", [])))

        cod, _ = subir("sin_permiso.png", PNG, token=None)
        fallos += comprobar("sin sesión -> 401", cod == 401, str(cod))
        fallos += comprobar("y no se guarda nada", not any("sin_permiso" in n for n in os.listdir(up)))

        import base64
        cod, r = peticion("POST", "/api/upload", json.dumps(
            {"name": "viejo.png", "type": "image", "data": base64.b64encode(PNG).decode(), "size": len(PNG)}).encode(),
            cabeceras={"Content-Type": "application/json"})
        fallos += comprobar("el /api/upload antiguo sigue funcionando", cod == 200 and r.get("ok"), f"{cod} {r}")
    finally:
        if proc:
            proc.terminate()
            try: proc.wait(timeout=5)
            except Exception: proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_subida_raw" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
