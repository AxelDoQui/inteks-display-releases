"""
Guardar los ajustes no puede borrar lo que el formulario no conoce.

El panel manda 5 claves (puerto, alternativo, nombre, autoarranque,
first_run) y el servidor hacia save_json del cuerpo entero: todo lo demas
-mdns_name, update_url, y manana el token de Telegram- desaparecia en
silencio la primera vez que alguien tocaba Ajustes y pulsaba Guardar.

Ejecutar:  python tests/test_config_merge.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8103
TOKEN = "tok-prueba-config"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    app = tempfile.mkdtemp(prefix="signalos_cfg_")
    datos = tempfile.mkdtemp(prefix="signalos_cfgd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(datos, "admin.json"), "w"))
    cfgpath = os.path.join(datos, "config.json")
    json.dump({"port": PORT, "port_fallback": 9000, "mdns_name": "signage",
               "installation_name": "Tienda Centro", "update_url": "https://ejemplo/v.json",
               "telegram_token": "no-me-borres", "autostart": True},
              open(cfgpath, "w"))

    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                         cwd=app, env=env, stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def post(payload):
        r = urllib.request.Request(
            base + "/api/config", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN},
            method="POST")
        return json.load(urllib.request.urlopen(r, timeout=5))

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

        # Exactamente lo que manda el formulario de Ajustes.
        post({"port": PORT, "port_fallback": 9000,
              "installation_name": "Tienda Norte", "autostart": False,
              "first_run": False})

        cfg = json.load(open(cfgpath))
        check(cfg.get("installation_name") == "Tienda Norte",
              "lo que se envia si se aplica")
        check(cfg.get("autostart") is False,
              "incluso cuando el valor nuevo es false")
        check(cfg.get("update_url") == "https://ejemplo/v.json",
              "update_url sobrevive")
        check(cfg.get("telegram_token") == "no-me-borres",
              "el token de Telegram sobrevive")
        check(cfg.get("mdns_name") == "signage",
              "mdns_name sobrevive")

        # Un cuerpo que no es un objeto no puede dejar la configuracion vacia.
        try:
            post([1, 2, 3])
        except Exception:
            pass
        cfg = json.load(open(cfgpath))
        check(cfg.get("port_fallback") == 9000,
              "un cuerpo invalido no destroza la configuracion")
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
