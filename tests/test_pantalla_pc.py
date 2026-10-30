"""
El interruptor «Este PC reproduce en su propia pantalla» (pantalla_pc).

La tarea programada «InTeks Display Pantalla» abre el reproductor cada 5 min; el
panel guarda `pantalla_pc` en config.json y InTeksDisplay.exe --pantalla lo lee
con una expresion regular (escritorio/InTeksDisplay.cs, LeerPantallaPc). Aqui se
comprueba lo que el servidor escribe y que esa misma expresion lo reconoce, y que
el panel lo muestra y lo manda.

Ejecutar:  python tests/test_pantalla_pc.py
"""
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8131
TOKEN = "tok-prueba-pantalla-pc"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
# La de InTeksDisplay.cs: solo un false explicito apaga la pantalla.
APAGADA = re.compile(r'"pantalla_pc"\s*:\s*false')

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    html = open(os.path.join(SRC, "admin.html"), encoding="utf-8").read()
    check('id="set-pantalla-pc"' in html, "el panel tiene la casilla")
    check('cfg.pantalla_pc!==false' in html, "al cargar, ausente cuenta como activa")
    check('pantalla_pc:document.getElementById("set-pantalla-pc").checked' in html,
          "al guardar manda la casilla")
    cs = open(os.path.join(SRC, "escritorio", "InTeksDisplay.cs"), encoding="utf-8").read()
    check(r'"\"pantalla_pc\"\\s*:\\s*false"' in cs,
          "el lanzador usa la expresion que este test da por buena")

    app = tempfile.mkdtemp(prefix="signalos_ppc_")
    datos = tempfile.mkdtemp(prefix="signalos_ppcd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(datos, "admin.json"), "w"))
    cfgpath = os.path.join(datos, "config.json")
    json.dump({"port": PORT, "port_fallback": 9000, "mdns_name": "signage",
               "telegram_token": "no-me-borres"}, open(cfgpath, "w"))

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

    def get():
        r = urllib.request.Request(base + "/api/config",
                                   headers={"X-SignalOS-Token": TOKEN})
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

        check(not APAGADA.search(open(cfgpath).read()),
              "sin la clave, la pantalla cuenta como activa")

        post({"pantalla_pc": False, "first_run": False})
        txt = open(cfgpath).read()
        check(APAGADA.search(txt) is not None,
              "apagada: lo escrito lo reconoce el lanzador")
        check(get().get("pantalla_pc") is False, "GET /api/config la devuelve apagada")
        check(json.loads(txt).get("telegram_token") == "no-me-borres",
              "apagarla no borra otros ajustes")

        # El formulario sigue mandando sus claves de siempre; no debe reactivarla
        # si no la incluye (otros clientes de /api/config).
        post({"installation_name": "Tienda Norte"})
        check(APAGADA.search(open(cfgpath).read()) is not None,
              "guardar otros ajustes sin la clave no la reactiva")

        post({"pantalla_pc": True})
        check(not APAGADA.search(open(cfgpath).read()), "reactivada: el lanzador abre")
        check(get().get("pantalla_pc") is True, "GET la devuelve activa")
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
