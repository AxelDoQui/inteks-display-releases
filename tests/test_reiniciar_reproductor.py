"""
Botón «Reiniciar reproductor»: POST /api/screen-reload manda «reload» por SSE
a la pantalla pedida (y a ninguna otra) y el player lo entiende.

Ejecutar:  python tests/test_reiniciar_reproductor.py
"""
import http.client, json, os, shutil, subprocess, sys, tempfile, threading, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8135
TOKEN = "tok-prueba-reload"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def escuchar(pantalla, salida):
    """Abre el SSE de una pantalla y apunta las líneas «data:» que llegan."""
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=8)
    c.request("GET", f"/api/events?screen={pantalla}")
    r = c.getresponse()
    t0 = time.time()
    while time.time() - t0 < 6:
        try:
            l = r.fp.readline().decode("utf-8", "replace").strip()
        except Exception:
            break
        if l.startswith("data:"):
            salida.append(l)


def main():
    html = open(os.path.join(SRC, "player.html"), encoding="utf-8").read()
    check('indexOf("reload")===0' in html, "el player entiende «reload»")
    app = tempfile.mkdtemp(prefix="signalos_rl_")
    datos = tempfile.mkdtemp(prefix="signalos_rld_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    json.dump({"rev": 1, "screens": {"TV": {"mode": "independent", "playlist": []},
                                     "TV2": {"mode": "independent", "playlist": []}}},
              open(os.path.join(datos, "content.json"), "w"))
    env = dict(os.environ); env["SIGNALOS_DATA"] = datos
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"

    def pedir(ruta, payload):
        r = urllib.request.Request(base + ruta, data=json.dumps(payload).encode(),
                                   headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN},
                                   method="POST")
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1); break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco"); return 1
        tv, tv2 = [], []
        for pant, sal in (("TV", tv), ("TV2", tv2)):
            threading.Thread(target=escuchar, args=(pant, sal), daemon=True).start()
        time.sleep(1.5)
        st, d = pedir("/api/screen-reload", {"id": "TV"})
        check(st == 200 and d.get("entregado") is True, "pide reiniciar y dice que lo entregó")
        time.sleep(1.5)
        check(any("reload:TV" in l for l in tv), "la pantalla pedida recibe «reload»")
        check(not any("reload" in l for l in tv2), "las demás no lo reciben")
        st, d = pedir("/api/screen-reload", {"id": "TV2"})
        st2, d2 = pedir("/api/screen-reload", {})
        st3, _ = pedir("/api/screen-reload", {"id": "no-existe"})
        check(st2 == 400 and st3 == 404, "sin id da 400 y una que no existe da 404")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
