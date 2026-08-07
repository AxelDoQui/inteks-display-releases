@echo off
setlocal enabledelayedexpansion

REM ─────────────────────────────────────────────────────────────────────────
REM  SignalOS Pro — lanzador
REM ─────────────────────────────────────────────────────────────────────────

REM Detectar si estamos en el directorio de instalacion o de desarrollo
if exist "%~dp0server.py" (
    set "SERVER_PATH=%~dp0"
) else (
    set "SERVER_PATH=%ProgramFiles%\SignalOS Pro\"
)

REM IMPRESCINDIBLE: server.py usa rutas relativas (uploads\, content.json,
REM config.json...) que se resuelven contra el working directory del PROCESO.
REM Al arrancar desde el registro (autoarranque de Windows) el CWD seria
REM System32 y el servidor crearia ahi una base de datos vacia, con lo que el
REM cliente veria todo su contenido perdido. Situarse en la carpeta primero.
cd /d "%SERVER_PATH%" 2>nul
if errorlevel 1 (
    echo ERROR: No se encuentra la carpeta de instalacion:
    echo   %SERVER_PATH%
    pause
    exit /b 1
)

REM Comprobar que Python esta disponible. Sin esto el fallo es silencioso:
REM "start /B python.exe" no muestra nada y el usuario ve el navegador con un
REM error de conexion sin saber por que.
where python.exe >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python no esta instalado o no esta en el PATH.
    echo.
    echo  Descarga Python 3.10 o superior desde:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANTE: marca la casilla "Add Python to PATH" al instalarlo.
    echo.
    pause
    exit /b 1
)

REM Leer puerto y puerto alternativo de config.json.
REM findstr /c: hace coincidencia literal exacta, asi "port": no captura
REM tambien "port_fallback":. (La version anterior canalizaba a `head -1`,
REM que no existe en cmd.exe: PORT quedaba vacio y caia siempre al 9000.)
set "PORT="
set "FALLBACK="
for /f "tokens=2 delims=:," %%A in ('findstr /c:"\"port\":" "config.json"') do set "PORT=%%A"
for /f "tokens=2 delims=:," %%A in ('findstr /c:"\"port_fallback\":" "config.json"') do set "FALLBACK=%%A"
set "PORT=%PORT: =%"
set "FALLBACK=%FALLBACK: =%"
if "%PORT%"=="" set "PORT=9000"
if "%FALLBACK%"=="" set "FALLBACK=%PORT%"

REM Arrancar el servidor sin ventana visible
start "" /B python.exe "server.py"

REM Esperar a que escuche. server.py cae al puerto alternativo si el principal
REM esta ocupado (server.py:194), asi que hay que vigilar los dos y abrir el
REM que responda de verdad.
set "READY="
for /L %%i in (1,1,30) do (
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

if not defined READY (
    echo.
    echo  ERROR: El servidor no respondio en 30 segundos.
    echo  Prueba a ejecutarlo a mano para ver el error:
    echo    cd /d "%SERVER_PATH%"
    echo    python server.py
    echo.
    pause
    exit /b 1
)

REM Se abre el ADMIN, no la raiz. La raiz es el router de arranque de PANTALLAS:
REM sin identidad guardada redirige a /pair, y eso es lo que hay que hacer en una
REM tablet, no en el PC servidor. Aqui quien esta delante es el administrador, y
REM la primera vez /admin.html lleva a crear la contrasena.
start "" "http://localhost:%READY%/admin.html"
exit /b 0
