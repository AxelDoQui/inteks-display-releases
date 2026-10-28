# Tarea programada «InTeks Display Pantalla»: mantiene abierta la pantalla del
# mini PC del televisor (InTeksDisplay.exe --pantalla).
#
# Por qué una tarea y no solo el acceso directo de Inicio: al actualizar, el
# instalador cierra la ventana para sustituir sus archivos y nadie la vuelve a
# abrir hasta el siguiente inicio de sesión. Con esta tarea, al iniciar sesión Y
# cada 5 minutos se intenta abrir; si ya está abierta no pasa nada (la app solo
# admite una instancia), y si se cerró, vuelve sola.
#
# Corre en la sesión del usuario (con pantalla), no como SYSTEM: una ventana
# abierta desde la sesión de servicios no se vería.
#
# Uso:  registrar-pantalla.ps1 -AppDir "C:\Program Files\InTeks Display" -Usuario "Tienda"
#       registrar-pantalla.ps1 -Quitar
param(
    [string]$AppDir,
    [string]$Usuario,
    [switch]$Quitar
)
$ErrorActionPreference = "Stop"
$TAREA = "InTeks Display Pantalla"

if ($Quitar) {
    Unregister-ScheduledTask -TaskName $TAREA -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}

$exe = Join-Path $AppDir "InTeksDisplay.exe"
if (-not (Test-Path $exe)) { Write-Host "ERROR: no existe $exe"; exit 1 }
if (-not $Usuario) { $Usuario = "$env:USERDOMAIN\$env:USERNAME" }

# Una actualización desde el panel la lanza el servidor, que corre como SYSTEM:
# aquí «el usuario» sería SYSTEM, que no tiene pantalla. La tarea que ya hay (de
# la instalación hecha por una persona) se queda como está.
if ($Usuario -match '(^|\\)SYSTEM$|^NT AUTHORITY') {
    Write-Host "Instalación sin usuario con sesión: se mantiene la tarea existente."
    exit 0
}

$accion = New-ScheduledTaskAction -Execute $exe -Argument "--pantalla" -WorkingDirectory $AppDir
$inicio = New-ScheduledTaskTrigger -AtLogOn -User $Usuario
$cada5  = New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$inicio.Repetition = $cada5.Repetition
$quien  = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive -RunLevel Limited
$ajustes = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TAREA -Action $accion -Trigger $inicio `
    -Principal $quien -Settings $ajustes -Force | Out-Null
Write-Host "Tarea '$TAREA' registrada para $Usuario."
