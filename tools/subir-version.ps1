param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

# ─────────────────────────────────────────────────────────────────────────────
#  Sube el numero de version en los tres sitios donde vive.
#
#  Por que hace falta un script para esto: la version esta en server.py (lo que
#  reporta el panel), en installer\setup.iss (dos veces: lo que ve Windows en
#  "Programas instalados" y el nombre del .exe) y en package.json. Son cuatro
#  ediciones a mano en tres archivos que no se hablan, y olvidarse de una
#  significa que el panel de una tienda dice una cosa y el instalador otra.
#
#  Peor todavia: dos .exe distintos con el mismo nombre. Ya paso -en un solo dia
#  salieron cinco builds llamados 1.0.0- y no habia forma de saber cual tenia
#  instalado cada equipo.
#
#  tests\version-sync.test.js vigila que los tres coincidan. Este script los
#  cambia a la vez para que nunca lleguen a discrepar.
#
#  Uso:   powershell -ExecutionPolicy Bypass -File tools\subir-version.ps1 1.0.1
# ─────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Host ""
    Write-Host "  '$Version' no tiene forma de version. Se espera algo como 1.0.1"
    Write-Host ""
    exit 1
}

$RAIZ = Split-Path -Parent $PSScriptRoot

function Reemplazar($ruta, $patron, $nuevo, $que) {
    $completa = Join-Path $RAIZ $ruta
    $texto = Get-Content $completa -Raw
    if ($texto -notmatch $patron) {
        Write-Host "  ERROR: no se encuentra $que en $ruta"
        exit 1
    }
    $cambiado = [regex]::Replace($texto, $patron, $nuevo)
    # -NoNewline: Set-Content anade un salto de linea al final y en cada pasada
    # el archivo creceria por abajo.
    Set-Content -Path $completa -Value $cambiado -NoNewline
    Write-Host "  $ruta  ->  $que"
}

Write-Host ""
Write-Host "  InTeks Display - subiendo a $Version"
Write-Host "  ------------------------------------"
Write-Host ""

Reemplazar "server.py" '(?m)^APP_VERSION\s*=\s*"[^"]+"' "APP_VERSION = `"$Version`"" "APP_VERSION"
Reemplazar "installer\setup.iss" '(?m)^AppVersion=.+$' "AppVersion=$Version" "AppVersion"
Reemplazar "installer\setup.iss" '(?m)^OutputBaseFilename=(.*)_v[0-9.]+\s*$' "OutputBaseFilename=`$1_v$Version" "nombre del .exe"
Reemplazar "package.json" '(?m)^(\s*"version":\s*)"[^"]+"' "`$1`"$Version`"" "version"

Write-Host ""
Write-Host "  Comprobando que los tres coinciden..."
Push-Location $RAIZ
try {
    $salida = & npm test 2>&1 | Out-String
} finally {
    Pop-Location
}

if ($salida -match "fail 0") {
    Write-Host "  Todo coincide."
} else {
    Write-Host ""
    Write-Host "  ERROR: los tests no pasan. Revisa antes de compilar:"
    $salida.Split("`n") | Where-Object { $_ -match "not ok|✖|fail " } | Select-Object -First 10
    exit 1
}

Write-Host ""
Write-Host "  Falta lo unico que no puede hacer un script:"
Write-Host "    1. Anota los cambios en CHANGELOG.md"
Write-Host "    2. git commit"
Write-Host "    3. Compila:  `"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`" installer\setup.iss"
Write-Host ""
Write-Host "  Saldra:  dist\installer\InTeks_Display_Setup_v$Version.exe"
Write-Host ""
