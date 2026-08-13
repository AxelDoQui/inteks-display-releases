"""
Desenlazar una pantalla que esta APAGADA tiene que seguir surtiendo efecto.

Caso real reportado el 2026-08-13: "a veces al desvincular una pantalla esta no
se desvincula y no me deja reciclarla".

La causa: desenlazar era un mensaje al aire, no un estado. El servidor mandaba
"unlink:<sid>" por SSE a quien estuviera escuchando EN ESE INSTANTE y no lo
apuntaba en ningun sitio. Si el televisor estaba apagado, dormido, o la red
parpadeo justo entonces, el mensaje no llegaba a nadie y el desenlace se perdia
en silencio: el aparato conservaba su identidad en localStorage y al volver el
servidor le servia su playlist como si nada. El nombre quedaba ocupado por un
aparato que se creia su dueno, y por eso no se podia reciclar.

El arreglo: si no habia nadie escuchando, se apunta el desenlace en
screens.json y se le entrega al aparato la proxima vez que aparezca.

Ejecutar:  python tests/test_desenlace.py
"""
import json, os, shutil, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8109          # libre: los demas usan 8086, 8090, 8093, 8097-8101, 8103-8108
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "token-de-pruebas-desenlace-01234"

CONTENIDO_BASE = {
    "items": [], "packages": [],
    "screens": {"TV": {"mode": "independent", "always_on": True, "playlist": []}},
    "rev": 0,
}


def arrancar():
    work = tempfile.mkdtemp(prefix="signalos_unlink_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    json.dump(CONTENIDO_BASE, open(os.path.join(work, "content.json"), "w"))
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(work, "admin.json"), "w"))
    # La pantalla ya existe y esta registrada, como una tele que lleva meses
    # enlazada. Lo importante es que AHORA MISMO no hay ninguna conexion SSE.
    json.dump({"TV": {"id": "TV", "connected": False, "last_seen": time.time()}},
              open(os.path.join(work, "screens.json"), "w"))

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


def desenlazar(sid="TV"):
    req = urllib.request.Request(
        BASE + "/api/screen-unlink",
        data=json.dumps({"screen": sid}).encode(),
        headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def primer_mensaje_sse(sid="TV", espera=8):
    """Abre /api/events y devuelve el primer 'data:' que mande el servidor."""
    s = socket.create_connection(("127.0.0.1", PORT), timeout=espera)
    try:
        s.sendall(f"GET /api/events?screen={sid} HTTP/1.1\r\nHost: x\r\n"
                  f"Connection: keep-alive\r\n\r\n".encode())
        s.settimeout(espera)
        buf = b""
        fin = time.time() + espera
        while time.time() < fin:
            try:
                trozo = s.recv(4096)
            except socket.timeout:
                break
            if not trozo:
                break
            buf += trozo
            for linea in buf.split(b"\n"):
                if linea.startswith(b"data: "):
                    return linea[6:].decode(errors="replace").strip()
        return ""
    finally:
        s.close()


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def main():
    proc, work = arrancar()
    fallos = 0
    try:
        print("\n  Desenlazar una pantalla APAGADA (sin conexion SSE)\n")

        r = desenlazar("TV")
        fallos += comprobar("el panel dice que se desenlazo", r.get("ok") is True, str(r))

        # Aqui es donde fallaba: no quedaba constancia de nada.
        screens = json.load(open(os.path.join(work, "screens.json"), encoding="utf-8"))
        fallos += comprobar("queda apuntado el desenlace pendiente",
                            screens.get("TV", {}).get("unlink_pending") is True,
                            f"screens.json = {screens.get('TV')}")

        # Y al encender el televisor, lo primero que recibe es la orden de
        # olvidar quien era. Sin esto volvia a servir su playlist tan tranquilo.
        msg = primer_mensaje_sse("TV")
        fallos += comprobar("al volver, lo primero que recibe es 'unlink'",
                            msg.startswith("unlink:"), f"recibio: {msg!r}")

        # Entregada la orden, la marca se borra: si no, un aparato reenlazado a
        # ese mismo nombre se desenlazaria solo una y otra vez.
        #
        # Se espera a que aparezca borrada en vez de mirarlo una sola vez: el
        # cliente lee el mensaje y cierra el socket ANTES de que el servidor
        # termine de guardar screens.json, asi que una lectura inmediata pilla
        # la marca todavia puesta. Es una carrera del test, no del servidor.
        borrada = False
        fin = time.time() + 3
        while time.time() < fin:
            screens = json.load(open(os.path.join(work, "screens.json"), encoding="utf-8"))
            if not screens.get("TV", {}).get("unlink_pending"):
                borrada = True
                break
            time.sleep(0.1)
        fallos += comprobar("y la marca se borra tras entregarla", borrada,
                            f"screens.json = {screens.get('TV')}")

        msg2 = primer_mensaje_sse("TV")
        fallos += comprobar("la segunda vez ya conecta con normalidad",
                            msg2.startswith("connected"), f"recibio: {msg2!r}")

        print("\n  Una pantalla que NO se ha desenlazado no se entera de nada\n")
        msg3 = primer_mensaje_sse("OTRA")
        fallos += comprobar("una pantalla desconocida sigue yendo a emparejar",
                            msg3.startswith("deleted:"), f"recibio: {msg3!r}")

        print("\n  Reenlazar limpia el desenlace pendiente\n")
        # Caso limite: se desenlaza la tele estando apagada y, ANTES de que
        # encienda, se reenlaza otro aparato a ese mismo nombre. El recien
        # llegado no puede llevarse un desenlace que no era suyo.
        desenlazar("TV")
        screens = json.load(open(os.path.join(work, "screens.json"), encoding="utf-8"))
        fallos += comprobar("(preparacion) vuelve a haber desenlace pendiente",
                            screens.get("TV", {}).get("unlink_pending") is True)

        req = urllib.request.Request(
            BASE + "/api/pair-request", data=b"{}",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            codigo = json.loads(r.read())["code"]
        req = urllib.request.Request(
            BASE + "/api/pair-claim",
            data=json.dumps({"code": codigo, "screen_name": "TV",
                             "modo": "reenlazar"}).encode(),
            headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN})
        with urllib.request.urlopen(req, timeout=5) as r:
            claim = json.loads(r.read())
        fallos += comprobar("el reenlace se acepta", claim.get("ok") is True, str(claim))

        screens = json.load(open(os.path.join(work, "screens.json"), encoding="utf-8"))
        fallos += comprobar("y borra el desenlace pendiente",
                            not screens.get("TV", {}).get("unlink_pending"),
                            f"screens.json = {screens.get('TV')}")

        msg4 = primer_mensaje_sse("TV")
        fallos += comprobar("el aparato reenlazado conecta con normalidad",
                            msg4.startswith("connected"), f"recibio: {msg4!r}")
    finally:
        parar(proc, work)

    print()
    if fallos:
        print(f"{fallos} FALLO(S)")
        sys.exit(1)
    print("TODO OK")


if __name__ == "__main__":
    main()
