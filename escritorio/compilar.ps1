# Compila InTeksDisplay.exe (el panel como app de escritorio).
#
# Necesita el paquete oficial Microsoft.Web.WebView2 de NuGet, descomprimido:
#   -Sdk <carpeta donde esta lib\net462 y runtimes\win-x64\native>
# (un .nupkg es un zip: basta con descomprimirlo).
# Salida: escritorio\bin\  -> el .exe y las tres DLL que necesita al lado.
param([Parameter(Mandatory = $true)][string]$Sdk)

$ErrorActionPreference = "Stop"
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz = Split-Path -Parent $aqui
$csc  = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$lib  = Join-Path $Sdk "lib\net462"
$nat  = Join-Path $Sdk "runtimes\win-x64\native\WebView2Loader.dll"
$ico  = Join-Path $raiz "assets\icon.ico"
$bin  = Join-Path $aqui "bin"

foreach ($f in @($csc, "$lib\Microsoft.Web.WebView2.Core.dll", "$lib\Microsoft.Web.WebView2.WinForms.dll", $nat, $ico)) {
    if (-not (Test-Path $f)) { throw "Falta: $f" }
}
New-Item -ItemType Directory -Force $bin | Out-Null
Copy-Item "$lib\Microsoft.Web.WebView2.Core.dll", "$lib\Microsoft.Web.WebView2.WinForms.dll", $nat $bin -Force

& $csc /nologo /target:winexe /out:"$bin\InTeksDisplay.exe" /win32icon:"$ico" `
    /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll `
    /r:"$bin\Microsoft.Web.WebView2.Core.dll" /r:"$bin\Microsoft.Web.WebView2.WinForms.dll" `
    "$aqui\InTeksDisplay.cs"
if ($LASTEXITCODE -ne 0) { throw "csc fallo ($LASTEXITCODE)" }
Write-Host "Listo: $bin\InTeksDisplay.exe"
