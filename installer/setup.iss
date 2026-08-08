[Setup]
AppName=SignalOS Pro
AppVersion=1.0.0
AppPublisher=InTeks Solutions
DefaultDirName={autopf}\SignalOS Pro
DefaultGroupName=SignalOS Pro
OutputDir=..\dist\installer
OutputBaseFilename=SignalOS_Pro_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\start_signalos.bat

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Sin "Flags: checked": ese flag no existe en Inno Setup y aborta la compilación.
; Las tareas ya salen marcadas por defecto; el flag que sí existe es "unchecked".
Name: "desktopicon"; Description: "Crear acceso directo en escritorio"; GroupDescription: "Accesos directos:"
Name: "startupicon"; Description: "Iniciar SignalOS Pro automáticamente al encender el equipo (recomendado)"; GroupDescription: "Arranque:"

; Sin sección [Registry]: el arranque automático ya NO va por la clave Run.
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
Name: "{commonappdata}\SignalOS Pro"; Permissions: users-modify
Name: "{commonappdata}\SignalOS Pro\uploads"; Permissions: users-modify

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
Source: "..\start_signalos.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\vendor\*"; DestDir: "{app}\vendor"; Flags: ignoreversion recursesubdirs createallsubdirs

; Extensión de Chrome para enviar divisas desde cualquier web. Google no permite
; instalarla en silencio desde un instalador —lo bloqueó por abuso de adware—, así
; que se copia la carpeta y se guía al usuario con instalar-extension.html.
Source: "..\signalos-extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "instalar-extension.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "registrar-tarea.ps1"; DestDir: "{app}"; Flags: ignoreversion

; NO empaquetar nunca:
;   content.json / screens.json  -> server.py los crea vacíos al arrancar
;                                   (init_file, server.py:200-201). Enviarlos
;                                   distribuiría el contenido de pruebas.
;   admin.json / pin.json        -> secretos por instalación (hash de
;                                   contraseña, secret de sesión, api_token).
;   uploads\                     -> os.makedirs lo crea (server.py:31).

[Icons]
Name: "{group}\SignalOS Pro"; Filename: "{app}\start_signalos.bat"; WorkingDir: "{app}"
Name: "{group}\Instalar extension de divisas"; Filename: "{app}\instalar-extension.html"; WorkingDir: "{app}"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{commondesktop}\SignalOS Pro"; Filename: "{app}\start_signalos.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Registrar el servidor como tarea al encender el equipo. Corre como SYSTEM con
; pythonw.exe: sin ventana que cerrar y sin depender de que alguien inicie
; sesión. Windows la reinicia sola si el proceso se cae.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-tarea.ps1"" -AppDir ""{app}"""; \
  StatusMsg: "Configurando el arranque automatico..."; \
  Flags: runhidden waituntilterminated; Tasks: startupicon

Filename: "{app}\start_signalos.bat"; Description: "Abrir el panel de administracion"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Quitar la tarea al desinstalar, o quedaría intentando arrancar un programa
; que ya no existe en cada encendido.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\registrar-tarea.ps1"" -Quitar"; \
  Flags: runhidden waituntilterminated; RunOnceId: "QuitarTareaSignalOS"
