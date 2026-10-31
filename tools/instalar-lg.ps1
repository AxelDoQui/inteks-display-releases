# Instala la mini-app «InTeks Display» en un televisor LG con webOS.
#
# Por qué existe: el navegador de los LG cierra la página cada ~2 minutos. Esta
# mini-app (carpeta webos\) abre el reproductor desde el entorno de apps del TV,
# donde eso no pasa. Solo pide tres datos.
#
# Antes, en el TV: instalar «Developer Mode» (LG Content Store), iniciar sesión con
# la cuenta de desarrollador de LG, activar «Dev Mode Status» y «Key Server».
# Ahí salen la IP del TV y la Passphrase. Este PC y el TV deben estar en la
# misma red. Hace falta Node.js (la herramienta de LG se instala sola).
#
# Uso:
#   powershell -File tools\instalar-lg.ps1 -TV 192.168.0.108 -Passphrase 6DC7B4 -Servidor 192.168.0.90
#   -Servidor es la IP del PC con InTeks Display (o su dirección completa, http://...).
param(
    [Parameter(Mandatory = $true)][string]$TV,
    [Parameter(Mandatory = $true)][string]$Passphrase,
    [Parameter(Mandatory = $true)][string]$Servidor,
    [string]$Nombre = "tienda-lg"
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$app = Join-Path $raiz "webos"
$ID = "com.inteks.display"

function Falla($txt) { Write-Host "ERROR: $txt" -ForegroundColor Red; exit 1 }

# La dirección del servidor, con http:// y barra final.
$url = $Servidor.Trim()
if ($url -notmatch '^https?://') { $url = "http://$url" }
if (-not $url.EndsWith("/")) { $url += "/" }

if (-not (Test-Path (Join-Path $app "index.html"))) { Falla "no encuentro la carpeta webos\ del proyecto." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Falla "falta Node.js (https://nodejs.org). Instálalo y vuelve a ejecutar esto." }

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
    Write-Host ""
    Write-Host "Listo. La mini-app está instalada y abierta en el TV, apuntando a $url" -ForegroundColor Green
    Write-Host "Si sale un código de 4 cifras, enlázala en el panel (Pantallas -> Esperando para enlazar)."
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
