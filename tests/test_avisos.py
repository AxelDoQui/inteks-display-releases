"""
Avisos por Telegram.

El servidor sabe desde hace tiempo que pantallas estan conectadas y desde
cuando, pero esa informacion solo existe si alguien mira el panel, y nadie lo
mira. Si un televisor pierde corriente un sabado a las 9, te enteras el lunes.

Se avisa de tres cosas: pantalla caida en horario, pantalla que vuelve, y
tasas caducadas. Cada una UNA vez: un aviso por minuto durante el fin de
semana se convierte en ruido y se deja de leer, que es lo mismo que no avisar.

Aqui Telegram es un servidor de mentira, para no depender de internet ni
mandarle nada a nadie.

Ejecutar:  python tests/test_avisos.py
"""
import http.server, importlib.util, json, os, shutil, socketserver, sys
import tempfile, threading, time

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(AQUI)
FAKE_PORT = 8196

enviados = []


class FalsoTelegram(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        enviados.append(self.rfile.read(n).decode("utf-8", "replace"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    datos = tempfile.mkdtemp(prefix="signalos_avi_")
    os.environ["SIGNALOS_DATA"] = datos

    socketserver.TCPServer.allow_reuse_address = True
    falso = socketserver.TCPServer(("127.0.0.1", FAKE_PORT), FalsoTelegram)
    threading.Thread(target=falso.serve_forever, daemon=True).start()

    spec = importlib.util.spec_from_file_location("srv", os.path.join(SRC, "server.py"))
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)

    # Telegram apuntando al servidor de mentira.
    srv.TELEGRAM_API = f"http://127.0.0.1:{FAKE_PORT}/bot{{token}}/sendMessage"

    cfg = srv.load_json(srv.CONFIG_FILE)
    cfg.update({"telegram_token": "123:ABC", "telegram_chat_id": "999",
                "alert_offline_min": 15})
    srv.save_json(srv.CONFIG_FILE, cfg)

    ahora = time.time()
    try:
        # ── Pantalla caida en horario ──────────────────────────────────────
        srv.save_json(srv.CONTENT_FILE, {"items": [], "packages": [], "screens": {
            "Escaparate": {"mode": "independent", "always_on": True, "playlist": []}}})
        srv.save_json(srv.SCREENS_FILE, {
            "Escaparate": {"id": "Escaparate", "connected": False,
                           "last_seen": ahora - 3600}})
        enviados.clear()
        srv.revisar_avisos()
        check(len(enviados) == 1 and "Escaparate" in enviados[0],
              f"avisa de la pantalla caida -> {enviados}")

        # ── No repite ──────────────────────────────────────────────────────
        enviados.clear()
        srv.revisar_avisos()
        srv.revisar_avisos()
        check(enviados == [], "no repite el aviso en cada pasada")

        # ── Cuando vuelve, avisa una vez ───────────────────────────────────
        srv.save_json(srv.SCREENS_FILE, {
            "Escaparate": {"id": "Escaparate", "connected": True,
                           "last_seen": time.time()}})
        enviados.clear()
        srv.revisar_avisos()
        check(len(enviados) == 1 and "Escaparate" in enviados[0],
              f"avisa de que ha vuelto -> {enviados}")
        enviados.clear()
        srv.revisar_avisos()
        check(enviados == [], "y tampoco repite la recuperacion")

        # ── Fuera de horario no molesta ────────────────────────────────────
        # Con todos los dias deshabilitados, la pantalla esta apagada porque
        # toca, no porque se haya roto.
        cerrado = {d: {"enabled": False} for d in
                   ("lunes", "martes", "miércoles", "jueves", "viernes",
                    "sábado", "domingo")}
        srv.save_json(srv.CONTENT_FILE, {"items": [], "packages": [], "screens": {
            "Caja": {"mode": "independent", "playlist": [], "schedule": cerrado}}})
        srv.save_json(srv.SCREENS_FILE, {
            "Caja": {"id": "Caja", "connected": False, "last_seen": ahora - 7200}})
        srv._alertas.clear()
        enviados.clear()
        srv.revisar_avisos()
        check(enviados == [], "no avisa de una pantalla que esta fuera de horario")

        # ── Tasas caducadas ────────────────────────────────────────────────
        srv.save_json(srv.CONTENT_FILE, {
            "items": [], "packages": [],
            "screens": {"TV": {"mode": "independent", "always_on": True, "playlist": [
                {"id": "fx_1", "type": "fx", "name": "WU", "stale_hours": 24,
                 "updated_at": ahora - 3 * 86400, "rows": []}]}}})
        srv.save_json(srv.SCREENS_FILE, {
            "TV": {"id": "TV", "connected": True, "last_seen": time.time()}})
        srv._alertas.clear()
        enviados.clear()
        srv.revisar_avisos()
        check(len(enviados) == 1 and "WU" in enviados[0],
              f"avisa de las tasas caducadas -> {enviados}")
        enviados.clear()
        srv.revisar_avisos()
        check(enviados == [], "y no lo repite cada minuto")

        # ── Sin token no se contacta con nadie ─────────────────────────────
        cfg = srv.load_json(srv.CONFIG_FILE)
        cfg["telegram_token"] = ""
        srv.save_json(srv.CONFIG_FILE, cfg)
        srv._alertas.clear()
        enviados.clear()
        srv.save_json(srv.SCREENS_FILE, {
            "TV": {"id": "TV", "connected": False, "last_seen": ahora - 7200}})
        srv.revisar_avisos()
        check(enviados == [], "sin token configurado no se habla con nadie")

        # ── Telegram caido no puede tumbar el servidor ─────────────────────
        cfg["telegram_token"] = "123:ABC"
        srv.save_json(srv.CONFIG_FILE, cfg)
        srv.TELEGRAM_API = "http://127.0.0.1:9/bot{token}/sendMessage"  # puerto muerto
        srv._alertas.clear()
        try:
            srv.revisar_avisos()
            check(True, "si Telegram no responde, no revienta")
        except Exception as e:
            check(False, f"si Telegram no responde, no revienta -> {e}")
    finally:
        falso.shutdown()
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
