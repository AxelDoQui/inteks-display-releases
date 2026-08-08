# Registra SignalOS Pro como tarea programada al ENCENDER el equipo.
#
# Por qué una tarea y no la clave Run del registro:
#   - Run se dispara al INICIAR SESIÓN. Tras un corte de luz de madrugada el PC
#     arranca y se queda en la pantalla de bloqueo: las pantallas sin contenido
#     hasta que alguien entre.
#   - Una tarea "al iniciar el equipo" corre como SYSTEM, sin sesión, y además
#     Windows la reinicia sola si el proceso se cae.
#
# Y por qué pythonw.exe y no python.exe: pythonw no abre consola. Sin ventana no
# hay nada que alguien pueda cerrar por error en un PC que también se usa para
# otras cosas. El servidor escribe su registro en server.log, dentro de la
# carpeta de datos.
#
# Uso:  registrar-tarea.ps1 -AppDir "C:\Program Files\SignalOS Pro"
#       registrar-tarea.ps1 -Quitar

param(
    [string]$AppDir,
    [switch]$Quitar
)

$TAREA = "SignalOS Pro"

if ($Quitar) {
    schtasks /Delete /TN $TAREA /F 2>$null | Out-Null
    Write-Host "Tarea '$TAREA' eliminada."
    exit 0
}

if (-not $AppDir -or -not (Test-Path (Join-Path $AppDir "server.py"))) {
    Write-Host "ERROR: no se encuentra server.py en '$AppDir'" -ForegroundColor Red
    exit 1
}

# pythonw.exe suele estar junto a python.exe. Se busca por PATH y, si no,
# en las rutas habituales de instalación.
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($py) { $cand = Join-Path (Split-Path $py) "pythonw.exe"; if (Test-Path $cand) { $pythonw = $cand } }
}
if (-not $pythonw) {
    $pythonw = Get-ChildItem "C:\Python*","$env:LOCALAPPDATA\Programs\Python\Python*" -Filter "pythonw.exe" -ErrorAction SilentlyContinue |
               Select-Object -First 1 -ExpandProperty FullName
}
if (-not $pythonw) {
    Write-Host "ERROR: no se encuentra pythonw.exe. Instala Python 3.10+ marcando 'Add to PATH'." -ForegroundColor Red
    exit 1
}

$servidor = Join-Path $AppDir "server.py"
Write-Host "pythonw : $pythonw"
Write-Host "servidor: $servidor"

try {
    $accion = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$servidor`"" -WorkingDirectory $AppDir
    $disparador = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    # Sin límite de duración: es un servidor, no un proceso por lotes. Y que
    # Windows lo reintente si se cae, hasta 3 veces con un minuto de espera.
    $ajustes = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

    Register-ScheduledTask -TaskName $TAREA -Action $accion -Trigger $disparador `
        -Principal $principal -Settings $ajustes -Force -ErrorAction Stop | Out-Null

    Start-ScheduledTask -TaskName $TAREA -ErrorAction SilentlyContinue
    Write-Host "Tarea '$TAREA' registrada y arrancada." -ForegroundColor Green
    exit 0
} catch {
    Write-Host "ERROR registrando la tarea: $_" -ForegroundColor Red
    exit 1
}
