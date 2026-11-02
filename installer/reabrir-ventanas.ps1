param(
    [string]$AppDir = ""
)

# ─────────────────────────────────────────────────────────────────────────────
#  Vuelve a abrir las ventanas de InTeks Display que había abiertas antes de
#  actualizar.
#
#  Por qué existe: parar-servidor.ps1 cierra InTeksDisplay.exe (la ventana del
#  panel y la pantalla completa) para que el instalador pueda sustituirlo. Si la
#  actualización la lanzó el servidor desde el panel, nadie las volvía a abrir.
#
#  parar-servidor.ps1 apunta en reabrir.txt cuáles había ("--pantalla" para la
#  pantalla completa, "-" para la ventana del panel). El instalador corre como
#  SYSTEM o en otra sesión, y una ventana abierta desde ahí no se vería: se abre
#  con una tarea de un solo uso que corre como el usuario que tiene la sesión
#  iniciada (el dueño de explorer.exe), y se borra al momento.
#
#  No falla nunca: lo peor que puede pasar es que haya que abrirla a mano.
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "SilentlyContinue"

$lista = Join-Path $env:ProgramData "InTeks Display\reabrir.txt"
if (-not (Test-Path $lista)) { exit 0 }
$pedidas = @(Get-Content $lista -Encoding UTF8 | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() } | Select-Object -Unique)
Remove-Item $lista -Force
if (-not $pedidas.Count) { exit 0 }

$exe = Join-Path $AppDir "InTeksDisplay.exe"
if (-not (Test-Path $exe)) { exit 0 }

# Quién tiene la sesión abierta: el dueño del escritorio (explorer.exe).
$usuario = $null
foreach ($p in @(Get-CimInstance Win32_Process -Filter "Name='explorer.exe'")) {
    $d = Invoke-CimMethod -InputObject $p -MethodName GetOwner
    if ($d -and $d.User) { $usuario = "$($d.Domain)\$($d.User)"; break }
}
if (-not $usuario) { exit 0 }

$n = 0
foreach ($pedida in $pedidas) {
    $n++
    $nombre = "InTeks Display reabrir $n"
    $param = @{ Execute = $exe; WorkingDirectory = $AppDir }
    if ($pedida -eq "--pantalla") { $param.Argument = "--pantalla" }
    $accion = New-ScheduledTaskAction @param
    $quien = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $nombre -Action $accion -Principal $quien -Force | Out-Null
    Start-ScheduledTask -TaskName $nombre
    Start-Sleep -Seconds 3
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
}
exit 0
