; El interprete embebido no va en git (son ~21 MB de binarios de python.org).
; Si falta, mejor abortar aqui con un mensaje claro que sacar un instalador que
; parece bueno y luego no arranca en el PC de un cliente.
#if !FileExists(AddBackslash(SourcePath) + "..\vendor\python\pythonw.exe")
  #error Falta vendor\python. Ejecuta primero: powershell -ExecutionPolicy Bypass -File tools\descargar-python.ps1
#endif

[Setup]
AppName=InTeks Display
AppVersion=1.0.57
AppPublisher=InTeks Solutions
DefaultDirName={autopf}\InTeks Display
DefaultGroupName=InTeks Display
OutputDir=..\dist\installer
OutputBaseFilename=InTeks_Display_Setup_v1.0.57
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Apuntar al .ico y no al .bat: un acceso directo a un archivo por lotes toma
; el icono generico de Windows (los engranajes), no el del programa.
UninstallDisplayIcon={app}\assets\icon.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Sin "Flags: checked": ese flag no existe en Inno Setup y aborta la compilación.
; Las tareas ya salen marcadas por defecto; el flag que sí existe es "unchecked".
Name: "desktopicon"; Description: "Crear acceso directo en escritorio"; GroupDescription: "Accesos directos:"
; Para el mini PC pegado al televisor: el mismo equipo es servidor y pantalla.
; Sin marcar por defecto, porque en el ordenador del dueño tapa el escritorio.
Name: "pantalla"; Description: "Este equipo reproduce en su propia pantalla (mini PC del televisor): abrir el reproductor a pantalla completa al iniciar sesión y no dejar que se suspenda"; GroupDescription: "Mini PC del televisor:"; Flags: unchecked
Name: "startupicon"; Description: "Iniciar InTeks Display automáticamente al encender el equipo (recomendado)"; GroupDescription: "Arranque:"
; Para poner la pantalla en un televisor LG: el navegador del LG cierra la página
; cada ~2 min, así que se le instala una mini-app (webos\). Esta casilla deja en la
; app un Node.js portable y la herramienta de LG para hacerlo. Descarga de internet
; (unos 200 MB en disco) y no toca ningún Node que el equipo ya tenga.
Name: "lg"; Description: "Herramientas para instalar la pantalla en un televisor LG (descarga unos 60 MB de internet y ocupa unos 200 MB; solo si vas a usar un LG)"; GroupDescription: "Televisores LG:"; Flags: unchecked

[InstallDelete]
; Restos de cuando el producto se llamaba SignalOS Pro. La clave Run apuntaba a
; un .bat que arrancaba un segundo servidor: si se queda, dos procesos se pelean
; por el puerto 80 y gana el viejo. Los DATOS del cliente no se tocan: viven en
; {commonappdata} y server.py los trae al arrancar.
Type: filesandordirs; Name: "{commonpf}\SignalOS Pro"

; El interprete embebido se borra entero en vez de reemplazarse archivo a
; archivo. Reemplazar DLL una a una deja la puerta abierta a mezclar dos
; versiones de Python si algo falla a mitad, y ese Frankenstein no arranca.
; Aqui ya no hay nada agarrandolas: PrepareToInstall paro el servidor antes.
Type: filesandordirs; Name: "{app}\vendor\python"

; OJO con lo que NO se borra aqui. Las primeras versiones escribian los datos
; dentro de Archivos de programa (admin.json, content.json, screens.json,
; uploads\...). Siguen ahi en equipos que vienen de aquella epoca, y
; migrar_datos_antiguos() los trae a {commonappdata} la primera vez que arranca
; el servidor nuevo. [InstallDelete] corre ANTES de todo eso, asi que borrarlos
; aqui seria borrarle al cliente sus pantallas y su contrasena justo antes de
; que nadie los haya leido. Se quedan; los recoge la migracion.
; El registro si se puede tirar: es un log, no configuracion.
Type: files; Name: "{app}\server.log"

[Registry]
; Solo HKLM. La version mas antigua tambien escribia en HKCU, pero borrarlo
; desde aqui no serviria: el instalador corre elevado, asi que HKCU seria el
; registro del ADMINISTRADOR y no el del usuario que usa el equipo. Esa
; limpieza la hace abrir-panel.bat, que si corre en la sesion correcta.
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "SignalOS Pro"; ValueType: none; Flags: deletevalue

; El arranque automático de InTeks Display NO va por la clave Run.
; Run se dispara al iniciar sesión, así que tras un corte de luz el equipo se
; quedaría en la pantalla de bloqueo con las pantallas sin contenido. Y además
; ejecutaba un .bat, que abre una consola que cualquiera puede cerrar por error.
; Ahora lo hace una tarea programada al encender el equipo, con pythonw.exe y
; sin ventana. Ver [Run] y installer\registrar-tarea.ps1.

[Dirs]
; Los datos NO pueden vivir en {app}: Windows prohíbe escribir en Program Files
; a los procesos sin elevar, y el servidor moría al arrancar. Se crea aquí desde
; el instalador (que sí va elevado) y con permiso de modificación para Users,
; para que funcione con cualquier cuenta y no solo con la que arranque primero.
; No lleva "uninsalwaysuninstall": al desinstalar se conservan el contenido y
; las pantallas del cliente.
Name: "{commonappdata}\InTeks Display"; Permissions: users-modify
Name: "{commonappdata}\InTeks Display\uploads"; Permissions: users-modify

[Files]
Source: "..\server.py"; DestDir: "{app}"; Flags: ignoreversion
; index.html es la raíz "/" (router de pantallas) — server.py:613 la sirve por
; defecto. Sin ella, el navegador que abre el instalador recibe un 404.
Source: "..\index.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\admin.html"; DestDir: "{app}"; Flags: ignoreversion
; login.html es imprescindible: /admin.html redirige aquí si no hay sesión.
Source: "..\login.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\player.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\pair.html"; DestDir: "{app}"; Flags: ignoreversion
; Service worker de la PWA (solo se activa bajo HTTPS o localhost).
Source: "..\sw.js"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\abrir-panel.bat"; DestDir: "{app}"; Flags: ignoreversion
; El panel como app de escritorio (ventana WebView2 propia, con su icono y su
; identidad en la barra de tareas). Sale de escritorio\compilar.ps1; sin
; compilarlo antes, esta linea aborta la compilacion a proposito. El .bat se
; queda como respaldo.
Source: "..\escritorio\bin\*"; DestDir: "{app}"; Flags: ignoreversion
; Recuperar el acceso al panel si se olvida la contrasena. Va como herramienta
; local y no como endpoint: por la red seria una puerta trasera.
Source: "..\restablecer-contrasena.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\restablecer-contrasena.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\vendor\*"; DestDir: "{app}\vendor"; Flags: ignoreversion recursesubdirs createallsubdirs

; Extensión de Chrome para enviar divisas desde cualquier web. Google no permite
; instalarla en silencio desde un instalador —lo bloqueó por abuso de adware—, así
; que se copia la carpeta y se guía al usuario con instalar-extension.html.
Source: "..\inteks-extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "instalar-extension.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "registrar-tarea.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "registrar-pantalla.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Mini-app para televisores LG y lo que la instala. Solo con la casilla «lg».
Source: "..\webos\*"; DestDir: "{app}\webos"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: lg
Source: "..\tools\instalar-lg.ps1"; DestDir: "{app}"; Flags: ignoreversion; Tasks: lg
Source: "instalar-herramientas-lg.ps1"; DestDir: "{app}"; Flags: ignoreversion; Tasks: lg
Source: "..\tools\vigilar-lg.ps1"; DestDir: "{app}"; Flags: ignoreversion; Tasks: lg
; Este NO se instala: se extrae a la carpeta temporal y se ejecuta antes de
; copiar nada. Ver [Code] / PrepareToInstall.
Source: "parar-servidor.ps1"; Flags: dontcopy

; NO empaquetar nunca:
;   content.json / screens.json  -> server.py los crea vacíos al arrancar
;                                   (init_file, server.py:200-201). Enviarlos
;                                   distribuiría el contenido de pruebas.
;   admin.json / pin.json        -> secretos por instalación (hash de
;                                   contraseña, secret de sesión, api_token).
;   uploads\                     -> os.makedirs lo crea (server.py:31).

[Icons]
; IconFilename en todos: sin el, un acceso directo a un .bat sale con el icono
; generico de archivo por lotes y el programa parece un script suelto.
Name: "{group}\InTeks Display"; Filename: "{app}\InTeksDisplay.exe"; WorkingDir: "{app}"
Name: "{group}\Instalar extension de divisas"; Filename: "{app}\instalar-extension.html"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
; Pregunta IP del TV, passphrase e IP del servidor y deja la mini-app en el LG.
Name: "{group}\Instalar la pantalla en un TV LG"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -NoExit -File ""{app}\instalar-lg.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Tasks: lg
Name: "{commondesktop}\InTeks Display"; Filename: "{app}\InTeksDisplay.exe"; WorkingDir: "{app}"; Tasks: desktopicon
; Al iniciar sesión, la pantalla completa. La app espera sola a que el servidor
; esté listo (lo despierta con la tarea programada), así que no hace falta retraso.
Name: "{commonstartup}\InTeks Display Pantalla"; Filename: "{app}\InTeksDisplay.exe"; Parameters: "--pantalla"; WorkingDir: "{app}"; Tasks: pantalla
Name: "{group}\InTeks Display Pantalla"; Filename: "{app}\InTeksDisplay.exe"; Parameters: "--pantalla"; WorkingDir: "{app}"; Tasks: pantalla

[Run]
; Abrir el puerto en el cortafuegos. SIN "Tasks:", a propósito: esto se hace
; siempre. Sin la regla, el servidor funciona en el propio PC y ninguna pantalla
; llega a él —se quedan cargando, sin error—, y eso no puede depender de que el
; usuario marque una casilla que habla del arranque automático. Es también el
; único momento en que hay permisos de administrador garantizados.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-tarea.ps1"" -AppDir ""{app}"" -SoloFirewall"; \
  StatusMsg: "Permitiendo el acceso de las pantallas..."; \
  Flags: runhidden waituntilterminated

; Registrar el servidor como tarea al encender el equipo. Corre como SYSTEM con
; pythonw.exe: sin ventana que cerrar y sin depender de que alguien inicie
; sesión. Windows la reinicia sola si el proceso se cae.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-tarea.ps1"" -AppDir ""{app}"""; \
  StatusMsg: "Configurando el arranque automatico..."; \
  Flags: runhidden waituntilterminated; Tasks: startupicon

; Mantiene abierta la ventana de la pantalla: al iniciar sesión y cada 5 min, para
; que vuelva sola tras una actualización (el instalador la cierra al sustituirla).
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-pantalla.ps1"" -AppDir ""{app}"" -Usuario ""{username}"""; \
  StatusMsg: "Configurando la pantalla del televisor..."; \
  Flags: runhidden waituntilterminated; Tasks: pantalla

; Un televisor que se suspende o apaga la pantalla deja la tienda en negro.
Filename: "powercfg.exe"; Parameters: "/change standby-timeout-ac 0"; Flags: runhidden waituntilterminated; Tasks: pantalla
Filename: "powercfg.exe"; Parameters: "/change monitor-timeout-ac 0"; Flags: runhidden waituntilterminated; Tasks: pantalla
Filename: "powercfg.exe"; Parameters: "/change hibernate-timeout-ac 0"; Flags: runhidden waituntilterminated; Tasks: pantalla

; Node.js portable + herramienta de LG dentro de la app. Tarda uno o dos minutos y
; si falla no aborta la instalación (deja el motivo en lg-tools\instalacion.log).
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\instalar-herramientas-lg.ps1"" -AppDir ""{app}"""; \
  StatusMsg: "Descargando las herramientas para televisores LG..."; \
  Flags: runhidden waituntilterminated; Tasks: lg

Filename: "{app}\InTeksDisplay.exe"; Description: "Abrir el panel de administracion"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Lo descargado por la casilla «lg»: no lo conoce el desinstalador.
Type: filesandordirs; Name: "{app}\lg-tools"

[UninstallRun]
; Quitar la tarea al desinstalar, o quedaría intentando arrancar un programa
; que ya no existe en cada encendido.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-tarea.ps1"" -Quitar"; \
  Flags: runhidden waituntilterminated; RunOnceId: "QuitarTareaInTeks Display"
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\vigilar-lg.ps1"" -Quitar"; \
  Flags: runhidden waituntilterminated; RunOnceId: "QuitarTareaInTeksLG"; Tasks: lg
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-pantalla.ps1"" -Quitar"; \
  Flags: runhidden waituntilterminated; RunOnceId: "QuitarTareaPantalla"

[Code]
{ Parar el servidor ANTES de copiar un solo archivo.

  registrar-tarea.ps1 tambien lo para, pero se ejecuta en [Run], al FINAL de la
  instalacion. Desde que el interprete de Python va DENTRO de la instalacion,
  ese servidor vivo tiene agarradas sus propias DLL y la copia falla:

      vendor\python\libcrypto-3.dll
      DeleteFile fallo; codigo 5. Acceso denegado.

  El instalador se pisaba a si mismo. PrepareToInstall corre antes de que Inno
  toque el disco, que es el unico momento en que esto sirve de algo. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  ExtractTemporaryFile('parar-servidor.ps1');
  { Si esto falla no se aborta la instalacion: en un equipo limpio no hay nada
    que parar, y un error aqui no puede impedir instalar por primera vez.
    Si de verdad habia algo agarrando un archivo, Inno lo dira igualmente. }
  Exec('powershell.exe',
       '-NoProfile -ExecutionPolicy Bypass -File "' +
         ExpandConstant('{tmp}\parar-servidor.ps1') +
         '" -AppDir "' + ExpandConstant('{app}') + '"',
       '', SW_HIDE, ewWaitUntilTerminated, Code);
end;
