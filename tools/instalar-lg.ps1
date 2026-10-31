# Instala la mini-app «InTeks Display» en un televisor LG con webOS.
#
# Por qué existe: el navegador de los LG cierra la página cada ~2 minutos. Esta
# mini-app (carpeta webos\) abre el reproductor desde el entorno de apps del TV,
# donde eso no pasa. Solo pide tres datos.
#
# Antes, en el TV: instalar «Developer Mode» (LG Content Store), iniciar sesión con
# la cuenta de desarrollador de LG, activar «Dev Mode Status» y «Key Server».
# Ahí salen la IP del TV y la Passphrase. Este PC y el TV deben estar en la
# misma red. Las herramientas (Node.js y la de LG) vienen con la app si se marcó
# «Herramientas para televisores LG» al instalar; si no, hace falta Node.js.
#
# Uso:
#   powershell -File tools\instalar-lg.ps1 -TV 192.168.0.108 -Passphrase 6DC7B4 -Servidor 192.168.0.90
#   -Servidor es la IP del PC con InTeks Display (o su dirección completa, http://...).
#   Sin parámetros los pregunta (es lo que hace el acceso directo del menú Inicio).
param(
    [string]$TV,
    [string]$Passphrase,
    [string]$Servidor,
    [string]$Nombre = "tienda-lg",
    [switch]$Vigilar
)
$ErrorActionPreference = "Stop"
# En el proyecto este script vive en tools\; instalado, junto a webos\ y lg-tools\.
$raiz = if (Test-Path (Join-Path $PSScriptRoot "webos")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
$app = Join-Path $raiz "webos"
$ID = "com.inteks.display"

function Falla($txt) { Write-Host "ERROR: $txt" -ForegroundColor Red; exit 1 }

if (-not $TV) { $TV = Read-Host "IP del televisor (sale en la app Developer Mode del TV)" }
$preguntar = -not $Passphrase
if (-not $Passphrase) { $Passphrase = Read-Host "Passphrase (la misma pantalla de Developer Mode)" }
if (-not $Servidor) { $Servidor = Read-Host "IP del PC con InTeks Display (el servidor)" }
if (-not $TV -or -not $Passphrase -or -not $Servidor) { Falla "faltan datos." }

# La dirección del servidor, con http:// y barra final.
$url = $Servidor.Trim()
if ($url -notmatch '^https?://') { $url = "http://$url" }
if (-not $url.EndsWith("/")) { $url += "/" }

if (-not (Test-Path (Join-Path $app "index.html"))) { Falla "no encuentro la carpeta webos\ del proyecto." }

# Las herramientas que trae la app van primero: así no hace falta tener Node en el PC.
$herr = Join-Path $raiz "lg-tools"
$instaladorHerr = Join-Path $raiz "installer\instalar-herramientas-lg.ps1"
if (-not (Test-Path $instaladorHerr)) { $instaladorHerr = Join-Path $raiz "instalar-herramientas-lg.ps1" }
if (-not (Test-Path (Join-Path $herr "cli\node_modules\.bin\ares-install.cmd")) -and (Test-Path $instaladorHerr) -and
    -not (Get-Command ares-install -ErrorAction SilentlyContinue)) {
    # Se marcó la casilla pero la descarga falló (sin internet, por ejemplo): reintentar.
    Write-Host "Preparando las herramientas para LG (descarga, unos minutos)..." -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File $instaladorHerr -AppDir $raiz
}
if (Test-Path (Join-Path $herr "cli\node_modules\.bin\ares-install.cmd")) {
    $env:PATH = (Join-Path $herr "node") + ";" + (Join-Path $herr "cli\node_modules\.bin") + ";" + $env:PATH
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Falla "faltan las herramientas para LG. Reinstala InTeks Display marcando «Herramientas para televisores LG», o instala Node.js (https://nodejs.org) y vuelve a ejecutar esto."
}

if (-not (Get-Command ares-install -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando la herramienta de LG (una sola vez)..." -ForegroundColor Cyan
    npm install -g @webos-tools/cli
    if ($LASTEXITCODE -ne 0) { Falla "no se pudo instalar la herramienta de LG (npm)." }
}

# El servidor tiene que contestar desde aquí: si no, el TV tampoco lo verá.
try { Invoke-WebRequest ($url + "api/auth-status") -UseBasicParsing -TimeoutSec 6 | Out-Null }
catch { Write-Host "AVISO: este PC no consigue hablar con $url. Se instala igual, pero comprueba la IP del servidor." -ForegroundColor Yellow }

# Copia de trabajo con la dirección puesta: la carpeta del proyecto no se toca.
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("inteks_lg_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    Copy-Item "$app\*" $tmp -Recurse
    $idx = Join-Path $tmp "index.html"
    $txt = [IO.File]::ReadAllText($idx)
    $nuevo = [regex]::Replace($txt, 'var SERVIDOR = "[^"]*";', ('var SERVIDOR = "' + $url + '";'))
    if ($nuevo -eq $txt -and $txt -notmatch [regex]::Escape($url)) { Falla "no pude poner la dirección del servidor en la mini-app." }
    [IO.File]::WriteAllText($idx, $nuevo, (New-Object Text.UTF8Encoding($false)))

    # Vincular el TV: se da de alta, se baja su clave y se le pone la passphrase.
    $lista = ares-setup-device --list 2>&1 | Out-String
    $info = "{'host':'$TV','port':'9922','username':'prisoner'}"
    if ($lista -match "(?m)^$([regex]::Escape($Nombre))\s") { ares-setup-device --modify $Nombre --info $info | Out-Null }
    else { ares-setup-device --add $Nombre --info $info | Out-Null }
    # «Key Server» del TV se apaga solo pasado un rato: la clave se baja con él
    # encendido. Si ya se bajó antes para este TV, vale la que hay.
    $clave = Join-Path $HOME ".ssh\${Nombre}_webos"
    $ErrorActionPreference = "Continue"
    $Passphrase | ares-novacom --device $Nombre --getkey 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    if (-not (Test-Path $clave)) {
        Falla "no pude bajar la clave del TV. En el TV, abre «Developer Mode» y comprueba que «Key Server» esté en ON (se apaga solo al rato), y vuelve a ejecutar esto."
    }
    ares-setup-device --modify $Nombre --info "{'privateKey':'${Nombre}_webos','passphrase':'$Passphrase'}" | Out-Null
    ares-device -i --device $Nombre 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Falla "no consigo entrar en el TV ($TV). Revisa que 'Key Server' esté en ON, la IP y la passphrase." }

    Write-Host "Empaquetando e instalando en $TV..." -ForegroundColor Cyan
    $salida = Join-Path $tmp "_ipk"
    New-Item -ItemType Directory -Path $salida | Out-Null
    ares-package $tmp -o $salida | Out-Null
    $ipk = Get-ChildItem $salida -Filter *.ipk | Select-Object -First 1
    if (-not $ipk) { Falla "no se generó el paquete de la mini-app." }
    ares-install --device $Nombre $ipk.FullName
    if ($LASTEXITCODE -ne 0) { Falla "falló la instalación en el TV." }
    ares-launch --device $Nombre $ID

    # ¿Que este PC la vuelva a abrir si se cierra o tras un corte de luz? Solo
    # para un televisor dedicado a la cartelería: en uno de uso normal molestaría.
    if (-not $Vigilar -and $preguntar) {
        $r = Read-Host "¿Que este PC mantenga la mini-app abierta (la abre sola si se cierra o tras un corte de luz)? Solo para un TV dedicado. (S/N)"
        $Vigilar = $r -match '^\s*[sSyY]'
    }

    # Apuntar cuándo empezó la sesión de Developer Mode de este TV (la hora del
    # propio televisor, que se anota al activarlo o renovarlo): el panel avisa
    # cuando va a caducar. Si falla, solo se pierde el aviso.
    try {
        $ErrorActionPreference = "Continue"
        $nums = @(ares-novacom --device $Nombre --run "date +%s; stat -c %Y /var/luna/preferences/devmode_enabled" 2>&1 |
            Where-Object { "$_" -match '^\d{9,}$' } | ForEach-Object { [double]"$_" })
        $ErrorActionPreference = "Stop"
        $datos = Join-Path $env:ProgramData "InTeks Display"
        if ($nums.Count -ge 2 -and (Test-Path $datos)) {
            $ahoraPc = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            $inicio = [int64]($ahoraPc - ($nums[0] - $nums[1]))
            $arch = Join-Path $datos "lg_tvs.json"
            $tvs = @()
            if (Test-Path $arch) { try { $tvs = @((Get-Content $arch -Raw -Encoding UTF8 | ConvertFrom-Json).tvs) | Where-Object { $_ -and $_.id -ne $TV } } catch { $tvs = @() } }
            # Si ya estaba apuntado, se respeta su casilla «Mantenerla abierta» del panel.
            $antes = $null
            if (Test-Path $arch) { try { $antes = @((Get-Content $arch -Raw -Encoding UTF8 | ConvertFrom-Json).tvs) | Where-Object { $_ -and $_.id -eq $TV } | Select-Object -First 1 } catch { } }
            $vig = [bool]$Vigilar -or ($antes -and $antes.vigilar -eq $true)
            $tvs += [pscustomobject]@{ id = $TV; nombre = $Nombre; ip = $TV; inicio = $inicio; vigilar = $vig }
            $json = (@{ tvs = @($tvs) } | ConvertTo-Json -Depth 4)
            [IO.File]::WriteAllText($arch, $json, (New-Object Text.UTF8Encoding($false)))
            $horas = [int](1000 - ($ahoraPc - $inicio) / 3600)
            Write-Host "Modo desarrollador del TV: quedan unas $horas horas. El panel avisará antes de que caduque." -ForegroundColor Cyan
        }
    } catch { $ErrorActionPreference = "Stop" }

    # La tarea que ejecuta el vigilante cada 5 minutos, con la cuenta de quien instala
    # (la clave del TV vive en su perfil). Se crea siempre: sin televisores marcados
    # no hace nada, y así la casilla del panel basta para activarlo después.
    try {
        $vig = Join-Path $raiz "vigilar-lg.ps1"
        if (-not (Test-Path $vig)) { $vig = Join-Path $PSScriptRoot "vigilar-lg.ps1" }
        $accion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$vig`""
        $disp = @((New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"),
                  (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)))
        $aj = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName "InTeks Display LG" -Action $accion -Trigger $disp -Settings $aj -Force | Out-Null
        Write-Host "Tarea «InTeks Display LG» creada: cada 5 minutos mira los televisores con «Mantenerla abierta» marcado en el panel." -ForegroundColor Cyan
    } catch { Write-Host "Aviso: no pude crear la tarea que mantiene la mini-app abierta ($($_.Exception.Message))." -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Listo. La mini-app está instalada y abierta en el TV, apuntando a $url" -ForegroundColor Green
    Write-Host "Si sale un código de 4 cifras, enlázala en el panel (Pantallas -> Esperando para enlazar)."
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
