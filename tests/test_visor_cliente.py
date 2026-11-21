"""
Visor de cliente: el servidor hace de buzón del «saludo» WebRTC entre el PC del mostrador
(extensión de Chrome, con api_token) y la pantalla (player.html, sin sesión).

Ejecutar:
    python tests/test_visor_cliente.py
"""
import json, os, shutil, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8123
TOKEN = "token-de-pruebas-0123456789"
BASE = f"http://127.0.0.1:{PORT}"
SDP = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\n"


def llamar(path, payload=None, token=None):
    cab = {"Content-Type": "application/json"}
    if token: cab["X-SignalOS-Token"] = token
    req = urllib.request.Request(BASE + path, headers=cab, method="POST" if payload is not None else "GET",
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or "{}")
        except ValueError: return e.code, {}


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}" + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_visor_")
    proc = None
    try:
        for f in ("server.py", "index.html", "admin.html", "login.html", "player.html", "pair.html", "sw.js", "config.json"):
            shutil.copy2(os.path.join(SRC, f), work)
        json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
        json.dump({"TV": {"id": "TV", "connected": True, "last_seen": time.time()}}, open(os.path.join(work, "screens.json"), "w"))
        proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=work,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(40):
            time.sleep(0.25)
            try: urllib.request.urlopen(BASE + "/api/auth-status", timeout=1); break
            except Exception: pass

        # Sin oferta
        cod, r = llamar("/api/visor/oferta?screen=TV")
        fallos += comprobar("sin oferta: ok false", cod == 200 and r.get("ok") is False, str((cod, r)))

        # La oferta la pone solo quien lleva el api_token
        cod, _ = llamar("/api/visor/oferta", {"screen": "TV", "sdp": SDP})
        fallos += comprobar("poner oferta sin token -> 401", cod == 401, str(cod))
        cod, _ = llamar("/api/visor/oferta", {"screen": "NoExiste", "sdp": SDP}, TOKEN)
        fallos += comprobar("oferta para pantalla desconocida -> 404", cod == 404, str(cod))
        cod, _ = llamar("/api/visor/oferta", {"screen": "TV", "sdp": "hola"}, TOKEN)
        fallos += comprobar("oferta que no es un SDP -> 400", cod == 400, str(cod))
        cod, _ = llamar("/api/visor/oferta", {"screen": "TV", "sdp": SDP + "a" * 40000}, TOKEN)
        fallos += comprobar("oferta enorme -> 400", cod in (400, 413), str(cod))
        cod, r = llamar("/api/visor/oferta", {"screen": "TV", "sdp": SDP}, TOKEN)
        n1 = r.get("n")
        fallos += comprobar("oferta con token -> ok y número", cod == 200 and r.get("ok") and isinstance(n1, int), str((cod, r)))

        # La pantalla la lee sin sesión
        cod, r = llamar("/api/visor/oferta?screen=TV")
        fallos += comprobar("la pantalla lee la oferta sin sesión", cod == 200 and r.get("sdp") == SDP and r.get("n") == n1 and r.get("respondida") is False, str(r))
        cod, r = llamar("/api/visor/oferta?screen=NoExiste")
        fallos += comprobar("pantalla desconocida -> 404", cod == 404, str(cod))

        # La respuesta
        resp = SDP.replace("o=- 1 2", "o=- 9 9")
        cod, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n1 + 5, "sdp": resp})
        fallos += comprobar("respuesta a otra oferta no vale", cod == 200 and r.get("ok") is False, str((cod, r)))
        cod, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n1, "sdp": "hola"})
        fallos += comprobar("respuesta que no es SDP -> 400", cod == 400, str(cod))
        cod, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": True, "sdp": resp})
        fallos += comprobar("número que no es número -> 400", cod == 400, str(cod))
        cod, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n1, "sdp": resp})
        fallos += comprobar("la pantalla responde sin sesión", cod == 200 and r.get("ok") is True, str((cod, r)))
        cod, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n1, "sdp": resp + "x"})
        fallos += comprobar("solo vale la primera respuesta", cod == 200 and r.get("ok") is False, str((cod, r)))
        _, r = llamar("/api/visor/oferta?screen=TV")
        fallos += comprobar("la oferta consta como respondida", r.get("respondida") is True, str(r))

        # La respuesta solo la lee la extensión, una vez
        cod, _ = llamar(f"/api/visor/respuesta?screen=TV&n={n1}")
        fallos += comprobar("leer la respuesta sin token -> 401", cod == 401, str(cod))
        cod, r = llamar(f"/api/visor/respuesta?screen=TV&n={n1}", token=TOKEN)
        fallos += comprobar("la extensión lee la respuesta", cod == 200 and r.get("sdp") == resp, str((cod, r)))
        cod, r = llamar(f"/api/visor/respuesta?screen=TV&n={n1}", token=TOKEN)
        fallos += comprobar("de un solo uso", r.get("ok") is False, str(r))
        _, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n1, "sdp": resp})
        fallos += comprobar("y tras leerla nadie más puede responder", r.get("ok") is False, str(r))

        # Oferta nueva: número nuevo y anula lo viejo
        _, r = llamar("/api/visor/oferta", {"screen": "TV", "sdp": SDP}, TOKEN)
        n2 = r.get("n")
        fallos += comprobar("oferta nueva -> número nuevo", n2 == n1 + 1, str(r))
        _, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n1, "sdp": resp})
        fallos += comprobar("respuesta a la oferta vieja ya no vale", r.get("ok") is False, str(r))
        _, r = llamar("/api/visor/respuesta", {"screen": "TV", "n": n2, "sdp": resp})
        fallos += comprobar("a la nueva sí", r.get("ok") is True, str(r))

        # Cerrar
        cod, _ = llamar("/api/visor/cerrar", {"screen": "TV"})
        fallos += comprobar("cerrar sin token -> 401", cod == 401, str(cod))
        cod, _ = llamar("/api/visor/cerrar", {"screen": "TV"}, TOKEN)
        _, r = llamar("/api/visor/oferta?screen=TV")
        fallos += comprobar("tras cerrar no hay oferta", cod == 200 and r.get("ok") is False, str(r))
        _, r = llamar("/api/visor/oferta", {"screen": "TV", "sdp": SDP}, TOKEN)
        fallos += comprobar("el número sigue subiendo tras cerrar", r.get("n") == n2 + 1, str(r))

        # Nada en disco
        fallos += comprobar("no se escribe nada en disco", not any("visor" in f.lower() for f in os.listdir(work)))
    finally:
        if proc: proc.kill(); proc.wait()
        shutil.rmtree(work, ignore_errors=True)
    print("\nTODO BIEN" if not fallos else f"\n{fallos} FALLO(S)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
