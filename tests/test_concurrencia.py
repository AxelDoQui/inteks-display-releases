"""
Dos ordenadores usando el mismo servidor sin pisarse.

Estos fallos viven en la concurrencia real de ThreadingHTTPServer: un simulacro
no los reproduce. Se arranca el servidor de verdad en un directorio temporal y
se le habla por HTTP desde varios hilos a la vez.

La prueba 6 se escribió ANTES del arreglo y se vio fallar: de 20 subidas
simultaneas sobrevivian 6. Si algun dia vuelve a pasar sin el guardian, es que
esta mal escrita.

Ejecutar:
    python tests/test_concurrencia.py
"""
import base64, json, os, shutil, subprocess, sys, tempfile, threading, time
import urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8107          # libre: los demas usan 8086, 8090, 8093, 8097-8101, 8103-8106
TOKEN = "token-de-pruebas-0123456789"
BASE = f"http://127.0.0.1:{PORT}"

MODULO_FX = {"id": "fx_1", "name": "WU", "type": "fx", "title": "TIPOS DE CAMBIO",
             "base_currency": "USD", "duration": 30,
             "rows": [{"flag": "ar", "country": "Argentina", "currency": "Peso",
                       "code": "ARS", "rate": "1716"}]}

CONTENIDO_BASE = {
    "items": [dict(MODULO_FX)],
    "screens": {"TV": {"mode": "independent", "playlist": [dict(MODULO_FX)]}},
    "rev": 0,
}


def peticion(url, payload=None, metodo="GET", token=TOKEN):
    """Devuelve (codigo, cuerpo_json). No lanza en los 4xx: aqui un 409 es un
    resultado que se afirma, no una averia."""
    datos = json.dumps(payload).encode() if payload is not None else None
    cabeceras = {"Content-Type": "application/json"}
    if token: cabeceras["X-SignalOS-Token"] = token
    req = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode()
        try: return e.code, json.loads(cuerpo or "{}")
        except ValueError: return e.code, {}


def rev_actual():
    _, cuerpo = peticion(BASE + "/api/content")
    return cuerpo.get("rev")


def arrancar(contenido_inicial):
    """Servidor real en un directorio temporal. Devuelve (proceso, dir, ruta_content)."""
    work = tempfile.mkdtemp(prefix="signalos_concur_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    # Token de API para pasar la puerta de control del servidor
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(work, "admin.json"), "w"))
    json.dump(contenido_inicial, open(os.path.join(work, "content.json"), "w"))

    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(BASE + "/api/auth-status", timeout=1)
            return proc, work, os.path.join(work, "content.json")
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("el servidor no arranco")


def parar(proc, work):
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    shutil.rmtree(work, ignore_errors=True)


def comprobar(etiqueta, condicion, detalle=""):
    print(f"  {'ok  ' if condicion else 'FALLO'} {etiqueta}"
          + (f"   [{detalle}]" if detalle and not condicion else ""))
    return 0 if condicion else 1


# ─────────────────────────────────────────────────────────────────────────────
#  1. Todos los caminos de escritura suben el contador
#
#  Si un camino se olvida de subirlo, la proteccion tiene un agujero justo por
#  ahi: dos paneles podrian creerse al dia despues de que uno escribiera.
# ─────────────────────────────────────────────────────────────────────────────
def prueba_1_todos_suben_rev():
    fallos = 0
    r0 = rev_actual()

    _, cuerpo = peticion(BASE + "/api/content",
                         {"items": [dict(MODULO_FX)], "rev": r0}, metodo="POST")
    r1 = rev_actual()
    fallos += comprobar("/api/content sube rev", r1 == r0 + 1, f"{r0} -> {r1}")

    peticion(BASE + "/api/upload", {"name": "x.png", "type": "image",
                                    "data": base64.b64encode(b"x").decode()}, metodo="POST")
    r2 = rev_actual()
    fallos += comprobar("/api/upload sube rev", r2 == r1 + 1, f"{r1} -> {r2}")

    peticion(BASE + "/api/fx-update", {"rows": [
        {"flag": "co", "country": "Colombia", "currency": "Peso",
         "code": "COP", "rate": "4100"}], "screen_ids": ["TV"]}, metodo="POST")
    r3 = rev_actual()
    fallos += comprobar("/api/fx-update sube rev", r3 == r2 + 1, f"{r2} -> {r3}")

    peticion(BASE + "/api/delete", {"id": "fx_1"}, metodo="POST")
    r4 = rev_actual()
    fallos += comprobar("/api/delete sube rev", r4 == r3 + 1, f"{r3} -> {r4}")
    return fallos


# ─────────────────────────────────────────────────────────────────────────────
#  2 y 3. El caso normal sigue funcionando; el caso de las tasas se rechaza
# ─────────────────────────────────────────────────────────────────────────────
def prueba_2_rev_correcto_guarda():
    r = rev_actual()
    codigo, _ = peticion(BASE + "/api/content",
                         {"items": [{"id": "a", "name": "A", "type": "image"}], "rev": r},
                         metodo="POST")
    return comprobar("guardar con el rev correcto devuelve 200", codigo == 200, f"codigo {codigo}")


def prueba_3_rev_viejo_rechaza(cpath):
    """El escenario real: el panel del PC1 no se entero de las tasas del PC2 y
    manda su copia caducada. Tiene que rebotar sin escribir nada."""
    fallos = 0
    r = rev_actual()
    antes = json.load(open(cpath))

    codigo, cuerpo = peticion(BASE + "/api/content",
                              {"items": [], "screens": {}, "rev": r - 1}, metodo="POST")
    fallos += comprobar("guardar con un rev viejo devuelve 409", codigo == 409, f"codigo {codigo}")
    fallos += comprobar("el 409 dice rev_conflict",
                        cuerpo.get("error") == "rev_conflict", str(cuerpo))
    fallos += comprobar("el 409 devuelve el rev bueno para que el panel se sincronice",
                        cuerpo.get("rev") == r, str(cuerpo))

    despues = json.load(open(cpath))
    fallos += comprobar("no se ha escrito nada: el contenido esta intacto", antes == despues)
    return fallos


def prueba_4_sin_rev_rechaza():
    """Una pestaña con admin.html cacheado de antes de esta version no puede
    colarse por la puerta de atras saltandose la comprobacion."""
    fallos = 0
    codigo, cuerpo = peticion(BASE + "/api/content",
                              {"items": [], "screens": {}}, metodo="POST")
    fallos += comprobar("guardar sin rev devuelve 409", codigo == 409, f"codigo {codigo}")
    fallos += comprobar("el 409 dice rev_stale_client para que el panel recargue",
                        cuerpo.get("error") == "rev_stale_client", str(cuerpo))
    return fallos


# ─────────────────────────────────────────────────────────────────────────────
#  5. El aviso que faltaba
#
#  fx-update notificaba pantalla por pantalla y 'admin' nunca esta en esa lista,
#  asi que el panel se quedaba con las tasas viejas sin saberlo.
# ─────────────────────────────────────────────────────────────────────────────
def prueba_5_fx_update_avisa_al_panel():
    recibido = []

    def escuchar():
        try:
            req = urllib.request.Request(BASE + "/api/events?screen=admin",
                                         headers={"X-SignalOS-Token": TOKEN})
            with urllib.request.urlopen(req, timeout=12) as r:
                for linea in r:
                    texto = linea.decode(errors="ignore").strip()
                    if texto.startswith("data:"):
                        recibido.append(texto)
                        if "update:admin" in texto:
                            return
        except Exception:
            pass

    oyente = threading.Thread(target=escuchar, daemon=True)
    oyente.start()
    time.sleep(1.5)          # que le de tiempo a registrarse en sse_clients

    peticion(BASE + "/api/fx-update", {"rows": [
        {"flag": "hn", "country": "Honduras", "currency": "Lempira",
         "code": "HNL", "rate": "30"}], "screen_ids": ["TV"]}, metodo="POST")

    oyente.join(timeout=8)
    ok = any("update:admin" in m for m in recibido)
    return comprobar("fx-update avisa al panel por SSE (update:admin)", ok,
                     f"recibido: {recibido}")


# ─────────────────────────────────────────────────────────────────────────────
#  5b. /api/screens/config tenia el mismo agujero que las tasas (5), y peor:
#  ademas de no avisar al panel, escribia sin comprobar el rev. saveScreensConfig()
#  manda una foto COMPLETA de content["screens"] (crear pantalla, asignar
#  playlist, videowall...), asi que sin el rev un panel con datos viejos borra
#  en silencio lo que guardo otro.
# ─────────────────────────────────────────────────────────────────────────────
def prueba_5b_screens_config_rechaza_rev_viejo(cpath):
    fallos = 0
    r = rev_actual()
    antes = json.load(open(cpath))

    codigo, cuerpo = peticion(BASE + "/api/screens/config",
                              {"rev": r - 1, "screens": {"TV": {"mode": "independent",
                                                                 "playlist": []}}},
                              metodo="POST")
    fallos += comprobar("/api/screens/config con rev viejo devuelve 409", codigo == 409,
                        f"codigo {codigo}")
    fallos += comprobar("el 409 dice rev_conflict",
                        cuerpo.get("error") == "rev_conflict", str(cuerpo))

    despues = json.load(open(cpath))
    fallos += comprobar("no se ha escrito nada: el contenido esta intacto", antes == despues)

    codigo, cuerpo = peticion(BASE + "/api/screens/config",
                              {"screens": {"TV": {"mode": "independent", "playlist": []}}},
                              metodo="POST")
    fallos += comprobar("/api/screens/config sin rev devuelve 409", codigo == 409,
                        f"codigo {codigo}")
    fallos += comprobar("el 409 dice rev_stale_client",
                        cuerpo.get("error") == "rev_stale_client", str(cuerpo))
    return fallos


def prueba_5c_screens_config_avisa_al_panel():
    recibido = []

    def escuchar():
        try:
            req = urllib.request.Request(BASE + "/api/events?screen=admin",
                                         headers={"X-SignalOS-Token": TOKEN})
            with urllib.request.urlopen(req, timeout=12) as r:
                for linea in r:
                    texto = linea.decode(errors="ignore").strip()
                    if texto.startswith("data:"):
                        recibido.append(texto)
                        if "update:admin" in texto:
                            return
        except Exception:
            pass

    oyente = threading.Thread(target=escuchar, daemon=True)
    oyente.start()
    time.sleep(1.5)

    r = rev_actual()
    peticion(BASE + "/api/screens/config",
             {"rev": r, "screens": {"TV": {"mode": "independent", "playlist": []}}},
             metodo="POST")

    oyente.join(timeout=8)
    ok = any("update:admin" in m for m in recibido)
    return comprobar("/api/screens/config avisa al panel por SSE (update:admin)", ok,
                     f"recibido: {recibido}")


# ─────────────────────────────────────────────────────────────────────────────
#  6. La carrera entre leer y escribir
#
#  load_json y save_json cierran cada uno su propio file_lock, pero el hueco
#  entre ambos no estaba protegido. Veinte hilos subiendo a la vez leian la
#  misma foto de content.json y se sobrescribian unos a otros.
#
#  Medido antes del arreglo: sobrevivian 6 de 20.
# ─────────────────────────────────────────────────────────────────────────────
def prueba_6_subidas_simultaneas(cpath):
    N = 20
    antes = len(json.load(open(cpath)).get("items", []))
    listos = threading.Barrier(N)
    errores = []

    def subir(i):
        try:
            listos.wait(timeout=10)      # que salgan todos a la vez
            codigo, _ = peticion(BASE + "/api/upload", {
                "name": f"foto{i:02d}.png",
                "type": "image",
                "data": base64.b64encode(f"contenido-{i}".encode()).decode(),
            }, metodo="POST")
            if codigo != 200:
                errores.append(f"hilo {i}: codigo {codigo}")
        except Exception as e:
            errores.append(f"hilo {i}: {e}")

    hilos = [threading.Thread(target=subir, args=(i,)) for i in range(N)]
    for h in hilos: h.start()
    for h in hilos: h.join(timeout=30)

    items = json.load(open(cpath)).get("items", [])
    ok = len(items) == antes + N and not errores
    return comprobar(f"{N} subidas simultaneas: no se pierde ninguna",
                     ok, f"habia {antes}, esperaba {antes + N}, hay {len(items)}; {errores[:3]}")


# ─────────────────────────────────────────────────────────────────────────────
#  7. La migracion desde 1.0.9
#
#  Sin ella el panel entra en bucle de recargas y queda inutilizable en TODA
#  instalacion actualizada: carga sin rev, guarda sin rev, recibe 409
#  rev_stale_client, recarga, y vuelve a empezar.
# ─────────────────────────────────────────────────────────────────────────────
def prueba_7_migracion_desde_1_0_9():
    fallos = 0
    # Exactamente lo que hay en el disco de una instalacion de 1.0.9: sin rev.
    legado = {"items": [dict(MODULO_FX)],
              "screens": {"TV": {"mode": "independent", "playlist": []}}}
    proc, work, cpath = arrancar(legado)
    try:
        r = rev_actual()
        fallos += comprobar("al arrancar sobre un content.json sin rev, el GET ya lo trae",
                            r is not None, f"rev={r}")

        codigo, _ = peticion(BASE + "/api/content",
                             {"items": [dict(MODULO_FX)], "rev": r}, metodo="POST")
        fallos += comprobar("y el primer guardado del panel pasa: no hay bucle de recargas",
                            codigo == 200, f"codigo {codigo}")

        en_disco = json.load(open(cpath))
        fallos += comprobar("el archivo migrado conserva el contenido de antes",
                            len(en_disco.get("items", [])) == 1)
    finally:
        parar(proc, work)
    return fallos


def main():
    fallos = 0
    proc, work, cpath = arrancar(dict(CONTENIDO_BASE))
    try:
        fallos += prueba_1_todos_suben_rev()
        fallos += prueba_2_rev_correcto_guarda()
        fallos += prueba_3_rev_viejo_rechaza(cpath)
        fallos += prueba_4_sin_rev_rechaza()
        fallos += prueba_5_fx_update_avisa_al_panel()
        fallos += prueba_5b_screens_config_rechaza_rev_viejo(cpath)
        fallos += prueba_5c_screens_config_avisa_al_panel()
        fallos += prueba_6_subidas_simultaneas(cpath)
    finally:
        parar(proc, work)

    fallos += prueba_7_migracion_desde_1_0_9()

    print()
    print("  TODO OK" if not fallos else f"  {fallos} FALLO(S)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
