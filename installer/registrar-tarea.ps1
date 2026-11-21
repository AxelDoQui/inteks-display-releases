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
#       registrar-tarea.ps1 -AppDir "..." -SoloFirewall   (solo abrir el puerto)
#       registrar-tarea.ps1 -Quitar

param(
    [string]$AppDir,
    [switch]$Quitar,
    # Solo la regla del cortafuegos, sin tocar la tarea. El instalador lo llama
    # asi SIEMPRE, marque o no el usuario el arranque automatico: sin la regla
    # ninguna pantalla llega al servidor, y eso no puede depender de una casilla
    # que habla de otra cosa.
    [switch]$SoloFirewall
)

$TAREA = "InTeks Display"
# El producto se llamaba SignalOS Pro. Su tarea hay que borrarla siempre, o
# quedarian dos arrancando servidores que se pelean por el puerto 80.
$TAREAS_VIEJAS = @("SignalOS Pro", "SignalOS")
$REGLA = "InTeks Display (HTTP)"

function AbrirCortafuegos($dir) {
    # Sin esta regla, el servidor funciona perfectamente en el propio PC y NO
    # responde a ningun otro aparato: el televisor o la tablet se quedan
    # cargando indefinidamente, sin error ni mensaje, porque un paquete
    # descartado no contesta nada. Era el fallo mas caro de diagnosticar de
    # todo el producto, y hasta ahora habia que arreglarlo a mano en cada
    # instalacion. El instalador ya corre elevado aqui: es el momento.
    #
    # -Profile Any, y no Private. Windows clasifica como PUBLICA cualquier red
    # nueva que no se marque a mano, y una regla de perfil Privado no se aplica
    # en una red Publica: la instalacion parecia correcta y seguia sin
    # funcionar. Peor aun, Windows puede reclasificar la red mas adelante y
    # tirar las pantallas sin que nadie haya tocado nada. Abre solo los puertos
    # de este programa, y el panel sigue pidiendo contrasena.
    $puertos = @(80, 9000)
    $cfg = Join-Path $env:ProgramData "InTeks Display\config.json"
    if (-not (Test-Path $cfg) -and $dir) { $cfg = Join-Path $dir "config.json" }
    if (Test-Path $cfg) {
        try {
            $c = Get-Content $cfg -Raw | ConvertFrom-Json
            # -as [int] y no -is [int]: ConvertFrom-Json puede devolver Int64,
            # y con -is se descartaban los puertos leidos sin decir nada.
            $leidos = @($c.port, $c.port_fallback) | ForEach-Object { $_ -as [int] } |
                      Where-Object { $_ -gt 0 -and $_ -le 65535 }
            if ($leidos) { $puertos = $leidos }
        } catch {}   # config ilegible: valen los de por defecto, no se aborta la instalacion
    }
    try {
        Get-NetFirewallRule -DisplayName $REGLA -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName $REGLA -Direction Inbound -Protocol TCP `
            -LocalPort $puertos -Action Allow -Profile Any -ErrorAction Stop | Out-Null
        Write-Host "Cortafuegos: abierto el puerto $($puertos -join ' y ') para las pantallas." -ForegroundColor Green
    } catch {
        # Que no se pueda abrir el puerto no puede impedir instalar: en local
        # funciona igual, y el manual explica como crear la regla a mano.
        Write-Host "AVISO: no se pudo crear la regla del cortafuegos ($_)." -ForegroundColor Yellow
        Write-Host "       Las pantallas no veran el servidor hasta crearla. Ver DOCS.md." -ForegroundColor Yellow
    }
}

if ($Quitar) {
    foreach ($t in @($TAREA) + $TAREAS_VIEJAS) { schtasks /Delete /TN $t /F 2>$null | Out-Null }
    Get-NetFirewallRule -DisplayName $REGLA -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    Write-Host "Tarea '$TAREA' eliminada."
    exit 0
}

if ($SoloFirewall) {
    AbrirCortafuegos $AppDir
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

# Antes de registrar la tarea, y pase lo que pase con ella: un servidor que
# arranca pero al que no llega ninguna pantalla no sirve de nada, y al reves
# tampoco. Son dos cosas independientes y ninguna debe llevarse a la otra por
# delante si falla.
#
# Durante la instalacion esto se ejecuta dos veces —el instalador ya llamo con
# -SoloFirewall— y da igual: la funcion borra la regla antes de crearla, asi
# que es repetible. Se deja aqui para que quien repare una instalacion a mano
# lanzando este script se lleve las dos cosas y no solo una.
AbrirCortafuegos $AppDir

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
