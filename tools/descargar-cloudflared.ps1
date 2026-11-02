# ─────────────────────────────────────────────────────────────────────────────
#  Trae cloudflared.exe, el conector que el instalador mete dentro de InTeks
#  Display para el «Acceso remoto» (el túnel hacia la cuenta de InTeks).
#
#  La versión y el SHA-256 van fijados a propósito: este .exe acaba instalado como
#  servicio de Windows en los PCs de las tiendas, así que no se acepta nada que no
#  sea byte a byte el que se probó. Para subir de versión, cambia las dos líneas.
#
#  No va en git (binario de terceros, ~55 MB). Uso:
#     powershell -ExecutionPolicy Bypass -File tools\descargar-cloudflared.ps1
# ─────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$VERSION = "2026.10.7"
$SHA256  = "2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343"
$URL     = "https://github.com/cloudflare/cloudflared/releases/download/$VERSION/cloudflared-windows-amd64.exe"
$RAIZ    = Split-Path -Parent $PSScriptRoot
$DESTINO = Join-Path $RAIZ "vendor\cloudflared"
$EXE     = Join-Path $DESTINO "cloudflared.exe"

if ((Test-Path $EXE) -and ((Get-FileHash $EXE -Algorithm SHA256).Hash -ieq $SHA256)) {
    Write-Host "  cloudflared $VERSION ya esta en vendor\cloudflared"
    exit 0
}

New-Item -ItemType Directory -Force -Path $DESTINO | Out-Null
$tmp = Join-Path $env:TEMP "cloudflared-$VERSION.exe"
Write-Host "  Descargando $URL"
Invoke-WebRequest -Uri $URL -OutFile $tmp -UseBasicParsing

$hash = (Get-FileHash $tmp -Algorithm SHA256).Hash
if ($hash -ine $SHA256) {
    Remove-Item $tmp -Force
    Write-Host "ERROR: el SHA-256 no coincide (esperado $SHA256, recibido $hash). No se usa." -ForegroundColor Red
    exit 1
}
Move-Item $tmp $EXE -Force
Write-Host "  cloudflared $VERSION listo en vendor\cloudflared (SHA-256 verificado)"
