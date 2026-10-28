"""
Copia de seguridad automática: una al día, válida, y con poda.

Se arranca el servidor de verdad en un directorio temporal. El vigilante hace la
copia nada más empezar (no espera al minuto), así que basta con esperar un poco.

Ejecutar:
    python tests/test_copia_automatica.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, zipfile
import urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8111
BASE = f"http://127.0.0.1:{PORT}"
PREFIJO = "InTeks-Display-auto-"


def arrancar(work, ajustes=None):
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    if ajustes:      # despues de copiar la plantilla, o la pisa
        cfg = json.load(open(os.path.join(work, "config.json")))
        cfg.update(ajustes)
        json.dump(cfg, open(os.path.join(work, "config.json"), "w"))
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(BASE + "/api/auth-status", timeout=1)
            return proc
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("el servidor no arranco")


def parar(proc):
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


def esperar(ruta, segundos=8):
    for _ in range(segundos * 4):
        if os.path.exists(ruta): return True
        time.sleep(0.25)
    return False


def main():
    fallos = 0
    work = tempfile.mkdtemp(prefix="signalos_copia_")
    copias = os.path.join(work, "copias")
    hoy = time.strftime("%Y-%m-%d")
    hoy_zip = os.path.join(copias, f"{PREFIJO}{hoy}.zip")
    try:
        json.dump({"items": [{"id": "a"}], "screens": {}, "rev": 3},
                  open(os.path.join(work, "content.json"), "w"))
        # 20 copias viejas (y un archivo ajeno que la poda NO debe tocar)
        os.makedirs(copias)
        for d in range(1, 21):
            open(os.path.join(copias, f"{PREFIJO}2020-01-{d:02d}.zip"), "wb").write(b"viejo")
        open(os.path.join(copias, "mis-notas.txt"), "w").write("no tocar")

        print("1. arranque: hace la copia de hoy y poda")
        proc = arrancar(work)
        try:
            fallos += comprobar("aparece la copia de hoy", esperar(hoy_zip))
            if os.path.exists(hoy_zip):
                with zipfile.ZipFile(hoy_zip) as z:
                    fallos += comprobar("el zip es valido", z.testzip() is None)
                    fallos += comprobar("lleva el contenido", "content.json" in z.namelist()
                                        and json.loads(z.read("content.json"))["rev"] == 3)
                    fallos += comprobar("sin multimedia", not any(n.startswith("uploads/") for n in z.namelist()))
            time.sleep(0.5)
            auto = sorted(f for f in os.listdir(copias) if f.startswith(PREFIJO))
            fallos += comprobar("quedan 14 (la poda respeta el limite)", len(auto) == 14, str(len(auto)))
            fallos += comprobar("la de hoy sobrevive a la poda", f"{PREFIJO}{hoy}.zip" in auto)
            fallos += comprobar("un archivo ajeno no se toca", os.path.exists(os.path.join(copias, "mis-notas.txt")))
            fallos += comprobar("no quedan .tmp", not any(f.endswith(".tmp") for f in os.listdir(copias)))
        finally:
            parar(proc)

        print("2. reinicio el mismo dia: no repite")
        antes = os.path.getmtime(hoy_zip)
        proc = arrancar(work)
        try:
            time.sleep(2)
            fallos += comprobar("la copia de hoy no se rehace", os.path.getmtime(hoy_zip) == antes)
        finally:
            parar(proc)

        print("3. apagada en ajustes: no hace nada")
        os.remove(hoy_zip)
        proc = arrancar(work, {"copia_auto": False})
        try:
            time.sleep(2)
            fallos += comprobar("con copia_auto=false no se crea", not os.path.exists(hoy_zip))
        finally:
            parar(proc)

        print("4. copia externa")
        externa = tempfile.mkdtemp(prefix="signalos_ext_")
        try:
            sitio = os.path.join(externa, "InTeks Display")      # nombre de instalacion por defecto
            os.makedirs(sitio)
            for d in range(1, 21):
                open(os.path.join(sitio, f"{PREFIJO}2020-01-{d:02d}.zip"), "wb").write(b"viejo")
            ext_zip = os.path.join(sitio, f"{PREFIJO}{hoy}.zip")
            proc = arrancar(work, {"copia_externa": externa})
            try:
                fallos += comprobar("aparece la copia en la carpeta externa", esperar(ext_zip))
                if os.path.exists(ext_zip):
                    with zipfile.ZipFile(ext_zip) as z:
                        fallos += comprobar("el zip externo es valido", z.testzip() is None and "content.json" in z.namelist())
                time.sleep(0.5)
                n = len([f for f in os.listdir(sitio) if f.startswith(PREFIJO)])
                fallos += comprobar("la poda externa respeta el limite", n == 14, str(n))
                fallos += comprobar("no quedan .tmp fuera", not any(f.endswith(".tmp") for f in os.listdir(sitio)))
            finally:
                parar(proc)
            # Carpeta que no existe (USB sin enchufar): no falla ni la inventa
            fantasma = os.path.join(externa, "no-existe", "usb")
            proc = arrancar(work, {"copia_externa": fantasma})
            try:
                time.sleep(2.5)
                fallos += comprobar("carpeta inexistente: no se crea", not os.path.exists(os.path.join(externa, "no-existe")))
                try:
                    urllib.request.urlopen(BASE + "/api/auth-status", timeout=2)
                    vivo = True
                except Exception:
                    vivo = False
                fallos += comprobar("y el servidor sigue vivo", vivo)
            finally:
                parar(proc)
        finally:
            shutil.rmtree(externa, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("OK test_copia_automatica" if not fallos else f"{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
