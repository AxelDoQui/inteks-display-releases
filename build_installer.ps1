# Script para compilar el instalador SignalOS Pro con Inno Setup

# Rutas habituales de ISCC.exe. La tercera es la instalación "solo para mí",
# que no va a Program Files y es la que usa este equipo.
$candidatos = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$ISCC = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $ISCC) {
    Write-Host "ERROR: Inno Setup no encontrado. Buscado en:" -ForegroundColor Red
    $candidatos | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    Write-Host "Descárgalo de: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    exit 1
}
Write-Host "Compilador: $ISCC" -ForegroundColor DarkGray

$setupPath = Join-Path $PSScriptRoot "installer\setup.iss"
$distPath = Join-Path $PSScriptRoot "dist\installer"

# Crear carpeta dist
New-Item -ItemType Directory -Path $distPath -Force | Out-Null

# Compilar instalador
Write-Host "Compilando instalador..." -ForegroundColor Cyan
& $ISCC $setupPath

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Instalador compilado correctamente" -ForegroundColor Green
    Write-Host "Ubicación: $distPath" -ForegroundColor Green
} else {
    Write-Host "`n✗ Error compilando instalador" -ForegroundColor Red
}
