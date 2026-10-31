# Deja dentro de la app las herramientas para instalar la mini-app en un televisor
# LG: un Node.js portable y la herramienta oficial de LG (ares-cli). Las usa
# instalar-lg.ps1. Nada va al PATH del sistema ni se toca un Node que ya exista.
#
# Lo lanza el instalador si se marca «Herramientas para televisores LG». Descarga de
# nodejs.org (la versión de abajo) y de npm, así que necesita internet SOLO en este
# momento. El zip se comprueba contra el SHASUMS256.txt de la misma versión.
# Si algo falla no aborta la instalación: deja el motivo en lg-tools\instalacion.log
# y instalar-lg.ps1 lo vuelve a intentar al ejecutarse.
#
# Uso:  instalar-herramientas-lg.ps1 -AppDir "C:\Program Files\InTeks Display"
param([Parameter(Mandatory = $true)][string]$AppDir)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$NODE_VERSION = "v24.16.0"
$base = Join-Path $AppDir "lg-tools"
$nodeDir = Join-Path $base "node"
$cliDir = Join-Path $base "cli"
$log = Join-Path $base "instalacion.log"

New-Item -ItemType Directory -Force $base | Out-Null
function Anota($t) { Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t) -Encoding UTF8 }

try {
    if (-not (Test-Path (Join-Path $nodeDir "node.exe"))) {
        $zipNombre = "node-$NODE_VERSION-win-x64.zip"
        $url = "https://nodejs.org/dist/$NODE_VERSION"
        $zip = Join-Path $base $zipNombre
        Anota "Descargando $zipNombre"
        Invoke-WebRequest "$url/$zipNombre" -OutFile $zip -UseBasicParsing
        $sumas = (Invoke-WebRequest "$url/SHASUMS256.txt" -UseBasicParsing).Content
        $linea = ($sumas -split "`n" | Where-Object { $_ -match [regex]::Escape($zipNombre) } | Select-Object -First 1)
        if (-not $linea) { throw "no encuentro la firma de $zipNombre en SHASUMS256.txt" }
        $esperado = ($linea.Trim() -split "\s+")[0].ToLower()
        $real = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
        if ($real -ne $esperado) { Remove-Item $zip -Force; throw "la firma de $zipNombre no coincide (descarga dañada)" }
        $tmp = Join-Path $base "_node"
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        Expand-Archive $zip -DestinationPath $tmp -Force
        $interna = Get-ChildItem $tmp -Directory | Select-Object -First 1
        if (Test-Path $nodeDir) { Remove-Item $nodeDir -Recurse -Force }
        Move-Item $interna.FullName $nodeDir
        Remove-Item $tmp -Recurse -Force
        Remove-Item $zip -Force
        Anota "Node.js $NODE_VERSION instalado en $nodeDir"
    }

    $ares = Join-Path $cliDir "node_modules\.bin\ares-install.cmd"
    if (-not (Test-Path $ares)) {
        Anota "Instalando la herramienta de LG (ares-cli)"
        New-Item -ItemType Directory -Force $cliDir | Out-Null
        $env:PATH = "$nodeDir;$env:PATH"
        # npm escribe avisos («deprecated») por stderr: con Stop contarían como error.
        $ErrorActionPreference = "Continue"
        & (Join-Path $nodeDir "npm.cmd") install --prefix $cliDir --no-audit --no-fund "@webos-tools/cli" 2>&1 |
            ForEach-Object { Anota "$_" }
        $ErrorActionPreference = "Stop"
        if (-not (Test-Path $ares)) { throw "npm no dejó instalada la herramienta de LG" }
        Anota "ares-cli instalado en $cliDir"
    }
    Anota "Listo"
    exit 0
}
catch {
    Anota "ERROR: $($_.Exception.Message)"
    exit 0
}
