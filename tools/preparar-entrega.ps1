# Reune en una sola carpeta (Entregables\) lo que se lleva a una tienda:
#   - el instalador de Windows (servidor + panel + pantalla)
#   - el .apk de la caja Android TV
#
# No compila nada: copia lo que ya esta compilado, con la version en el nombre.
# Antes hay que haber pasado por:
#   build_installer.ps1                       -> dist\installer\InTeks_Display_Setup_v<VERSION>.exe
#   android\gradlew.bat assembleDebug         -> android\app\build\outputs\apk\debug\app-debug.apk
#     (con JAVA_HOME en el JDK de Android Studio: "...\Android Studio\jbr")
#
# Falla si falta alguno o si el .apk no es de la version actual, para no
# entregar un instalador de una version y un apk de otra.
#
# Uso:   powershell -ExecutionPolicy Bypass -File tools\preparar-entrega.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$version = (Get-Content (Join-Path $raiz "package.json") -Raw | ConvertFrom-Json).version

$instalador = Join-Path $raiz "dist\installer\InTeks_Display_Setup_v$version.exe"
$apk        = Join-Path $raiz "android\app\build\outputs\apk\debug\app-debug.apk"
$meta       = Join-Path $raiz "android\app\build\outputs\apk\debug\output-metadata.json"
$destino    = Join-Path $raiz "Entregables"

if (-not (Test-Path $instalador)) { throw "Falta el instalador $instalador. Ejecuta build_installer.ps1" }
if (-not (Test-Path $apk))        { throw "Falta el apk $apk. Compila con gradlew assembleDebug" }
$vApk = (Get-Content $meta -Raw | ConvertFrom-Json).elements[0].versionName
if ($vApk -ne $version) { throw "El apk es de la version $vApk y el instalador de la $version. Recompila el apk." }

New-Item -ItemType Directory -Force $destino | Out-Null
# Solo queda la version actual: dos entregas mezcladas es justo lo que se evita.
Get-ChildItem $destino -File | Where-Object { $_.Name -like "InTeks_Display_*" } | Remove-Item -Force

Copy-Item $instalador (Join-Path $destino "InTeks_Display_Setup_v$version.exe")
Copy-Item $apk        (Join-Path $destino "InTeks_Display_TV_v$version.apk")

@"
InTeks Display v$version

  InTeks_Display_Setup_v$version.exe   Windows: servidor + panel + reproductor.
                                       Incluye Python, no hay que instalar nada mas.
                                       Para el mini PC del televisor, marca la casilla
                                       "Este equipo reproduce en su propia pantalla".
  InTeks_Display_TV_v$version.apk      Android TV / tablet: reproductor en modo kiosco.
                                       Se instala con adb o desde un USB.

Generado el $(Get-Date -Format 'yyyy-MM-dd HH:mm').
"@ | Set-Content (Join-Path $destino "LEEME.txt") -Encoding UTF8

Get-ChildItem $destino | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,2)}}
Write-Host "`nListo: $destino"
