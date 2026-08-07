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
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
UninstallDisplayIcon={app}\start_signalos.bat

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en escritorio"; GroupDescription: "Accesos directos:"; Flags: checked
Name: "startupicon"; Description: "Iniciar SignalOS Pro automáticamente al encender el equipo (recomendado)"; GroupDescription: "Arranque:"; Flags: checked

[Registry]
; Arranque automático con Windows (se elimina al desinstalar)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SignalOS Pro"; ValueData: """{app}\start_signalos.bat"""; Tasks: startupicon; Flags: uninsdeletevalue

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

; NO empaquetar nunca:
;   content.json / screens.json  -> server.py los crea vacíos al arrancar
;                                   (init_file, server.py:200-201). Enviarlos
;                                   distribuiría el contenido de pruebas.
;   admin.json / pin.json        -> secretos por instalación (hash de
;                                   contraseña, secret de sesión, api_token).
;   uploads\                     -> os.makedirs lo crea (server.py:31).

[Icons]
Name: "{group}\SignalOS Pro"; Filename: "{app}\start_signalos.bat"; WorkingDir: "{app}"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{commondesktop}\SignalOS Pro"; Filename: "{app}\start_signalos.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\start_signalos.bat"; Description: "Iniciar SignalOS Pro"; Flags: nowait postinstall skipifsilent
