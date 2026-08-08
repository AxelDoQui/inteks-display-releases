@echo off
setlocal enabledelayedexpansion

REM ─────────────────────────────────────────────────────────────────────────
REM  SignalOS Pro — abrir el panel de administracion
REM
REM  Este .bat YA NO arranca el servidor. De eso se encarga la tarea programada
REM  "SignalOS Pro", que se lanza al encender el equipo, corre como SYSTEM y usa
REM  pythonw.exe para que no exista ninguna ventana que alguien pueda cerrar por
REM  error. Aqui solo se abre el admin, y se despierta la tarea si no estuviera
REM  corriendo (por ejemplo tras instalar, antes del primer reinicio).
REM ─────────────────────────────────────────────────────────────────────────

if exist "%~dp0server.py" (
    set "SERVER_PATH=%~dp0"
) else (
    set "SERVER_PATH=%ProgramFiles%\SignalOS Pro\"
)
cd /d "%SERVER_PATH%" 2>nul

REM Leer puerto y alternativo de la configuracion. Ojo: la que manda es la de
REM la carpeta de datos; la de aqui es solo la plantilla del instalador.
set "CFG=%SERVER_PATH%config.json"
if exist "%ProgramData%\SignalOS Pro\config.json" set "CFG=%ProgramData%\SignalOS Pro\config.json"

set "PORT="
set "FALLBACK="
for /f "tokens=2 delims=:," %%A in ('findstr /c:"\"port\":" "%CFG%" 2^>nul') do set "PORT=%%A"
for /f "tokens=2 delims=:," %%A in ('findstr /c:"\"port_fallback\":" "%CFG%" 2^>nul') do set "FALLBACK=%%A"
set "PORT=%PORT: =%"
set "FALLBACK=%FALLBACK: =%"
if "%PORT%"=="" set "PORT=80"
if "%FALLBACK%"=="" set "FALLBACK=9000"

REM ¿Ya esta escuchando?
set "READY="
netstat -an | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul 2>&1
if !errorlevel! equ 0 set "READY=%PORT%"
if not defined READY (
    netstat -an | findstr /c:":%FALLBACK% " | findstr /c:"LISTENING" >nul 2>&1
    if !errorlevel! equ 0 set "READY=%FALLBACK%"
)

REM Si no lo esta, despertar la tarea programada y esperar.
if not defined READY (
    schtasks /Run /TN "SignalOS Pro" >nul 2>&1
    for /L %%i in (1,1,20) do (
        if not defined READY (
            timeout /t 1 /nobreak >nul 2>&1
            netstat -an | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul 2>&1
            if !errorlevel! equ 0 set "READY=%PORT%"
        )
        if not defined READY (
            netstat -an | findstr /c:":%FALLBACK% " | findstr /c:"LISTENING" >nul 2>&1
            if !errorlevel! equ 0 set "READY=%FALLBACK%"
        )
    )
)

if not defined READY (
    echo.
    echo  El servidor no responde.
    echo.
    echo  Comprueba la tarea programada "SignalOS Pro" en el Programador de tareas,
    echo  y el registro de errores en:
    echo    %ProgramData%\SignalOS Pro\server.log
    echo.
    pause
    exit /b 1
)

REM Se abre el ADMIN, no la raiz. La raiz es el router de arranque de PANTALLAS:
REM sin identidad guardada redirige a /pair, y eso toca en una tablet, no aqui.
start "" "http://localhost:%READY%/admin.html"
exit /b 0
