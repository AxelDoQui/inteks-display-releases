# Abre la mini-app «InTeks Display» en los televisores LG que lo pidan si no está
# abierta: tras un corte de luz, o si alguien la cerró. LG no deja que una app
# arranque sola al encender el TV, así que lo hace este PC.
#
# Lo lanza una tarea programada cada 5 minutos (la crea instalar-lg.ps1 con
# -Vigilar), con la cuenta del usuario que instaló la mini-app: la clave y los
# datos del TV están en su perfil. Solo toca los televisores de lg_tvs.json con
# "vigilar": true (casilla del panel, Ajustes → Televisores LG). Un TV apagado o
# sin red se salta sin hacer nada. Deja el rastro en vigilar-lg.log.
param([switch]$Quitar)

$ErrorActionPreference = "Stop"
$TAREA = "InTeks Display LG"
$ID = "com.inteks.display"

if ($Quitar) {
    Unregister-ScheduledTask -TaskName $TAREA -Confirm:$false -ErrorAction SilentlyContinue
    exit 0
}

$datos = Join-Path $env:ProgramData "InTeks Display"
$log = Join-Path $datos "vigilar-lg.log"
function Anota($t) {
    try {
        if ((Test-Path $log) -and (Get-Item $log).Length -gt 200KB) { Move-Item $log "$log.old" -Force }
        Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t) -Encoding UTF8
    } catch { }
}

# Si la mini-app se instaló desde el panel, la clave del TV está en esta carpeta y no
# en el perfil de quien ejecuta la tarea (que es SYSTEM).
$casa = Join-Path $datos "lg-home"
if (Test-Path $casa) {
    $env:USERPROFILE = $casa
    $env:HOME = $casa
}

# En el proyecto este script vive en tools\; instalado, junto a lg-tools\.
$raiz = if (Test-Path (Join-Path $PSScriptRoot "lg-tools")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
$herr = Join-Path $raiz "lg-tools"
if (Test-Path (Join-Path $herr "cli\node_modules\.bin\ares-launch.cmd")) {
    $env:PATH = (Join-Path $herr "node") + ";" + (Join-Path $herr "cli\node_modules\.bin") + ";" + $env:PATH
}
if (-not (Get-Command ares-launch -ErrorAction SilentlyContinue)) { Anota "ERROR: no encuentro la herramienta de LG (ares-launch)"; exit 0 }

$arch = Join-Path $datos "lg_tvs.json"
if (-not (Test-Path $arch)) { exit 0 }
try { $tvs = @((Get-Content $arch -Raw -Encoding UTF8 | ConvertFrom-Json).tvs) } catch { Anota "ERROR: lg_tvs.json ilegible"; exit 0 }

function Escucha($ip, $puerto) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $r = $c.BeginConnect($ip, $puerto, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne(2000) -and $c.Connected
        $c.Close()
        return $ok
    } catch { return $false }
}

foreach ($tv in $tvs) {
    if (-not $tv -or $tv.vigilar -ne $true) { continue }
    # Apagado, en reposo o sin red: no hay nada que hacer hasta que conteste.
    if (-not (Escucha $tv.ip 9922)) { continue }
    $ErrorActionPreference = "Continue"
    $abiertas = (ares-launch --device $tv.nombre --running 2>&1 | Out-String)
    if ($abiertas -match [regex]::Escape($ID)) { $ErrorActionPreference = "Stop"; continue }
    if ($abiertas -match "ERR") {
        Anota "$($tv.nombre) ($($tv.ip)): no pude preguntar qué hay abierto: $($abiertas.Trim() -replace '\s+', ' ')"
        $ErrorActionPreference = "Stop"; continue
    }
    $res = (ares-launch --device $tv.nombre $ID 2>&1 | Out-String)
    $ErrorActionPreference = "Stop"
    if ($res -match "Launched") { Anota "$($tv.nombre) ($($tv.ip)): la mini-app no estaba abierta; abierta." }
    else { Anota "$($tv.nombre) ($($tv.ip)): no se pudo abrir: $($res.Trim() -replace '\s+', ' ')" }
}
exit 0
