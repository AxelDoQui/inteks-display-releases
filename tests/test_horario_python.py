"""
La version Python de la logica de horario.

El servidor necesita saber si una pantalla DEBERIA estar encendida para no
avisar de una caida a las tres de la madrugada. Esa logica ya existe en
player.html, en JavaScript, y aqui hace falta en Python.

Duplicarla es inevitable -son dos lenguajes- pero que se separen no.
tests/casos-horario.json es el mismo archivo que lee schedule.test.js: si
alguien cambia una implementacion y no la otra, uno de los dos peta.

Ejecutar:  python tests/test_horario_python.py
"""
import importlib.util, json, os, shutil, sys, tempfile, time

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(AQUI)

# server.py crea carpetas y archivos al importarse. Con SIGNALOS_DATA a un
# temporal no toca los datos reales de la maquina de desarrollo.
TMP = tempfile.mkdtemp(prefix="signalos_hor_")
os.environ["SIGNALOS_DATA"] = TMP
spec = importlib.util.spec_from_file_location("srv", os.path.join(SRC, "server.py"))
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


def momento(c):
    """struct_time con el dia de la semana y la fecha que pide el caso."""
    # struct_time usa 0=lunes; el corpus usa 0=domingo, como JavaScript.
    tm_wday = (c["dia"] - 1) % 7
    return time.struct_time((c["anio"], c["mes"], c["dia_mes"],
                             c["hora"], c["minuto"], 0, tm_wday, 1, -1))


def main():
    try:
        corpus = json.load(open(os.path.join(AQUI, "casos-horario.json"), encoding="utf-8"))
        for caso in corpus["casos"]:
            cfg = {"schedule": caso["horario"]} if caso["horario"] is not None else {}
            got = srv.pantalla_activa(cfg, momento(caso["cuando"]))
            check(got == caso["activa"], f"[corpus] {caso['nombre']} -> {got}")

        # always_on manda sobre todo, igual que en el player.
        cfg = {"always_on": True,
               "schedule": {"lunes": {"enabled": False, "start": "08:00", "end": "20:00"}}}
        check(srv.pantalla_activa(cfg, momento(
            {"dia": 1, "hora": 3, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15})) is True,
            "always_on ignora el horario")

        # Una pantalla sin configuracion ninguna se da por encendida: no se
        # puede acusar de caida a algo de lo que no se sabe nada.
        check(srv.pantalla_activa({}, momento(
            {"dia": 1, "hora": 3, "minuto": 0, "anio": 2026, "mes": 6, "dia_mes": 15})) is True,
            "sin configuracion se da por activa")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
