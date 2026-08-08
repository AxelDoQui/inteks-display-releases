@echo off
setlocal enabledelayedexpansion

REM ─────────────────────────────────────────────────────────────────────────
REM  InTeks Display — restablecer la contrasena del panel
REM
REM  Se ejecuta EN EL ORDENADOR donde esta el servidor. No existe ningun
REM  "he olvidado la contrasena" accesible por la red, y es a proposito: eso no
REM  seria recuperacion, seria una puerta trasera que cualquiera conectado al
REM  wifi de la tienda podria usar. La prueba de identidad es estar aqui.
REM ─────────────────────────────────────────────────────────────────────────

REM Misma busqueda que registrar-tarea.ps1: PATH primero, luego el lanzador py,
REM y por ultimo las rutas habituales de instalacion.
set "PY="
for %%C in (python.exe) do if not defined PY set "PY=%%~$PATH:C"
if not defined PY (
    where py >nul 2>&1 && set "PY=py"
)
if not defined PY (
    for /d %%D in ("C:\Python*" "%LocalAppData%\Programs\Python\Python*") do (
        if not defined PY if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
    )
)

if not defined PY (
    echo.
    echo   No se encuentra Python en este equipo.
    echo   InTeks Display lo necesita para funcionar: instalalo desde
    echo   https://www.python.org/downloads/ y vuelve a ejecutar esto.
    echo.
    pause
    exit /b 1
)

"%PY%" "%~dp0restablecer-contrasena.py"
set "SALIDA=%errorlevel%"
echo.
pause
exit /b %SALIDA%
