"""
Un archivo de datos dañado no se convierte en «vacío» ni se borra.

Caso real que se evita: un corte de luz deja content.json a medias (o a cero
bytes). Antes, load_json devolvía {} y el siguiente guardado escribía encima: se
perdían todas las pantallas y playlists sin avisar.

Ahora: si no existe, es vacío; si está dañado, se aparta con otro nombre (nunca se
borra) y se recupera de la copia .bak que deja cada guardado.

Ejecutar:
    python tests/test_json_danado.py
"""
import glob, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8115
TOKEN = "token-de-pruebas-0123456789"
BASE = f"http://127.0.0.1:{PORT}"


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def servidor(work):
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(work, "admin.json"), "w"))
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=work,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(40):
        time.sleep(0.25)
        try: urllib.request.urlopen(BASE + "/api/auth-status", timeout=1); return proc
        except Exception: pass
    proc.kill(); raise RuntimeError("el servidor no arranco")


def pedir(path, payload=None):
    req = urllib.request.Request(BASE + path, headers={"X-SignalOS-Token": TOKEN, "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 method="POST" if payload is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def parar(proc):
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()


def main():
    fallos = 0
    bueno = {"items": [{"id": "a", "type": "image", "name": "a"}], "screens": {"TV": {"mode": "independent", "playlist": []}}, "rev": 7}

    print("1. dañado CON copia .bak: se recupera")
    work = tempfile.mkdtemp(prefix="signalos_dan_")
    try:
        open(os.path.join(work, "content.json"), "w").write('{"items": [ {"id": "a"')       # a medias
        json.dump(bueno, open(os.path.join(work, "content.json.bak"), "w"))
        proc = servidor(work)
        try:
            c = pedir("/api/content")
            fallos += comprobar("devuelve lo de la copia", c.get("rev") == 7 and c["items"][0]["id"] == "a", str(c)[:120])
            fallos += comprobar("lo dañado se aparta, no se borra", len(glob.glob(os.path.join(work, "content.json.corrupto-*"))) == 1)
            fallos += comprobar("content.json vuelve a ser valido", json.load(open(os.path.join(work, "content.json")))["rev"] >= 7)
        finally:
            parar(proc)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("2. dañado SIN copia: se aparta y no se pierde")
    work = tempfile.mkdtemp(prefix="signalos_dan_")
    try:
        roto = '{"items": [ {"id": "importante"'
        open(os.path.join(work, "content.json"), "w").write(roto)
        proc = servidor(work)
        try:
            pedir("/api/content")
            apartados = glob.glob(os.path.join(work, "content.json.corrupto-*"))
            fallos += comprobar("el dañado queda guardado aparte", len(apartados) == 1 and open(apartados[0]).read() == roto)
        finally:
            parar(proc)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("3. cada guardado deja .bak de la version anterior")
    work = tempfile.mkdtemp(prefix="signalos_dan_")
    try:
        json.dump(bueno, open(os.path.join(work, "content.json"), "w"))
        proc = servidor(work)
        try:
            actual = pedir("/api/content")
            nuevo = dict(actual); nuevo["items"] = actual["items"] + [{"id": "b", "type": "image", "name": "b"}]
            pedir("/api/content", nuevo)
            bak = json.load(open(os.path.join(work, "content.json.bak")))
            fallos += comprobar("el .bak es la version anterior", [i["id"] for i in bak["items"]] == ["a"], str(bak)[:120])
            fallos += comprobar("content.json tiene la nueva", [i["id"] for i in json.load(open(os.path.join(work, "content.json")))["items"]] == ["a", "b"])
        finally:
            parar(proc)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("4. que no exista sigue siendo normal")
    work = tempfile.mkdtemp(prefix="signalos_dan_")
    try:
        proc = servidor(work)
        try:
            pedir("/api/content")
            fallos += comprobar("sin archivo no se aparta nada", not glob.glob(os.path.join(work, "*.corrupto-*")))
        finally:
            parar(proc)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("OK test_json_danado" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
