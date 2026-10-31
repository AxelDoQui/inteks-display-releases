param(
    [string]$AppDir = ""
)

# ─────────────────────────────────────────────────────────────────────────────
#  Para el servidor ANTES de que el instalador copie nada.
#
#  Por que existe: registrar-tarea.ps1 tambien para el servidor, pero se ejecuta
#  en [Run], al FINAL de la instalacion. Los archivos se copian mientras el
#  servidor viejo sigue vivo, y como ahora el interprete de Python va dentro de
#  la propia instalacion, ese proceso tiene agarradas sus DLL:
#
#     vendor\python\libcrypto-3.dll
#     DeleteFile fallo; codigo 5. Acceso denegado.
#
#  El instalador se pisaba a si mismo. Esto se llama desde PrepareToInstall,
#  que corre antes de tocar un solo archivo.
#
#  No falla nunca: si no hay nada que parar, sale en silencio. Un error aqui no
#  puede impedir una instalacion limpia en un equipo donde no habia nada.
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "SilentlyContinue"

$TAREAS = @("InTeks Display", "SignalOS Pro", "SignalOS")

foreach ($t in $TAREAS) {
    schtasks /End /TN "$t" 2>$null | Out-Null
}

# Procesos del servidor. Se identifican de dos formas porque hay dos epocas:
#   - Interprete propio: el .exe vive dentro de la carpeta de instalacion.
#   - Instalaciones antiguas: Python del sistema ejecutando nuestro server.py.
# Matar todos los pythonw del equipo seria inaceptable: el cliente puede tener
# sus propios programas en Python corriendo.
$muertos = 0
Get-Process python, pythonw -ErrorAction SilentlyContinue | ForEach-Object {
    $p = $_
    $suyo = $false

    if ($AppDir -and $p.Path -and $p.Path.StartsWith($AppDir, [StringComparison]::OrdinalIgnoreCase)) {
        $suyo = $true
    }

    if (-not $suyo) {
        $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cl -and ($cl -like "*InTeks Display*server.py*" -or $cl -like "*SignalOS*server.py*")) {
            $suyo = $true
        }
    }

    if ($suyo) {
        try { Stop-Process -Id $p.Id -Force -ErrorAction Stop; $muertos++ } catch {}
    }
}

# La ventana del panel (InTeksDisplay.exe) también agarra su propio .exe: si la
# actualización se lanza desde esa ventana, el instalador no puede sustituirlo
# («DeleteFile falló; código 5»), aborta, deshace lo hecho y deja el servidor
# parado. Pasó el 2026-10-31. Se cierran las de esta instalación; el panel se
# vuelve a abrir con su acceso directo.
Get-Process InTeksDisplay -ErrorAction SilentlyContinue | ForEach-Object {
    if ($AppDir -and $_.Path -and $_.Path.StartsWith($AppDir, [StringComparison]::OrdinalIgnoreCase)) {
        try { Stop-Process -Id $_.Id -Force -ErrorAction Stop; $muertos++ } catch {}
    }
}

# Windows no suelta los handles en el mismo instante en que muere el proceso.
# Sin esta espera, el instalador puede llegar al DeleteFile antes de tiempo y
# fallar igual, que es justo lo que veniamos a evitar.
if ($muertos -gt 0) {
    Start-Sleep -Milliseconds 1500
}

exit 0
