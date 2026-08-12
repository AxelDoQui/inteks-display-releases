"""
Reconexion SSE: una conexion vieja que muere no puede pisar a la nueva.

Caso real, 2026-08-12: "Pantalla Exterior (LG)" servia contenido con total
normalidad -el bot de Telegram la veia conectada- y el panel la mostraba
caida. La causa era una carrera: cada conexion /api/events corre en su
propio hilo (ThreadingHTTPServer), y un EventSource reconecta solo por su
cuenta. Si la reconexion llega ANTES de que el hilo de la conexion vieja se
entere de que la suya murio -tarda hasta el siguiente ping, cada 10 s-, el
hilo viejo, al fin enterarse, pisaba `connected=True` (que puso la conexion
nueva) con su propio `connected=False`. La pantalla quedaba marcada caida
para siempre aunque siguiera viva y sirviendo.

Esto SOLO se reproduce con hilos y sockets de verdad -un simulacro no
reproduce una carrera-, asi que se arranca el servidor real, como en
test_concurrencia.py. Es lento a proposito (~25 s): el servidor solo detecta
una conexion muerta al intentar escribirle el siguiente ping, y ese intervalo
esta grabado en el propio server.py, no hay forma de acelerarlo desde fuera.

Detalle tecnico importante: el cierre tiene que ser ABORTIVO (RST), no un
cierre normal (FIN). Se probo con un cierre normal y el servidor, en esta
maquina, tardaba muchisimo mas de un ciclo de ping en enterarse -o no se
enteraba nunca dentro de un tiempo razonable de prueba-, probablemente porque
el primer par de escrituras se limitan a encolarse en el buffer del sistema
sin que nadie las rechace todavia. Con SO_LINGER a 0 el cierre manda un RST
de verdad, y el siguiente ping falla en el primer intento, tal como pasaria
con una caida de wifi real.

Ejecutar:  python tests/test_sse_reconexion.py
"""
import json, os, shutil, socket, struct, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8108          # libre: los demas usan 8086, 8090, 8093, 8097-8101, 8103-8107
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "token-de-pruebas-sse-0123456789"

CONTENIDO_BASE = {
    "items": [], "packages": [],
    "screens": {"TV": {"mode": "independent", "always_on": True, "playlist": []}},
    "rev": 0,
}


def arrancar():
    work = tempfile.mkdtemp(prefix="signalos_sse_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    json.dump(CONTENIDO_BASE, open(os.path.join(work, "content.json"), "w"))
    # Token de API para poder leer /api/screens (protegido) sin sesion de panel.
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(work, "admin.json"), "w"))

    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(BASE + "/api/auth-status", timeout=1)
            return proc, work
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("el servidor no arranco")


def parar(proc, work):
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    shutil.rmtree(work, ignore_errors=True)


def conectado(sid="TV"):
    req = urllib.request.Request(BASE + "/api/screens", headers={"X-SignalOS-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read()).get(sid, {}).get("connected")


def abrir_sse(sid="TV"):
    """Abre una conexion /api/events de verdad, por socket crudo (para poder
    forzar despues un cierre abortivo), y espera a que quede registrada."""
    s = socket.create_connection(("127.0.0.1", PORT), timeout=15)
    s.sendall(f"GET /api/events?screen={sid} HTTP/1.1\r\nHost: x\r\nConnection: keep-alive\r\n\r\n".encode())
    buf = b""
    while b"data: connected" not in buf:
        buf += s.recv(4096)
    return s


def matar_de_golpe(s):
    """Cierre ABORTIVO (RST), no un cierre normal (FIN).

    Con un cierre normal, el servidor no se entera en un tiempo razonable
    -las primeras escrituras se quedan encoladas sin que nadie las rechace
    todavia-. SO_LINGER a 0 fuerza un RST real: la siguiente escritura del
    servidor falla en el acto, igual que pasaria con una caida de wifi.
    """
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    s.close()


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    proc, work = arrancar()
    fallos = 0
    try:
        # ── La reconexion no debe quedar pisada por la conexion vieja ───────
        vieja = abrir_sse("TV")
        fallos += comprobar("la primera conexion deja la pantalla en linea",
                            conectado("TV") is True)

        # El EventSource del televisor reconecta solo, SIN que este hilo viejo
        # se haya enterado todavia de que su conexion murio (eso tarda hasta
        # el siguiente ping). Se mata la vieja de golpe -como una caida de
        # wifi real- y se abre la nueva enseguida.
        matar_de_golpe(vieja)
        time.sleep(1)
        nueva = abrir_sse("TV")
        fallos += comprobar("la reconexion deja la pantalla en linea",
                            conectado("TV") is True)

        # Ahora hay que esperar a que el hilo VIEJO, dormido en su ciclo de
        # ping, intente escribirle a un socket que ya no existe, falle, y
        # corra su limpieza. Sin el arreglo, esa limpieza pisaba
        # connected=True (de la conexion nueva) con connected=False.
        time.sleep(13)
        fallos += comprobar(
            "tras la limpieza de la conexion vieja, la pantalla SIGUE en linea",
            conectado("TV") is True,
            "la conexion nueva sigue viva: no debia marcarse caida")

        matar_de_golpe(nueva)

        # ── Contraste: si de verdad no queda ninguna conexion, SI se marca caida ──
        # Confirma que el arreglo no rompio el caso normal: una pantalla que
        # de verdad se apaga tiene que seguir marcandose caida.
        time.sleep(13)
        fallos += comprobar(
            "sin ninguna conexion viva, la pantalla SI se marca caida",
            conectado("TV") is False)
    finally:
        parar(proc, work)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
