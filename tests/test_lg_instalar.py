"""
Instalar la mini-app en un LG desde el panel: POST /api/lg-instalar valida los datos,
lanza el script en segundo plano (aquí uno de mentira, SIGNALOS_LG_SCRIPT) y
GET /api/lg-instalar cuenta cómo va. La passphrase no se ve en lo que cuenta.

Ejecutar:  python tests/test_lg_instalar.py
"""
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8136
TOKEN = "tok-prueba-lg"
CLAVE = "SECRETO123"
ESTATICOS = ("server.py", "index.html", "admin.html", "login.html",
             "player.html", "pair.html", "sw.js", "config.json")
FALSO = r'''param([string]$TV,[string]$Servidor,[string]$Casa,[switch]$Vigilar)
Write-Host "Instalando en $TV con clave $env:INTEKS_LG_PASS servidor=$Servidor casa=$Casa vigilar=$Vigilar"
if ($TV -eq "10.0.0.3") { Start-Sleep -Seconds 4 }
if ($TV -eq "10.0.0.2") { Write-Host "ERROR: no consigo entrar en el TV"; exit 1 }
Write-Host "Listo"
'''
fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def main():
    if sys.platform != "win32":
        print("TODO OK (solo Windows)"); return 0
    html = open(os.path.join(SRC, "admin.html"), encoding="utf-8").read()
    check("abrirInstalarLg" in html and "/api/lg-instalar" in html, "el panel trae el cuadro de instalar")
    iss = open(os.path.join(SRC, "installer", "setup.iss"), encoding="utf-8-sig").read()
    check(re.search(r'instalar-lg\.ps1"; DestDir: "\{app\}"; Flags: ignoreversion\s*\n', iss) is not None,
          "el instalador copia instalar-lg.ps1 siempre")
    check('Name: "{group}\\Instalar la pantalla en un TV LG"' not in iss, "ya no hay acceso en el menú Inicio")

    app = tempfile.mkdtemp(prefix="signalos_lg_")
    datos = tempfile.mkdtemp(prefix="signalos_lgd_")
    for f in ESTATICOS:
        shutil.copy2(os.path.join(SRC, f), app)
    falso = os.path.join(app, "falso-instalar-lg.ps1")
    open(falso, "w", encoding="utf-8-sig").write(FALSO)
    json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(os.path.join(datos, "admin.json"), "w"))
    json.dump({"port": PORT, "port_fallback": 9000}, open(os.path.join(datos, "config.json"), "w"))
    json.dump({"rev": 1, "screens": {}}, open(os.path.join(datos, "content.json"), "w"))
    env = dict(os.environ, SIGNALOS_DATA=datos, SIGNALOS_LG_SCRIPT=falso)
    p = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=app, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{PORT}"
    cab = {"Content-Type": "application/json", "X-SignalOS-Token": TOKEN}

    def pedir(ruta, payload=None):
        r = urllib.request.Request(base + ruta, data=None if payload is None else json.dumps(payload).encode(),
                                   headers=cab, method="GET" if payload is None else "POST")
        try:
            with urllib.request.urlopen(r, timeout=8) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def esperar_fin(segundos=20):
        t0 = time.time()
        while time.time() - t0 < segundos:
            st, d = pedir("/api/lg-instalar")
            if d.get("estado") != "instalando":
                return d
            time.sleep(0.4)
        return d

    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(base + "/api/auth-status", timeout=1); break
            except Exception:
                pass
        else:
            print("FALLO: el servidor no arranco"); return 1

        st, d = pedir("/api/lg-instalar")
        check(st == 200 and d.get("disponible") is True and d.get("estado") == "libre", "empieza libre y disponible")
        sug = d.get("servidor_sugerido", "")
        check(sug.startswith("http://") and sug.endswith(f":{PORT}/") and "localhost" not in sug,
              "propone la dirección del servidor con su puerto")

        bueno = {"ip": "192.168.0.108", "passphrase": CLAVE, "servidor": "192.168.0.90"}
        for malo, que in (({**bueno, "ip": "300.1.1.1"}, "IP fuera de rango"),
                          ({**bueno, "ip": "no-es-ip"}, "IP que no es IP"),
                          ({**bueno, "passphrase": "ab;calc"}, "passphrase con signos"),
                          ({**bueno, "servidor": "x; rm -rf"}, "servidor con signos"),
                          ({**bueno, "passphrase": ""}, "sin passphrase")):
            st, d = pedir("/api/lg-instalar", malo)
            check(st == 400 and d.get("ok") is False, f"rechaza {que}")
        check(pedir("/api/lg-instalar")[1]["estado"] == "libre", "un dato malo no lanza nada")

        st, d = pedir("/api/lg-instalar", {**bueno, "vigilar": True})
        check(st == 200 and d.get("ok") is True, "acepta datos buenos")
        fin = esperar_fin()
        txt = "\n".join(fin.get("lineas", []))
        check(fin.get("estado") == "ok", "termina bien")
        check(CLAVE not in txt and "***" in txt, "la passphrase no sale en lo que cuenta")
        check("192.168.0.108" in txt and "servidor=192.168.0.90" in txt and "lg-home" in txt and "vigilar=True" in txt,
              "el script recibe IP, servidor, carpeta propia y «vigilar»")

        st, d = pedir("/api/lg-instalar", {**bueno, "ip": "10.0.0.2"})
        fin = esperar_fin()
        check(fin.get("estado") == "error" and any(l.startswith("ERROR:") for l in fin.get("lineas", [])),
              "si el script falla, queda en error con su motivo")

        pedir("/api/lg-instalar", {**bueno, "ip": "10.0.0.3"})
        time.sleep(1)
        st, d = pedir("/api/lg-instalar", bueno)
        check(st == 409, "no deja lanzar dos a la vez")
        check(esperar_fin().get("estado") == "ok", "la lenta acaba bien")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
        shutil.rmtree(app, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
