"""
Archivos subidos con espacios o acentos en el nombre.

El servidor nunca decodificaba la URL. urlparse() no deshace el
porcentaje-encoding, asi que cuando el navegador pedia "Tarifas%20sujetas",
el servidor buscaba en disco un archivo cuyo nombre contuviera literalmente
"%20". No existe -> 404.

Las imagenes funcionaban de casualidad: se llamaban 0000_1.png, sin un solo
caracter que necesite codificarse. Cualquier archivo con espacios o acentos
era invisible: el video no se reproducia y su miniatura salia negra, sin
ningun mensaje de error que lo explicara.

Ejecutar:  python tests/test_nombres_urls.py
"""
import json, os, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8106
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_url_")
    datos = tempfile.mkdtemp(prefix="signalos_urld_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    ups = os.path.join(datos, "uploads")
    os.makedirs(ups, exist_ok=True)

    # Los tres nombres son reales: el primero salio de una instalacion de
    # verdad y es el que destapo el fallo.
    NOMBRES = [
        "0003_Tarifas sujetas a cambios. Consulta términos y condiciones.mp4",
        "0000_1.png",
        "cartel año nuevo.png",
    ]
    for n in NOMBRES:
        with open(os.path.join(ups, n), "wb") as f:
            f.write(b"\x00" * 2048)

    # Un archivo fuera de uploads, para comprobar que sigue sin poder tocarse.
    with open(os.path.join(datos, "admin.json"), "w") as f:
        json.dump({"secret": "s" * 64, "pwd_hash": "no-me-leas"}, f)

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def pedir(ruta_cruda):
        """Pide una ruta tal cual, sin que urllib la vuelva a codificar."""
        try:
            r = urllib.request.urlopen(base + ruta_cruda, timeout=5)
            return r.status, r.read(64)
        except urllib.error.HTTPError as e:
            return e.code, b""

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

        for n in NOMBRES:
            # Exactamente lo que manda el navegador: el nombre codificado.
            ruta = "/uploads/" + urllib.parse.quote(n)
            code, _ = pedir(ruta)
            check(code == 200, f"se sirve «{n[:40]}…» -> HTTP {code}")

        # ── La proteccion contra salirse de uploads sigue en pie ───────────
        # Decodificar abre la puerta a esconder ../ dentro del porcentaje.
        for intento in ("/uploads/../admin.json",
                        "/uploads/%2e%2e/admin.json",
                        "/uploads/%2E%2E%2Fadmin.json",
                        "/uploads/..%2Fadmin.json"):
            code, cuerpo = pedir(intento)
            check(code == 404 and b"no-me-leas" not in cuerpo,
                  f"no se puede salir de uploads con «{intento}» -> HTTP {code}")

        # Un archivo que de verdad no existe sigue dando 404.
        code, _ = pedir("/uploads/" + urllib.parse.quote("no existe.png"))
        check(code == 404, "un archivo inexistente sigue dando 404")

        # ── Los estaticos tambien se decodifican ───────────────────────────
        with open(os.path.join(app, "página de prueba.html"), "w", encoding="utf-8") as f:
            f.write("<h1>hola</h1>")
        code, cuerpo = pedir("/" + urllib.parse.quote("página de prueba.html"))
        check(code == 200 and b"hola" in cuerpo,
              f"un estatico con acentos tambien se sirve -> HTTP {code}")
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
