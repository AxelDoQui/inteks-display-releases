# Registra InTeks Display como tarea programada al ENCENDER el equipo.
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
# Uso:  registrar-tarea.ps1 -AppDir "C:\Program Files\InTeks Display"
#       registrar-tarea.ps1 -Quitar

param(
    [string]$AppDir,
    [switch]$Quitar
)

$TAREA = "InTeks Display"
# El producto se llamaba SignalOS Pro. Su tarea hay que borrarla siempre, o
# quedarian dos arrancando servidores que se pelean por el puerto 80.
$TAREAS_VIEJAS = @("SignalOS Pro", "SignalOS")

if ($Quitar) {
    foreach ($t in @($TAREA) + $TAREAS_VIEJAS) { schtasks /Delete /TN $t /F 2>$null | Out-Null }
    Write-Host "Tarea '$TAREA' eliminada."
    exit 0
}

# Limpieza de la version anterior, antes de registrar la nueva
foreach ($t in $TAREAS_VIEJAS) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        schtasks /Delete /TN $t /F 2>$null | Out-Null
        Write-Host "Tarea antigua '$t' eliminada."
    }
}
# Y cualquier servidor de la instalacion anterior que siga vivo: si no, ocupa
# el puerto 80 y el nuevo nunca llega a arrancar ahi.
Get-Process python,pythonw -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction Stop).CommandLine
        if ($cl -like "*SignalOS*server.py*") {
            Write-Host "Cerrando servidor anterior (PID $($_.Id))."
            Stop-Process -Id $_.Id -Force
        }
    } catch {}
}

if (-not $AppDir -or -not (Test-Path (Join-Path $AppDir "server.py"))) {
    Write-Host "ERROR: no se encuentra server.py en '$AppDir'" -ForegroundColor Red
    exit 1
}

# El interprete que viene DENTRO de la instalacion manda sobre cualquier otro.
# Asi el servidor no depende de lo que el cliente tenga instalado ni de que
# alguien actualice o desinstale "su" Python un martes por la tarde y se lleve
# por delante el escaparate.
$pythonw = $null
$propio = Join-Path $AppDir "vendor\python\pythonw.exe"
if (Test-Path $propio) {
    $pythonw = $propio
    Write-Host "Usando el Python incluido en la instalacion."
}
# Respaldo para instalaciones antiguas, anteriores a incluir el interprete.
if (-not $pythonw) {
    $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $pythonw) {
    $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($py) { $cand = Join-Path (Split-Path $py) "pythonw.exe"; if (Test-Path $cand) { $pythonw = $cand } }
}
if (-not $pythonw) {
    $pythonw = Get-ChildItem "C:\Python*","$env:LOCALAPPDATA\Programs\Python\Python*" -Filter "pythonw.exe" -ErrorAction SilentlyContinue |
               Select-Object -First 1 -ExpandProperty FullName
}
if (-not $pythonw) {
    Write-Host "ERROR: no se encuentra pythonw.exe ni el interprete incluido en '$propio'." -ForegroundColor Red
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

    # IMPRESCINDIBLE al actualizar: Python carga el .py en memoria al arrancar,
    # así que copiar archivos nuevos NO cambia un proceso que ya está corriendo.
    # Sin este reinicio, tras actualizar se quedaba sirviendo el HTML nuevo
    # (que se lee del disco en cada peticion) con el codigo viejo en memoria:
    # endpoints inexistentes, 401 raros y ningun mensaje que lo explicara.
    # Start-ScheduledTask no hace nada si la tarea ya corre: hay que pararla.
    Stop-ScheduledTask -TaskName $TAREA -ErrorAction SilentlyContinue
    Get-Process pythonw -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like "*python*" } |
        ForEach-Object {
            # Solo los que estén sirviendo ESTE server.py, no otros pythonw
            try { if ((Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like "*$($AppDir.Replace('\','\\'))*") { Stop-Process -Id $_.Id -Force } } catch {}
        }
    Start-Sleep -Milliseconds 800
    Start-ScheduledTask -TaskName $TAREA -ErrorAction SilentlyContinue

    Write-Host "Tarea '$TAREA' registrada y (re)arrancada." -ForegroundColor Green
    exit 0
} catch {
    Write-Host "ERROR registrando la tarea: $_" -ForegroundColor Red
    exit 1
}
