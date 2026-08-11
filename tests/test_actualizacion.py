"""
Aviso de version nueva.

Hoy la unica forma de llevar una version nueva a una tienda instalada es ir con
el .exe. Esto no instala nada solo -en una pantalla de escaparate, actualizarse
sin permiso es la peor idea posible- pero al menos avisa en el panel.

Viene APAGADO: update_url vacia. El dia que haya donde publicar la version, se
pega la direccion y empieza a funcionar sin tocar codigo. Mientras tanto el
servidor no habla con nadie de fuera.

Ejecutar:  python tests/test_actualizacion.py
"""
import http.server, json, os, shutil, socketserver, subprocess, sys, tempfile
import threading, time, urllib.error, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8101
FAKE_PORT = 8199        # lejos de PORT: el servidor real usa PORT y PORT+1
TOKEN = "tok-prueba-version"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")

fallos = 0
respuesta_falsa = {"cuerpo": b'{"version":"9.9.9"}', "codigo": 200}


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


class Falso(http.server.BaseHTTPRequestHandler):
    """Hace de sitio donde se publica la ultima version."""
    def do_GET(self):
        self.send_response(respuesta_falsa["codigo"])
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(respuesta_falsa["cuerpo"])

    def log_message(self, *a):
        pass


def main():
    app = tempfile.mkdtemp(prefix="signalos_upd_")
    datos = tempfile.mkdtemp(prefix="signalos_updd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(datos, "admin.json"), "w"))
    cfgpath = os.path.join(datos, "config.json")
    json.dump({"port": PORT, "update_url": ""}, open(cfgpath, "w"))

    socketserver.TCPServer.allow_reuse_address = True
    falso = socketserver.TCPServer(("127.0.0.1", FAKE_PORT), Falso)
    threading.Thread(target=falso.serve_forever, daemon=True).start()

    procesos = []

    def arrancar(port):
        env = dict(os.environ); env["SIGNALOS_DATA"] = datos
        p = subprocess.Popen([sys.executable, "server.py", "--port", str(port)],
                             cwd=app, env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
        procesos.append(p)
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/auth-status", timeout=1)
                return p
            except Exception:
                pass
        return None

    def consultar(port, tok=TOKEN, force=True):
        # force=1 salta la cache. Sin esto, cada consulta del test devolveria la
        # respuesta de la primera y no se probaria nada.
        h = {"X-SignalOS-Token": tok} if tok else {}
        sufijo = "?force=1" if force else ""
        r = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/update-check{sufijo}", headers=h)
        return json.load(urllib.request.urlopen(r, timeout=15))

    try:
        # ── Apagado por defecto ────────────────────────────────────────────
        if not arrancar(PORT):
            print("FALLO: el servidor no arranco")
            return 1
        d = consultar(PORT)
        check(d.get("enabled") is False,
              f"sin direccion configurada, viene apagado -> {d}")
        check("update_available" not in d or d.get("update_available") is False,
              "y no se inventa que hay actualizacion")

        # ── La pantalla tiene que poder enterarse de que el servidor cambio ──
        # Al instalar una version nueva, la pagina que el televisor lleva horas
        # abierta sigue ejecutando el codigo viejo. Sin este dato en la
        # respuesta, el arreglo tarda hasta 4 horas en verse o no se ve nunca.
        # Paso de verdad con la 1.0.17.
        pl = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/api/playlist?screen=TV", timeout=10))
        import re as _re
        srv_version = pl.get("version", "")
        check(bool(_re.match(r"^\d+\.\d+\.\d+$", str(srv_version))),
              f"la playlist dice que version sirve el servidor -> {srv_version!r}")

        try:
            consultar(PORT, tok=None)
            check(False, "deberia exigir autenticacion")
        except urllib.error.HTTPError as ex:
            check(ex.code == 401, "consultar la version exige autenticacion")

        for p in procesos:
            p.terminate()
        procesos.clear()

        # ── Con direccion configurada ──────────────────────────────────────
        json.dump({"port": PORT + 1, "update_url": f"http://127.0.0.1:{FAKE_PORT}/v.json"},
                  open(cfgpath, "w"))
        if not arrancar(PORT + 1):
            print("FALLO: el servidor no arranco la segunda vez")
            return 1

        d = consultar(PORT + 1)
        check(d.get("enabled") is True and d.get("update_available") is True
              and d.get("latest") == "9.9.9",
              f"detecta que hay una version mas nueva -> {d}")
        check(d.get("current"), "y dice cual tiene instalada")

        # Misma version: no hay nada que avisar.
        respuesta_falsa["cuerpo"] = json.dumps({"version": d["current"]}).encode()
        d = consultar(PORT + 1)
        check(d.get("update_available") is False,
              f"con la misma version no avisa -> {d}")

        # Version publicada MAS VIEJA que la instalada: tampoco.
        respuesta_falsa["cuerpo"] = b'{"version":"0.0.1"}'
        d = consultar(PORT + 1)
        check(d.get("update_available") is False,
              "una version publicada mas vieja no cuenta como actualizacion")

        # ── La trampa clasica: comparar versiones como TEXTO ────────────────
        # "1.0.10" es alfabeticamente MENOR que "1.0.9", asi que un servidor que
        # comparase textos no anunciaria justo la actualizacion mas esperada.
        #
        # Esto se construye a partir de la version instalada y no con numeros
        # fijos: antes decia b'{"version":"1.0.10"}' y la prueba se cayo sola el
        # dia que el programa llego a la 1.0.10, porque su premisa -que la
        # instalada era anterior- dejo de ser cierta.
        mayor, menor, parche = (int(x) for x in d["current"].split("."))

        respuesta_falsa["cuerpo"] = json.dumps(
            {"version": f"{mayor}.{menor}.{parche + 1}"}).encode()
        d2 = consultar(PORT + 1)
        check(d2.get("update_available") is True,
              f"un parche mas alto es una actualizacion -> {d2}")

        # Y al reves: con el parche en dos digitos, uno de un solo digito
        # PARECE mayor en alfabetico ("...9" > "...10") pero es mas viejo.
        if parche >= 10 and str(parche)[0] < "9":
            respuesta_falsa["cuerpo"] = json.dumps(
                {"version": f"{mayor}.{menor}.9"}).encode()
            d2 = consultar(PORT + 1)
            check(d2.get("update_available") is False,
                  f"...9 parece mayor que ...{parche} como texto, pero es mas "
                  f"vieja y no se anuncia -> {d2}")

        # ── Que un fallo de red no rompa el panel ──────────────────────────
        respuesta_falsa["codigo"] = 500
        d = consultar(PORT + 1)
        check(d.get("enabled") is True and d.get("update_available") is False
              and d.get("error"),
              f"si no se puede consultar, lo dice sin romper -> {d}")
        respuesta_falsa["codigo"] = 200

        respuesta_falsa["cuerpo"] = b"esto no es json"
        d = consultar(PORT + 1)
        check(d.get("error") is not None and d.get("update_available") is False,
              "una respuesta que no es JSON tampoco rompe nada")

        # ── La consulta se cachea ──────────────────────────────────────────
        # Abrir Ajustes no puede salir a internet cada vez: seria molestar al
        # sitio de versiones y hacer esperar al panel sin motivo.
        respuesta_falsa["cuerpo"] = b'{"version":"5.5.5"}'
        primera = consultar(PORT + 1)                       # force: consulta de verdad
        respuesta_falsa["cuerpo"] = b'{"version":"7.7.7"}'
        segunda = consultar(PORT + 1, force=False)          # deberia salir de la cache
        check(segunda.get("latest") == primera.get("latest") == "5.5.5",
              f"sin forzar, responde desde la cache -> {segunda.get('latest')}")
        tercera = consultar(PORT + 1)                       # forzando, vuelve a mirar
        check(tercera.get("latest") == "7.7.7",
              f"y el boton de comprobar ahora si vuelve a mirar -> {tercera.get('latest')}")
    finally:
        for p in procesos:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        falso.shutdown()
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
