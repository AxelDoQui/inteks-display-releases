# ─────────────────────────────────────────────────────────────────────────────
#  Trae el Python embebido que el instalador mete dentro de InTeks Display.
#
#  Por que embebido: hasta ahora el cliente tenia que instalar Python por su
#  cuenta. Para vender esto a una tienda, "primero instala Python" es justo
#  donde se pierde al cliente. El paquete embebido de python.org es un
#  interprete completo en una carpeta, sin instalador ni registro ni PATH.
#
#  No va en git (son ~11 MB de binarios de terceros, no codigo nuestro). Este
#  script lo baja de forma reproducible, como tools/gen_currencies.py hace con
#  los datos de divisas.
#
#  Uso:   powershell -ExecutionPolicy Bypass -File tools\descargar-python.ps1
# ─────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$VERSION = "3.12.10"
$URL     = "https://www.python.org/ftp/python/$VERSION/python-$VERSION-embed-amd64.zip"
$RAIZ    = Split-Path -Parent $PSScriptRoot
$DESTINO = Join-Path $RAIZ "vendor\python"
$TEMPZIP = Join-Path $env:TEMP "python-$VERSION-embed-amd64.zip"

Write-Host ""
Write-Host "  InTeks Display - Python embebido $VERSION"
Write-Host "  --------------------------------------------"
Write-Host ""

if (Test-Path (Join-Path $DESTINO "pythonw.exe")) {
    Write-Host "  Ya esta en vendor\python. Borra esa carpeta si quieres rehacerlo."
    Write-Host ""
    exit 0
}

Write-Host "  Descargando $URL"
Invoke-WebRequest -Uri $URL -OutFile $TEMPZIP -UseBasicParsing
$mb = [math]::Round((Get-Item $TEMPZIP).Length / 1MB, 1)
Write-Host "  Descargado: $mb MB"

if (Test-Path $DESTINO) { Remove-Item -Recurse -Force $DESTINO }
New-Item -ItemType Directory -Force -Path $DESTINO | Out-Null
Expand-Archive -Path $TEMPZIP -DestinationPath $DESTINO -Force
Remove-Item $TEMPZIP

# El paquete embebido trae un ._pth que deja sys.path clavado y desactiva el
# mecanismo de "site". server.py solo usa la biblioteca estandar, asi que con
# eso basta; lo unico que hace falta es que la carpeta del programa entre en
# sys.path para poder ejecutar server.py desde ahi.
$pth = Get-ChildItem -Path $DESTINO -Filter "python*._pth" | Select-Object -First 1
if ($pth) {
    $lineas = Get-Content $pth.FullName
    if ($lineas -notcontains "..") {
        # ".." = la carpeta del programa, un nivel por encima de vendor\python
        Add-Content -Path $pth.FullName -Value ".."
        Write-Host "  Anadido '..' a $($pth.Name) (para encontrar server.py)"
    }
}

$exe = Join-Path $DESTINO "pythonw.exe"
if (-not (Test-Path $exe)) {
    Write-Host ""
    Write-Host "  ERROR: no aparece pythonw.exe en $DESTINO"
    Write-Host ""
    exit 1
}

# Comprobacion de verdad: que este interprete pueda importar lo que usa el
# servidor. Si falta algo, mejor enterarse aqui que en el PC de un cliente.
$py = Join-Path $DESTINO "python.exe"
$modulos = "json,os,base64,mimetypes,threading,time,socket,sys,random,struct,hmac,hashlib,secrets,shutil,io,zipfile,http.server,urllib.request,urllib.parse"
& $py -c "import $($modulos.Replace(',', ', ')); print('modulos ok')"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: a este Python embebido le falta algo que usa server.py"
    Write-Host ""
    exit 1
}

$total = [math]::Round(((Get-ChildItem $DESTINO -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "  Listo: $DESTINO ($total MB)"
Write-Host "  Ya puedes compilar el instalador."
Write-Host ""
