"""
Comprueba que POST /api/fx-update actualiza las tasas sin destrozar el resto
de la configuración del módulo de divisas.

La extensión de Chrome solo envía {rows, screen_ids} (sidebar.js), así que todo
lo que el usuario haya personalizado en el admin —titulo, moneda base, colores,
mensaje al pie— tiene que sobrevivir a una actualizacion de tasas.

Arranca el servidor en un directorio temporal. Ejecutar:
    python tests/test_fx_update.py
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8093
TOKEN = "token-de-pruebas-0123456789"

# Módulo tal y como lo deja un usuario que lo ha personalizado en el admin.
MODULO = {
    "id": "fx_1", "name": "WU", "type": "fx",
    "title": "WESTERN UNION - TIPOS DE CAMBIO",
    "base_currency": "USD",
    "rows": [{"flag": "ar", "country": "Argentina", "currency": "Peso", "code": "ARS", "rate": "1716"}],
    "duration": 30, "bg": "#ffdd00", "color": "#000000",
    "logo": "/uploads/wu.png",
    "footer_note": "Los tipos pueden variar segun la cantidad a enviar",
}

NUEVAS = [
    {"flag": "ar", "country": "Argentina", "currency": "Peso", "code": "ARS", "rate": "1800"},
    {"flag": "co", "country": "Colombia", "currency": "Peso", "code": "COP", "rate": "4100"},
]


def post(url, payload, token=TOKEN):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-SignalOS-Token": token},
        method="POST")
    return json.load(urllib.request.urlopen(req, timeout=5))


def main():
    work = tempfile.mkdtemp(prefix="signalos_fxupd_")
    for f in ("server.py", "index.html", "admin.html", "login.html",
              "player.html", "pair.html", "sw.js", "config.json"):
        shutil.copy2(os.path.join(SRC, f), work)
    # Token de API para poder pasar la puerta de control del servidor
    json.dump({"api_token": TOKEN, "secret": "s" * 64},
              open(os.path.join(work, "admin.json"), "w"))
    # Contenido con el módulo personalizado, en la librería y en la pantalla
    json.dump({"items": [dict(MODULO)],
               "screens": {"TV": {"mode": "independent", "playlist": [dict(MODULO)]}}},
              open(os.path.join(work, "content.json"), "w"))

    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
    cpath = os.path.join(work, "content.json")
    failed = 0
    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1)
                break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco")
            return 1

        # Exactamente lo que manda la extensión: solo filas y pantalla destino.
        post(base + "/api/fx-update", {"rows": NUEVAS, "screen_ids": ["TV"]})
        item = json.load(open(cpath))["screens"]["TV"]["playlist"][0]

        checks = [
            ("las tasas se actualizan",
             [r["rate"] for r in item["rows"]] == ["1800", "4100"]),
            ("el titulo personalizado sobrevive",
             item["title"] == "WESTERN UNION - TIPOS DE CAMBIO"),
            ("la moneda base sobrevive",
             item["base_currency"] == "USD"),
            ("el mensaje al pie sobrevive",
             item.get("footer_note") == MODULO["footer_note"]),
            ("los colores sobreviven",
             item["bg"] == "#ffdd00" and item["color"] == "#000000"),
            ("el logo sobrevive", item.get("logo") == "/uploads/wu.png"),
            ("la duracion sobrevive", item.get("duration") == 30),
        ]
        for label, ok in checks:
            print(f"  {'ok  ' if ok else 'FALLO'} {label}")
            failed += not ok

        # La copia de la LIBRERIA tiene que quedar sincronizada. Si se queda con
        # las tasas viejas, en cuanto el usuario edite el módulo en el admin y
        # guarde, el admin propaga las suyas y deshace lo que hizo la extensión.
        lib = json.load(open(cpath))["items"][0]
        ok = [r["rate"] for r in lib["rows"]] == ["1800", "4100"]
        print(f"  {'ok  ' if ok else 'FALLO'} la copia de la libreria queda sincronizada")
        failed += not ok
        ok = lib["title"] == "WESTERN UNION - TIPOS DE CAMBIO" and lib["bg"] == "#ffdd00"
        print(f"  {'ok  ' if ok else 'FALLO'} y conserva su propia configuracion")
        failed += not ok

        # ── El orden lo fija el admin, no la extension ─────────────────────
        # El usuario ordena su tablero a mano; una actualizacion de tasas no
        # puede reordenarlo aunque la extension mande las filas en otro orden.
        json.dump({"items": [dict(MODULO, rows=[
                       {"flag": "ar", "country": "Argentina", "currency": "Peso", "code": "ARS", "rate": "1"},
                       {"flag": "co", "country": "Colombia", "currency": "Peso", "code": "COP", "rate": "2"},
                       {"flag": "hn", "country": "Honduras", "currency": "Lempira", "code": "HNL", "rate": "3"}])],
                   "screens": {"TV": {"mode": "independent", "playlist": [dict(MODULO, rows=[
                       {"flag": "ar", "country": "Argentina", "currency": "Peso", "code": "ARS", "rate": "1"},
                       {"flag": "co", "country": "Colombia", "currency": "Peso", "code": "COP", "rate": "2"},
                       {"flag": "hn", "country": "Honduras", "currency": "Lempira", "code": "HNL", "rate": "3"}])]}}},
                  open(cpath, "w"))

        # La extension las manda al reves y con una nueva al principio
        post(base + "/api/fx-update", {"rows": [
            {"flag": "py", "country": "Paraguay", "currency": "Guarani", "code": "PYG", "rate": "6900"},
            {"flag": "hn", "country": "Honduras", "currency": "Lempira", "code": "HNL", "rate": "30,84"},
            {"flag": "ar", "country": "Argentina", "currency": "Peso", "code": "ARS", "rate": "1800"},
            {"flag": "co", "country": "Colombia", "currency": "Peso", "code": "COP", "rate": "4100"},
        ], "screen_ids": ["TV"]})

        filas = json.load(open(cpath))["screens"]["TV"]["playlist"][0]["rows"]
        orden = [r["code"] for r in filas]
        ok = orden[:3] == ["ARS", "COP", "HNL"]
        print(f"  {'ok  ' if ok else 'FALLO'} se conserva el orden del admin -> {orden}")
        failed += not ok

        ok = orden[3:] == ["PYG"]
        print(f"  {'ok  ' if ok else 'FALLO'} las divisas nuevas se anaden al final")
        failed += not ok

        tasas = {r["code"]: r["rate"] for r in filas}
        ok = tasas["ARS"] == "1800" and tasas["COP"] == "4100" and tasas["HNL"] == "30,84"
        print(f"  {'ok  ' if ok else 'FALLO'} y las tasas si se actualizan")
        failed += not ok

        lib = json.load(open(cpath))["items"][0]
        ok = [r["code"] for r in lib["rows"]][:3] == ["ARS", "COP", "HNL"]
        print(f"  {'ok  ' if ok else 'FALLO'} la libreria conserva el mismo orden")
        failed += not ok

        # Restaurar el contenido original para las comprobaciones siguientes
        json.dump({"items": [dict(MODULO)],
                   "screens": {"TV": {"mode": "independent", "playlist": [dict(MODULO)]}}},
                  open(cpath, "w"))

        # Si se envía un título explícito, ese sí debe aplicarse.
        post(base + "/api/fx-update",
             {"rows": NUEVAS, "screen_ids": ["TV"], "title": "OTRO TITULO"})
        item = json.load(open(cpath))["screens"]["TV"]["playlist"][0]
        ok = item["title"] == "OTRO TITULO"
        print(f"  {'ok  ' if ok else 'FALLO'} un titulo explicito si se aplica")
        failed += not ok

        # ── La ventanilla/agente (Ria y similares) llega hasta la pantalla ──
        # Antes sidebar.js la calculaba para elegir la tasa y la tiraba antes de
        # mandarla; ahora tiene que sobrevivir para que el cliente la vea.
        json.dump({"items": [dict(MODULO)],
                   "screens": {"TV": {"mode": "independent", "playlist": [dict(MODULO)]}}},
                  open(cpath, "w"))
        post(base + "/api/fx-update", {"rows": [
            {"flag": "co", "country": "Colombia", "currency": "Peso", "code": "COP",
             "rate": "4100", "agent": "Davivienda"},
        ], "screen_ids": ["TV"]})
        item = json.load(open(cpath))["screens"]["TV"]["playlist"][0]
        ok = item["rows"][0].get("agent") == "Davivienda"
        print(f"  {'ok  ' if ok else 'FALLO'} la ventanilla/agente llega hasta la pantalla")
        failed += not ok

        lib = json.load(open(cpath))["items"][0]
        ok = lib["rows"][0].get("agent") == "Davivienda"
        print(f"  {'ok  ' if ok else 'FALLO'} y tambien a la copia de la libreria")
        failed += not ok

        # Una fila sin agente (cambio normal) no se inventa uno
        post(base + "/api/fx-update", {"rows": [
            {"flag": "ar", "country": "Argentina", "currency": "Peso", "code": "ARS", "rate": "1900"},
        ], "screen_ids": ["TV"]})
        item = json.load(open(cpath))["screens"]["TV"]["playlist"][0]
        fila_ars = next(r for r in item["rows"] if r["code"] == "ARS")
        ok = not fila_ars.get("agent")
        print(f"  {'ok  ' if ok else 'FALLO'} una fila sin ventanilla no se inventa una")
        failed += not ok
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)

    print("TODO OK" if failed == 0 else f"{failed} FALLO(S)")
    return 1 if failed else 0


sys.exit(main())
