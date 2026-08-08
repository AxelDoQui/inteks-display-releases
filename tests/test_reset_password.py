"""
La herramienta de restablecer la contrasena.

Ya paso una vez: se olvido la contrasena del panel y hubo que editar admin.json
a mano. En casa de un cliente eso es una llamada y acceso remoto al ordenador.

Lo delicado es QUE se borra. Si se borrara el archivo entero, la extension de
Chrome perderia su token y dejaria de poder enviar tasas, asi que habria que
reconfigurarla en el navegador. Solo se quitan salt y pwd_hash.

No hay ningun endpoint de recuperacion por la red, y es a proposito: eso no
seria recuperacion, seria una puerta trasera para cualquiera en el wifi de la
tienda. La prueba de identidad es estar delante del equipo.

Ejecutar:  python tests/test_reset_password.py
"""
import glob, json, os, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERRAMIENTA = os.path.join(SRC, "restablecer-contrasena.py")
PORT = 8099
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def correr(datos, respuesta="SI\n"):
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    return subprocess.run([sys.executable, HERRAMIENTA], input=respuesta,
                          capture_output=True, text=True, env=env, timeout=30)


def main():
    datos = tempfile.mkdtemp(prefix="signalos_rst_")
    apath = os.path.join(datos, "admin.json")
    original = {"salt": "abc123", "pwd_hash": "hash-secreto",
                "secret": "s" * 64, "api_token": "token-de-la-extension"}

    try:
        # ── Caso normal ────────────────────────────────────────────────────
        json.dump(dict(original), open(apath, "w"))
        r = correr(datos)
        check(r.returncode == 0, f"la herramienta termina bien -> {r.returncode}")

        despues = json.load(open(apath))
        check("pwd_hash" not in despues, "la contrasena se borra")
        check("salt" not in despues, "y su sal tambien")
        check(despues.get("api_token") == "token-de-la-extension",
              "el token de la extension SOBREVIVE (si no, habria que reconfigurarla)")
        check(despues.get("secret") == "s" * 64, "y el secreto de sesion tambien")

        copias = glob.glob(apath + ".bak-*")
        check(len(copias) == 1, f"deja una copia previa -> {copias}")
        check(json.load(open(copias[0])).get("pwd_hash") == "hash-secreto",
              "y esa copia conserva lo borrado, por si acaso")

        check("SIN PERDER TIEMPO" in r.stdout and "cualquiera" in r.stdout,
              "avisa de que hay que poner una nueva ya mismo")

        # ── Hay que confirmar ──────────────────────────────────────────────
        json.dump(dict(original), open(apath, "w"))
        r = correr(datos, respuesta="no\n")
        check(r.returncode == 1 and json.load(open(apath)).get("pwd_hash") == "hash-secreto",
              "sin confirmar no toca nada")

        # ── Sin contrasena puesta ──────────────────────────────────────────
        json.dump({"secret": "s" * 64}, open(apath, "w"))
        r = correr(datos)
        check(r.returncode == 0 and "ya no ten" in r.stdout.lower(),
              f"si no habia contrasena, lo dice y no falla -> {r.stdout.strip()[-60:]}")

        # ── Sin archivo ────────────────────────────────────────────────────
        os.remove(apath)
        for f in glob.glob(apath + ".bak-*"):
            os.remove(f)
        r = correr(datos)
        check(r.returncode == 1 and "No se encuentra admin.json" in r.stdout,
              "si no encuentra el archivo lo explica en vez de reventar")

        # Con SIGNALOS_DATA puesta, NO puede irse a buscar a otra parte. Este
        # test nacio de un susto real: la herramienta cayo hacia
        # %PROGRAMDATA%\SignalOS Pro y dejo sin contrasena una instalacion que
        # nadie estaba tocando.
        lineas = r.stdout.split("Se ha buscado en:", 1)[-1].strip().splitlines()
        buscadas = [l.strip() for l in lineas if l.strip().endswith("admin.json")]
        check(buscadas == [os.path.join(datos, "admin.json")],
              f"con SIGNALOS_DATA puesta busca SOLO ahi -> {buscadas}")

        # ── El servidor lo acepta de verdad ────────────────────────────────
        # Que el JSON quede bien no basta: hay que ver que el servidor entra en
        # modo "crea una contrasena" y no en un estado raro.
        app = tempfile.mkdtemp(prefix="signalos_rsta_")
        for f in ESTATICOS:
            shutil.copy2(os.path.join(SRC, f), app)
        json.dump(dict(original), open(apath, "w"))
        correr(datos)

        env = dict(os.environ); env["SIGNALOS_DATA"] = datos
        p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                             cwd=app, env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{PORT}"
        try:
            estado = None
            for _ in range(40):
                time.sleep(0.25)
                try:
                    estado = json.load(urllib.request.urlopen(
                        base + "/api/auth-status", timeout=1))
                    break
                except Exception:
                    pass
            check(estado is not None and estado.get("has_password") is False,
                  f"el servidor entra en modo 'crea una contrasena' -> {estado}")
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
            shutil.rmtree(app, ignore_errors=True)
    finally:
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
