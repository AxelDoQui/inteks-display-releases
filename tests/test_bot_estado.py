"""
Bot de Telegram que responde: /estado.

Prueba las piezas sin hilo de fondo (que corre para siempre) ni internet:
construir_estado() con datos preparados, quien recibe respuesta y quien
silencio, y el long-poll de verdad contra un Telegram de mentira -el mismo
que ya usa test_avisos.py.

Ejecutar:  python tests/test_bot_estado.py
"""
import http.server, importlib.util, json, os, shutil, socketserver, sys
import tempfile, threading, time
from urllib.parse import urlparse, parse_qs

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(AQUI)
FAKE_PORT = 8197

recibidas = []          # peticiones que le llegaron al Telegram de mentira


class FalsoTelegram(http.server.BaseHTTPRequestHandler):
    respuestas_updates = []   # cola de listas de "updates" a devolver, una por llamada

    def do_GET(self):
        recibidas.append(self.path)
        cuerpo = {"ok": True, "result": []}
        if "getUpdates" in self.path:
            cola = FalsoTelegram.respuestas_updates
            cuerpo["result"] = cola.pop(0) if cola else []
        self._responder(cuerpo)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        recibidas.append((self.path, self.rfile.read(n).decode("utf-8", "replace")))
        self._responder({"ok": True})

    def _responder(self, cuerpo):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(cuerpo).encode())

    def log_message(self, *a):
        pass


fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    datos = tempfile.mkdtemp(prefix="signalos_bot_")
    os.environ["SIGNALOS_DATA"] = datos

    socketserver.TCPServer.allow_reuse_address = True
    falso = socketserver.TCPServer(("127.0.0.1", FAKE_PORT), FalsoTelegram)
    threading.Thread(target=falso.serve_forever, daemon=True).start()

    spec = importlib.util.spec_from_file_location("srv", os.path.join(SRC, "server.py"))
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)

    srv.TELEGRAM_API = f"http://127.0.0.1:{FAKE_PORT}/bot{{token}}/sendMessage"
    srv.TELEGRAM_GETUPDATES_API = f"http://127.0.0.1:{FAKE_PORT}/bot{{token}}/getUpdates"

    ahora = time.time()
    try:
        # ── construir_estado(): pantallas ───────────────────────────────────
        srv.save_json(srv.CONTENT_FILE, {"items": [], "packages": [], "screens": {
            "Escaparate": {"mode": "independent", "always_on": True, "playlist": [
                {"id": "fx_1", "type": "fx", "name": "Western Union", "stale_hours": 24,
                 "updated_at": ahora - 3600, "rows": []},
            ]},
            "Caja": {"mode": "independent", "playlist": [
                {"id": "fx_2", "type": "fx", "name": "Ria", "stale_hours": 24,
                 "updated_at": ahora - 3 * 86400, "rows": []},
            ]},
        }})
        srv.save_json(srv.SCREENS_FILE, {
            "Escaparate": {"id": "Escaparate", "connected": True, "last_seen": ahora},
            "Caja": {"id": "Caja", "connected": False, "last_seen": ahora - 7200},
            "admin": {"id": "admin", "connected": True, "last_seen": ahora},
        })

        texto = srv.construir_estado()
        check("Escaparate" in texto and "en línea" in texto,
              "incluye una pantalla conectada")
        check("Caja" in texto and "caída" in texto, "incluye una pantalla caída")
        check("admin" not in texto.split("Pantallas")[1].split("Tableros")[0],
              "el panel admin no cuenta como pantalla")
        check("Western Union" in texto and "✅" in texto,
              "tablero al día sale marcado ok")
        check("Ria" in texto and "⚠" in texto, "tablero caducado sale marcado con aviso")
        check(srv.APP_VERSION in texto, "incluye la versión")

        # ── _responder_mensaje(): autorización y comandos ───────────────────
        check(srv._responder_mensaje("/estado", 111, "111") is not None,
              "el chat autorizado recibe respuesta a /estado")
        check(srv._responder_mensaje("/estado", 222, "111") is None,
              "un chat distinto no recibe nada -ni error-")
        check(srv._responder_mensaje("/Estado@MiBot", 111, "111") is not None,
              "tolera mayúsculas y el sufijo @nombrebot")
        check(srv._responder_mensaje("hola", 111, "111") is not None,
              "algo que no es /estado recibe la línea de ayuda")
        check("PIN" not in (srv._responder_mensaje("hola", 111, "111") or "") and
              "reiniciar" not in (srv._responder_mensaje("hola", 111, "111") or "").lower(),
              "la ayuda no menciona nada sensible")

        # ── _telegram_get_updates(): contra el falso Telegram de verdad ─────
        FalsoTelegram.respuestas_updates = [[
            {"update_id": 501, "message": {"chat": {"id": 111}, "text": "/estado"}},
        ]]
        recibidas.clear()
        r = srv._telegram_get_updates("123:ABC", offset=500, timeout=0)
        check(len(r) == 1 and r[0]["update_id"] == 501,
              f"lee un update de verdad por HTTP -> {r}")
        check(any("getUpdates" in p and "offset=500" in p for p in recibidas),
              f"manda el offset en la petición -> {recibidas}")

        # ── Telegram caído no revienta ───────────────────────────────────────
        r = srv._telegram_get_updates("123:ABC", offset=None, timeout=0)  # cola ya vacía, ok
        srv.TELEGRAM_GETUPDATES_API = "http://127.0.0.1:9/bot{token}/getUpdates"  # puerto muerto
        try:
            r = srv._telegram_get_updates("123:ABC", offset=None, timeout=0)
            check(r == [], "si Telegram no responde, no revienta y no inventa mensajes")
        except Exception as e:
            check(False, f"si Telegram no responde, no revienta -> {e}")
    finally:
        falso.shutdown()
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
