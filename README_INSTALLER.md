# SignalOS Pro — Construcción del Instalador

> Actualizado: 7 de agosto de 2026.

## Requisitos

1. **Inno Setup 6** — https://jrsoftware.org/isdl.php
2. **Python 3.10 o superior** en la máquina donde se compila y **también en la
   del cliente** (ver más abajo).

## ⚠️ El instalador NO incluye Python

Conviene tenerlo claro antes de distribuir. `setup.iss` empaqueta los archivos
de SignalOS, no un intérprete: `start_signalos.bat` invoca el `python.exe` del
PATH del sistema. En un equipo sin Python el lanzador se detiene y muestra
instrucciones para instalarlo, en lugar de fallar en silencio como antes.

Las opciones son tres:

- **Pedir Python como requisito previo** (lo actual). Simple, pero añade un
  paso a la instalación del cliente.
- **Empaquetar el Python embebido** de python.org (~15 MB descomprimido) dentro
  de `{app}\python\` y apuntar el `.bat` ahí. Es el camino natural si el
  producto se distribuye en volumen.
- **Distribuir la variante Electron**, que sí trae su propio runtime, pero pesa
  355 MB y hoy es una ruta de empaquetado distinta y desatendida.

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
├── start_signalos.bat
├── assets/
├── vendor/
├── signalos-extension/ ← se copia a {app}\extension\
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
dist/installer/SignalOS_Pro_Setup_v1.0.0.exe
```

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
  SignalOS ya es un servidor HTTP y podría alojarlo. A cambio hay que firmar la
  extensión y el cliente no puede desinstalarla desde Chrome.
- **Chrome Web Store** como extensión *no listada*, visible solo con el enlace.
  Cuesta 5 USD una vez, pasa revisión de Google y se actualiza sola.

Mientras tanto, cargarla en modo desarrollador funciona exactamente igual y son
tres clics una sola vez.

## Qué hace el instalador

- Instala en `C:\Program Files\SignalOS Pro\`
- Accesos directos en escritorio y menú inicio
- Opción de arranque con Windows (entrada en `HKCU\...\Run`)
- Al ejecutar, `start_signalos.bat` lee el puerto de `config.json`, arranca
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
| "Python no está instalado o no está en el PATH" | Falta Python | Instálalo marcando *Add Python to PATH* |
| "El servidor no respondió en 30 segundos" | El servidor cascó al arrancar | `cd` a la carpeta y ejecuta `python server.py` a mano para ver el error |
| Instalación nueva da 404 en todo | Falta un archivo en `[Files]` | Revisa la sección `[Files]` de `setup.iss` |
| El contenido "desaparece" tras reiniciar | Working directory incorrecto | El `.bat` debe hacer `cd /d` antes de lanzar el servidor; las rutas de `server.py` son relativas |

## Distribución

- Comparte `SignalOS_Pro_Setup_v1.0.0.exe`
- Requiere Python 3.10+ en el equipo destino (ver arriba)
- No requiere Node.js
- Windows 10 y 11, 64 bits
