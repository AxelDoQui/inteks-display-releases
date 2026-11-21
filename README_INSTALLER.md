# InTeks Display — Construcción del Instalador

> Actualizado: 21 de noviembre de 2026 (v1.0.85).

## Requisitos

1. **Inno Setup 6** — https://jrsoftware.org/isdl.php
2. **Conexión a internet, una sola vez**, en la máquina donde se compila: hace
   falta para bajar el Python embebido (ver más abajo). El equipo del cliente
   **no necesita tener Python**.

## El instalador SÍ incluye Python

El instalador lleva dentro un intérprete **embebido** de python.org en
`{app}\vendor\python\` (~21 MB). El cliente no instala nada aparte, y la tarea
programada arranca el servidor con ese `pythonw.exe`.

- **No va en git** (son binarios de python.org). Antes de compilar hay que
  bajarlo una vez:

  ```powershell
  powershell -ExecutionPolicy Bypass -File tools\descargar-python.ps1
  ```

- Si falta `vendor\python\pythonw.exe`, `setup.iss` **aborta la compilación**
  con `#error`, para no generar nunca un instalador sin intérprete.
- Al **actualizar**, `[InstallDelete]` borra `{app}\vendor\python` antes de
  copiar el nuevo, para no mezclar archivos de dos versiones de Python (ese
  Frankenstein no arranca).
- La variante Electron (`escritorio/`) trae su propio runtime, pero pesa
  355 MB y es una ruta de empaquetado distinta.

## Pasos para construir

### 1. Instala Inno Setup

Se instala por defecto en `C:\Program Files (x86)\Inno Setup 6\`.
`build_installer.ps1` busca ahí y en `C:\Program Files\Inno Setup 6\`.

### 2. Comprueba que están todos los archivos

`installer/setup.iss` es la fuente de verdad de qué se empaqueta. Hoy son:

```
Digital Signage/
├── server.py
├── index.html          ← raíz "/" (router de pantallas)
├── admin.html
├── login.html          ← sin él, /admin.html devuelve 404
├── player.html
├── pair.html
├── sw.js               ← service worker de la PWA
├── config.json         (se instala con onlyifdoesntexist)
├── abrir-panel.bat
├── assets/
├── vendor/
│   └── python/         ← intérprete embebido (no va en git; tools\descargar-python.ps1)
├── inteks-extension/ ← se copia a {app}\extension\
└── installer/
    └── instalar-extension.html  ← la guía de 3 pasos
```

**Nunca se empaquetan** `content.json` ni `screens.json` (el servidor los crea
vacíos al arrancar; incluirlos enviaría el contenido de pruebas a cada cliente)
ni `admin.json` ni `pin.json`, que son secretos por instalación.

Si añades un archivo nuevo al proyecto, **añádelo también a `[Files]`**. Es el
fallo más fácil de cometer aquí y no se nota hasta que alguien instala en
limpio.

### 3. Compila

```powershell
cd "c:\Users\axeld\Documents\1. Proyectos Apps\Digital Signage"
.\build_installer.ps1
```

O abre `installer/setup.iss` con Inno Setup y pulsa *Compile*.

### 4. Resultado

```
dist/installer/InTeks_Display_Setup_v<VERSION>.exe
```

El número sale de `OutputBaseFilename` en `setup.iss`, que lo pone
`tools\subir-version.ps1`. Si el nombre no lleva la versión que esperas, es que
no subiste la versión antes de compilar.

## La extensión de Chrome

El instalador copia la extensión a `{app}\extension\` y crea un acceso directo
**«Instalar extension de divisas»** que abre una página con los pasos.

**No se puede instalar sola, y no es un descuido.** Google bloqueó la
instalación silenciosa de extensiones desde instaladores de Windows porque era
el vector habitual del adware. El mecanismo clásico —una clave de registro
apuntando a un `.crx` local— lleva desactivado desde Chrome 33: la extensión se
instala y el navegador la deshabilita. Los tutoriales que lo explican están
obsoletos.

Quedan dos vías legítimas si algún día hace falta la instalación automática:

- **Política de empresa** (`ExtensionInstallForcelist` en
  `HKLM\SOFTWARE\Policies\Google\Chrome`) apuntando a un `update.xml` propio.
  InTeks Display ya es un servidor HTTP y podría alojarlo. A cambio hay que firmar la
  extensión y el cliente no puede desinstalarla desde Chrome.
- **Chrome Web Store** como extensión *no listada*, visible solo con el enlace.
  Cuesta 5 USD una vez, pasa revisión de Google y se actualiza sola.

Mientras tanto, cargarla en modo desarrollador funciona exactamente igual y son
tres clics una sola vez.

## Dónde viven los datos

El programa se instala en `C:\Program Files\InTeks Display\` y **los datos van
aparte**, en `C:\ProgramData\InTeks Display\`:

| Carpeta | Contenido | Al desinstalar |
|---|---|---|
| `{app}` | server.py, los .html, vendor, assets, extension | se borra |
| `{commonappdata}\InTeks Display` | config.json, content.json, screens.json, admin.json, pin.json, uploads/ | **se conserva** |

Windows prohíbe escribir en `Program Files` a los procesos sin elevar, así que
guardar ahí el estado hacía que el servidor muriera al arrancar con
`PermissionError: [WinError 5] Acceso denegado: 'uploads'`. El instalador crea
la carpeta de datos con permiso de modificación para *Users*.

En **desarrollo** no cambia nada: si se puede escribir junto a `server.py`, los
datos se quedan ahí como siempre. La variable de entorno `SIGNALOS_DATA` fuerza
una carpeta concreta, lo que usan las pruebas.

El `config.json` que instala el instalador sirve de **plantilla**: la primera
vez se copia a la carpeta de datos, respetando el puerto y el nombre elegidos.

## Cómo arranca el servidor

Como **tarea programada** llamada `InTeks Display`, no como un `.bat` en el
arranque. La registra `installer\registrar-tarea.ps1` durante la instalación:

| | |
|---|---|
| Disparador | al **encender el equipo** |
| Usuario | `SYSTEM` |
| Ejecuta | `pythonw.exe server.py` |
| Ventana | ninguna |
| Si el proceso cae | Windows lo reinicia, hasta 3 veces con 1 minuto de espera |

Dos razones para no usar la clave `Run` del registro:

- `Run` se dispara **al iniciar sesión**. Tras un corte de luz de madrugada el
  equipo arranca y se queda en la pantalla de bloqueo, con las pantallas sin
  contenido hasta que alguien entre.
- Ejecutaba un `.bat`, que abre una consola. En un PC que también se usa para
  otras cosas, cualquiera puede cerrarla por error y dejar las pantallas
  muertas.

`pythonw.exe` no abre consola en absoluto, así que **no hay ventana que
cerrar**. Como contrapartida no hay salida por pantalla, y por eso el servidor
escribe su registro en `C:\ProgramData\InTeks Display\server.log`: es el primer
sitio donde mirar si algo no arranca.

El acceso directo del escritorio ya **no arranca el servidor**: abre el panel de
administración, y despierta la tarea si no estuviera corriendo.

Para comprobar el estado a mano:

```powershell
schtasks /Query /TN "InTeks Display" /V /FO LIST
Get-Content "$env:ProgramData\InTeks Display\server.log" -Tail 20
```

## Qué hace el instalador

- Instala en `C:\Program Files\InTeks Display\`
- Accesos directos en escritorio y menú inicio
- Opción de arranque con Windows (entrada en `HKCU\...\Run`)
- Al ejecutar, `abrir-panel.bat` lee el puerto de `config.json`, arranca
  `server.py`, espera a que escuche y abre el navegador en el puerto correcto
- Desinstalador en "Programas y características"

## Puertos

`config.json` trae `port: 80` y `port_fallback: 9000`. Si el principal está
ocupado, `server.py` prueba el alternativo y después los 19 puertos
consecutivos por encima **del alternativo** (9001, 9002…), no del principal.
El lanzador vigila el principal y el alternativo y abre el que realmente
responda, así que no hay que sincronizarlos a mano.

El puerto 80 lo suelen ocupar IIS, Skype o algún Apache/XAMPP previo. Es la
causa más habitual de que la instalación acabe en el 9000.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| "Inno Setup no encontrado" | Ruta distinta | Edita `$ISCC` en `build_installer.ps1` |
| Al compilar: "Falta vendor\python" | No se ha bajado el Python embebido | `powershell -ExecutionPolicy Bypass -File tools\descargar-python.ps1` y vuelve a compilar |
| El servidor no arranca tras instalar | Falla al iniciar | Mira `C:\ProgramData\InTeks Display\server.log`; o ejecuta `"{app}\vendor\python\python.exe" server.py` a mano para ver el error |
| Instalación nueva da 404 en todo | Falta un archivo en `[Files]` | Revisa la sección `[Files]` de `setup.iss` |
| El contenido "desaparece" tras reiniciar | Working directory incorrecto | El `.bat` debe hacer `cd /d` antes de lanzar el servidor; las rutas de `server.py` son relativas |
| Un TV/tablet se queda cargando indefinidamente al abrir la IP, aunque el PC vea el servidor por `localhost` | Windows Firewall bloquea las conexiones entrantes de otros dispositivos por defecto. Desde 1.0.14 la regla la crea el instalador (`registrar-tarea.ps1`, función `AbrirCortafuegos`); en instalaciones anteriores no existe | `New-NetFirewallRule -DisplayName "InTeks Display (HTTP)" -Direction Inbound -Protocol TCP -LocalPort 80,9000 -Action Allow -Profile Any` (PowerShell como administrador). **`Any`, no `Private`**: una red sin marcar es Pública para Windows, y una regla de perfil Privado no se aplica ahí |
| Una caja Android o un móvil Android no abre `http://signage.local` | Android no resuelve nombres mDNS (iOS y macOS sí) | Usar la IP del servidor |

## Distribución

- Comparte `InTeks_Display_Setup_v<VERSION>.exe`, el de `dist/installer/`
- No requiere Python ni Node.js en el equipo destino (el intérprete va dentro)
- Windows 10 y 11, 64 bits
