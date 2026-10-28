# Publica la versión actual en GitHub Releases para que las tiendas la reciban
# con el botón «Actualizar ahora» del panel.
#
# Qué hace:
#   1. Calcula el SHA-256 del instalador de Entregables\.
#   2. Escribe Entregables\version.json (versión, dirección del instalador, huella).
#   3. Crea la release v<versión> con el instalador, el .apk y version.json.
#
# Las tiendas consultan siempre:
#   https://github.com/<repo>/releases/latest/download/version.json
# (la dirección que va en «update_url» de config.json de cada tienda).
#
# Antes: build_installer.ps1, compilar el .apk y tools\preparar-entrega.ps1.
# Necesita la CLI de GitHub (gh) con la sesión iniciada.
#
# Uso:   powershell -File tools\publicar-version.ps1 -Repo usuario/repositorio
#        powershell -File tools\publicar-version.ps1 -Repo usuario/repositorio -SoloManifiesto
#   (-SoloManifiesto escribe version.json y se para: no sube nada)
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$Notas = "",
    [switch]$SoloManifiesto,
    [switch]$SinPreguntar
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$version = (Get-Content (Join-Path $raiz "package.json") -Raw | ConvertFrom-Json).version
$ent = Join-Path $raiz "Entregables"
$nombreExe = "InTeks_Display_Setup_v$version.exe"
$exe = Join-Path $ent $nombreExe
$apk = Join-Path $ent "InTeks_Display_TV_v$version.apk"
foreach ($f in @($exe, $apk)) {
    if (-not (Test-Path $f)) { throw "Falta $f. Ejecuta antes tools\preparar-entrega.ps1" }
}
if ($Repo -notmatch '^[\w.-]+/[\w.-]+$') { throw "El repositorio debe ser usuario/nombre" }

if (-not $Notas) {
    # Las notas salen del CHANGELOG: lo que hay bajo «## <versión>» hasta la siguiente «---».
    $cl = Get-Content (Join-Path $raiz "CHANGELOG.md") -Raw -Encoding UTF8
    if ($cl -match "(?s)## $([regex]::Escape($version)) [^\r\n]*\r?\n(.*?)\r?\n---") { $Notas = $Matches[1].Trim() }
}

$huella = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
$manifiesto = [ordered]@{
    version       = $version
    installer_url = "https://github.com/$Repo/releases/download/v$version/$nombreExe"
    sha256        = $huella
    url           = "https://github.com/$Repo/releases/tag/v$version"
    notes         = $Notas
}
$json = Join-Path $ent "version.json"
[IO.File]::WriteAllText($json, ($manifiesto | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
Write-Host "version.json escrito: $json"
Write-Host "  versión $version   SHA-256 $huella"
if ($SoloManifiesto) { exit 0 }

Write-Host ""
Write-Host "Se va a PUBLICAR en https://github.com/$Repo la release v$version con:"
Write-Host "  $nombreExe, $(Split-Path -Leaf $apk) y version.json"
if (-not $SinPreguntar -and (Read-Host "¿Publicar? (s/n)") -ne "s") { Write-Host "Cancelado."; exit 1 }

gh release create "v$version" $exe $apk $json --repo $Repo --title "InTeks Display $version" --notes $Notas
if ($LASTEXITCODE -ne 0) { throw "gh no pudo crear la release" }
Write-Host ""
Write-Host "Publicada. update_url para las tiendas:"
Write-Host "  https://github.com/$Repo/releases/latest/download/version.json"
