"""
Arranque automatico DE VERDAD (desde 1.0.21).

La casilla del panel guardaba un valor en config.json que nadie leia; el
arranque real lo daba (o no) la tarea programada de Windows, sin ninguna
conexion con esa casilla. Ahora _tarea_autoarranque_estado()/_fijar_autoarranque()
consultan y tocan esa tarea de verdad, via schtasks.exe.

IMPORTANTE: esto NUNCA debe llamar a schtasks.exe de verdad. La tarea se
llama "InTeks Display", el mismo nombre que usaria una instalacion real en
esta maquina -tocarla de verdad en un test podria activar o desactivar el
arranque automatico real de este equipo. subprocess.run se sustituye por una
version de mentira para todo el test.

Ejecutar:  python tests/test_autoarranque.py
"""
import importlib.util, os, shutil, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(AQUI)

fallos = 0


def check(ok, txt):
    global fallos
    print(f"  {'ok  ' if ok else 'FALLO'} {txt}")
    fallos += not ok


class FalsoProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def main():
    datos = tempfile.mkdtemp(prefix="signalos_auto_")
    os.environ["SIGNALOS_DATA"] = datos

    spec = importlib.util.spec_from_file_location("srv", os.path.join(SRC, "server.py"))
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)

    llamadas = []      # cada comando que se "ejecuto", para comprobar que se llamo bien
    cola = []          # respuestas preparadas, una por llamada, en orden

    def falso_run(cmd, **kw):
        llamadas.append(cmd)
        if cola:
            return cola.pop(0)
        return FalsoProc(1, "", "sin respuesta preparada")

    original_run = srv.subprocess.run
    srv.subprocess.run = falso_run

    try:
        # ── _tarea_autoarranque_estado() ─────────────────────────────────────
        cola[:] = [FalsoProc(1, "", "ERROR: The system cannot find the file specified.")]
        e = srv._tarea_autoarranque_estado()
        check(e == {"existe": False, "activa": False}, f"la tarea no existe -> {e}")

        cola[:] = [FalsoProc(0, "Estado:      Listo\n", "")]
        e = srv._tarea_autoarranque_estado()
        check(e["existe"] is True and e["activa"] is True, f"existe y esta activa -> {e}")

        cola[:] = [FalsoProc(0, "Estado:      Deshabilitada\n", "")]
        e = srv._tarea_autoarranque_estado()
        check(e["existe"] is True and e["activa"] is False, f"existe pero deshabilitada -> {e}")

        cola[:] = [FalsoProc(0, "Status:       Disabled\n", "")]
        e = srv._tarea_autoarranque_estado()
        check(e["activa"] is False, "tambien detecta 'Disabled' en ingles")

        # ── _fijar_autoarranque(True), la tarea ya existe: solo se habilita ──
        llamadas.clear()
        cola[:] = [FalsoProc(0, "Estado: Deshabilitada\n", ""),   # la consulta de estado
                   FalsoProc(0, "SUCCESS", "")]                    # el /Change /Enable
        ok, msg = srv._fijar_autoarranque(True)
        check(ok and msg == "", f"activar con la tarea ya creada sale bien -> ({ok!r}, {msg!r})")
        check(llamadas[-1][:4] == ["schtasks", "/Change", "/TN", "InTeks Display"] and
              "/Enable" in llamadas[-1],
              f"llama a schtasks /Change ... /Enable -> {llamadas[-1]}")

        # ── _fijar_autoarranque(True), la tarea NO existe: la crea de cero ───
        llamadas.clear()
        cola[:] = [FalsoProc(1, "", "no existe"),   # la consulta de estado: no existe
                   FalsoProc(0, "Tarea 'InTeks Display' registrada", "")]  # registrar-tarea.ps1
        ok, msg = srv._fijar_autoarranque(True)
        check(ok, f"activar sin tarea previa la crea -> ({ok!r}, {msg!r})")
        check(llamadas[-1][0] == "powershell.exe" and "registrar-tarea.ps1" in llamadas[-1][5] and
              "-AppDir" in llamadas[-1],
              f"llama a registrar-tarea.ps1, no reinventa la busqueda de pythonw.exe -> {llamadas[-1]}")

        # ── _fijar_autoarranque(False), la tarea existe: se deshabilita ──────
        llamadas.clear()
        cola[:] = [FalsoProc(0, "Estado: Listo\n", ""),
                   FalsoProc(0, "SUCCESS", "")]
        ok, msg = srv._fijar_autoarranque(False)
        check(ok, f"desactivar con la tarea presente sale bien -> ({ok!r}, {msg!r})")
        check("/Disable" in llamadas[-1], f"llama a schtasks /Change ... /Disable -> {llamadas[-1]}")

        # ── _fijar_autoarranque(False), la tarea NO existe: no hay nada que hacer ──
        llamadas.clear()
        cola[:] = [FalsoProc(1, "", "no existe")]
        ok, msg = srv._fijar_autoarranque(False)
        check(ok and llamadas == [llamadas[0]],
              "desactivar sin tarea no falla y no intenta tocar nada mas")

        # ── Fallo real (sin permisos de administrador, el caso mas comun) ────
        llamadas.clear()
        cola[:] = [FalsoProc(0, "Estado: Listo\n", ""),
                   FalsoProc(1, "", "ERROR: Access is denied.")]
        ok, msg = srv._fijar_autoarranque(False)
        check(ok is False and "Access is denied" in msg,
              f"un fallo de permisos se informa, no se traga en silencio -> ({ok!r}, {msg!r})")

        # ── Una excepcion (schtasks.exe no encontrado, etc.) tampoco revienta ──
        def revienta(cmd, **kw):
            raise FileNotFoundError("no se encuentra schtasks.exe")
        srv.subprocess.run = revienta
        try:
            ok, msg = srv._fijar_autoarranque(True)
            check(ok is False and "schtasks" in msg, f"una excepcion se convierte en (False, mensaje) -> ({ok!r}, {msg!r})")
        except Exception as e:
            check(False, f"una excepcion en subprocess no puede tumbar la funcion -> {e}")
        srv.subprocess.run = falso_run
    finally:
        srv.subprocess.run = original_run   # nunca dejar el subprocess real sustituido
        shutil.rmtree(datos, ignore_errors=True)

    print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
    return 1 if fallos else 0


sys.exit(main())
