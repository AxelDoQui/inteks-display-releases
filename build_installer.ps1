# Script para compilar el instalador SignalOS Pro con Inno Setup

$ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $ISCC)) {
    $ISCC = "C:\Program Files\Inno Setup 6\ISCC.exe"
}

if (-not (Test-Path $ISCC)) {
    Write-Host "ERROR: Inno Setup no encontrado" -ForegroundColor Red
    Write-Host "Descárgalo de: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    exit 1
}

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
