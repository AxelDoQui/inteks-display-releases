# Script para compilar el instalador InTeks Display con Inno Setup

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

    # Dejar solo el recien compilado.
    #
    # El nombre del .exe lleva la version dentro a proposito (setup.iss,
    # OutputBaseFilename): sin eso salian varios instaladores distintos
    # llamados igual y no habia forma de saber cual tenia cada tienda. El
    # efecto secundario era que se acumulaban todos —cinco versiones, 60 MB—
    # y volvia la misma duda por el otro lado: cual de los cinco hay que
    # llevarse. Se borran aqui y no antes de compilar, para no quedarse sin
    # ninguno si la compilacion falla.
    #
    # Si alguna vez hace falta una version anterior, se reconstruye: el
    # historial de git la tiene, y tools\subir-version.ps1 deja los cuatro
    # sitios coherentes.
    $m = Select-String -Path $setupPath -Pattern '^OutputBaseFilename=(.+)$' | Select-Object -First 1
    if ($m) {
        $actual = $m.Matches[0].Groups[1].Value.Trim()
        $viejos = Get-ChildItem $distPath -Filter "InTeks_Display_Setup_v*.exe" -ErrorAction SilentlyContinue |
                  Where-Object { $_.BaseName -ne $actual }
        foreach ($v in $viejos) {
            Remove-Item $v.FullName -Force
            Write-Host "  retirado $($v.Name)" -ForegroundColor DarkGray
        }
    } else {
        # Sin poder leer que version se acaba de compilar, borrar seria a ciegas.
        Write-Host "  aviso: no se pudo leer OutputBaseFilename, no se limpia nada" -ForegroundColor Yellow
    }

    Write-Host "Ubicación: $distPath" -ForegroundColor Green
} else {
    Write-Host "`n✗ Error compilando instalador" -ForegroundColor Red
}
