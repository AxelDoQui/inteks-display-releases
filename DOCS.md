# InTeks Display (SignalOS) — documentación única

v1.0.85 · actualizado 2026-11-21. Cartelería digital para tiendas. Este es el **único** .md de referencia (además de `CHANGELOG.md`, que lee `tools/publicar-version.ps1`). Los documentos anteriores están en el historial de git.

## 1. Arquitectura

- `server.py`: solo stdlib, `ThreadingHTTPServer`, SSE. Sin frameworks ni paso de build en el front (HTML/CSS/JS plano).
- Páginas: `index.html` (router), `admin.html`, `login.html`, `player.html`, `pair.html`, `sw.js` (PWA).
- `inteks-extension/`: extensión Chrome MV3 (divisas). `visor-cliente/extension`: extensión del visor.
- `android/`: app kiosco Kotlin. `webos/`: mini-app LG. `escritorio/`: variante Electron (355 MB, ruta aparte).
- Bot de Telegram (`/estado`), Acceso remoto (Cloudflare, desde 1.0.67), instalador Inno Setup con Python embebido.
- Obsoletos: `extension/script_google/`, `android-tablet/`, `programa-pc/`.

### Datos
- Carpeta de datos: `%PROGRAMDATA%\InTeks Display` (instalado) o junto a `server.py` (desarrollo). `pick_data_dir()` decide por ruta de instalación; `SIGNALOS_DATA` fuerza una (la usan los tests).
- Archivos: `config.json` (plantilla, se copia en el primer arranque), `content.json`, `screens.json`, `admin.json` y `pin.json` (secretos), `uploads/`, `server.log`, `copias/`, `actualizacion\instalacion.log`.
- Nunca se empaquetan `content.json`, `screens.json`, `admin.json`, `pin.json`.
- `content.json` se escribe **solo** vía `contenido_en_edicion()`, que sube `rev` (conflicto: gana quien guarda primero). Las validaciones van antes de abrir la guarda. `screens.json` no tiene guarda de escritura (pendiente).
- `unlink_pending` se registra siempre y se entrega en la siguiente conexión SSE. **No fiarse de un aviso por SSE.**
- Puertos: `port: 80`, `port_fallback: 9000`, luego 19 consecutivos por encima del alternativo.
- Actualización: `update_url: "off"` la desactiva; baja instalador, verifica SHA-256, instala en silencio.

### Endpoints
`/api/info`, `auth-status`, `admin-info`, `content`, `config`, `playlist` (campo `version` → recarga automática), `screens`, `events` (SSE), `pin`, `pair-pending`, `update-check`, `backup`, `restore`, `login|logout|set-password`, `pair`, `pair-request|pair-status|pair-claim`, `upload`, `delete`, `screens/config`, `screens/delete`, `screen-unlink`, `fx-update`, `visor/oferta|respuesta|cerrar`, `alert-test`, `restart`, `items/`.

### Player
Ventana de materialización de slides (radio 1), recarga de seguridad cada 4 h, modo `?preview=1`. Guarda lo último reproducido y las imágenes: aguanta sin servidor (punto tenue en una esquina).

### CSS (WebView de 2017, Chrome 62)
Respaldo antes de la declaración moderna; en `clamp()` el respaldo es el término medio; **nada de sintaxis moderna dentro de custom properties** (no tiene respaldo posible). Lo vigila `tests/css-respaldos.test.js`.

### Android
Barrido de autodescubrimiento; `FLAG_TURN_SCREEN_ON` + wake lock; latido con AlarmManager; nombre guardado fuera del WebView; en pantalla desatendida nunca pide dirección (`queHacerSinServidor()`); salida de mantenimiento con 5×BACK. Sin mDNS: usar la IP. Build con AGP 9: barras dobles en `local.properties` y `JAVA_HOME` al JBR de Android Studio.

## 2. Desarrollo, pruebas y versiones

- `npm test` (266) · 19 suites `tests/test_*.py` (un servidor InTeks en marcha rompe `test_reset_password.py`) · `gradlew test` en `android/` (40).
- `tests/ayuda-aparatos.test.js` lee este archivo: exige la sección `## Con qué reproducir` (< 30 líneas, remite a la ayuda). Fire TV Stick debe seguir «no probado».
- Fallos visuales: verificar renderizando con Chrome headless (`player.html?preview=1` en iframe, `--dump-dom`) y midiendo.
- **Subir versión antes de cada build**, sin excepciones: `tools\subir-version.ps1`.
- Dos instalaciones con el mismo token de Telegram chocan en `getUpdates`.

## 3. Instalador

1. Inno Setup 6 instalado; internet una vez para el Python embebido.
2. `powershell -ExecutionPolicy Bypass -File tools\descargar-python.ps1` (no va en git; sin él `setup.iss` aborta con `#error`).
3. `tools\subir-version.ps1`, luego `.\build_installer.ps1` → `dist/installer/InTeks_Display_Setup_v<VERSION>.exe`.
4. **Todo archivo nuevo va a `[Files]` de `installer/setup.iss`**; si no, 404 en instalación limpia (fallo más común).
- `[InstallDelete]` borra `{app}\vendor\python` al actualizar. `{app}` se borra al desinstalar; `{commonappdata}\InTeks Display` se conserva.
- Servidor = tarea programada «InTeks Display»: al arrancar el equipo, SYSTEM, `pythonw.exe server.py`, sin ventana, reinicia hasta 3 veces (1 min). El acceso directo solo abre el panel. Comprobar: `schtasks /Query /TN "InTeks Display" /V /FO LIST` y `Get-Content "$env:ProgramData\InTeks Display\server.log" -Tail 20`. Si falta la tarea: `& "C:\Program Files\InTeks Display\registrar-tarea.ps1" -AppDir "C:\Program Files\InTeks Display"`.
- La extensión de Chrome no se puede instalar en silencio (Google lo bloqueó). Vías: política `ExtensionInstallForcelist` o Web Store no listada (5 USD). Hoy: modo desarrollador, tres clics.
- Windows 10/11 64 bits; el equipo destino no necesita Python.

## 4. Operación (manual de tienda)

**Básico.** El servidor arranca solo con el equipo (sin iniciar sesión). La casilla «Iniciar con Windows» de Ajustes toca la tarea de verdad; puede fallar sin permisos de administrador y el panel lo dice. Registro: `C:\ProgramData\InTeks Display\server.log`.

**Enlazar un televisor.** Abrir `http://signage.local` (o la IP) → código de 4 cifras → Panel → Pantallas → «Esperando para enlazar» → nombre → Enlazar. Ya enlazado: avisa y vuelve solo en 6 s. Si perdió su identidad: desplegable «reenlazar a: …». **Desenlazar** suelta el aparato sin borrar nada. Televisores que borran memoria: «copiar enlace directo» como página de inicio. Renombrar: Más → Renombrar.

## Con qué reproducir

Cualquier pantalla con navegador sirve para empezar, pero el navegador de fábrica de un televisor no aguanta doce horas con una página abierta y, al fallar, deja el escaparate en negro (pasó con un LG).

- Escaparate encendido todo el día: **caja Android barata** al HDMI con la app de InTeks o Fully Kiosk.
- LG webOS: mini-app (ver «Fallos»), sin cambiar de televisor.
- Mini PC con Windows: servidor y pantalla en uno (siguiente apartado).
- La guía completa, una ficha por aparato, está en el panel: **Ayuda → Con qué reproducir**. Vive allí para tener un solo texto que mantener.

**Mini PC como pantalla.** En el instalador, marcar «Este equipo reproduce en su propia pantalla»; emparejar una vez con el PIN. Se abre solo a pantalla completa y vuelve en ~5 min si falla. Manual: inicio de sesión automático (`netplwiz`) y BIOS «Restore on AC Power Loss = Power On». Panel desde otro equipo: `http://IP/admin.html`.

**Contenido.** Librería → Playlist por pantalla. *Paquetes*: grupo vivo (editarlo cambia todas las pantallas que lo usan; al borrarlo en uso, sus contenidos quedan sueltos). *Vigencia*: fechas inicio/fin; si todo ha caducado se sigue mostrando y la tarjeta avisa. *Margen de seguridad* 0–5 % (solo en la pantalla que recorte bordes). *Transición* (fundido, deslizar, zoom, corte) y *orden aleatorio* (no repite el último). **⭐** = cadencia fija (cada 4 por defecto), solo con orden aleatorio.

**Divisas.** Sección Divisas. El tablero muestra la fecha de las **tasas**, no la de hoy; pasadas 24 h (ajustable, 0 desactiva) parpadea. Extensión de Chrome: instalar una vez, requiere el **token de API** (Ajustes); busca país/moneda; desde otro PC, campo Servidor + token.

**Visor de cliente** (recuadro de una web en una tablet del mostrador). Una vez: cargar `visor-cliente\extension` en Chrome (modo desarrollador) y pegar dirección del servidor + token (Ajustes → Seguridad). Cada uso: añadir recuadro → elegir pantalla → «Mostrar en la pantalla»; repetir para cerrar. El vídeo va por la wifi de la tienda; el servidor guarda ~2 KB en memoria, caducan a los 30 min. Sin imagen: misma red, pantalla enlazada, token vigente. Sin commit y sin probar en aparatos reales. Desde 1.0.85 «Ver ahora» del muro enseña en cada marco lo suyo.

**Panel desde otro PC.** `http://signage.local/admin.html`, misma contraseña, paneles sincronizados. Si no llega: cortafuegos o usar la IP. **Android siempre con IP** (no resuelve `.local`). Conflicto: gana quien guarda primero; el segundo recibe «otro equipo cambió algo…» y repite su última acción.

**Acceso remoto.** En la cuenta de InTeks añadir el PC (nombre → `nombre.inteksdisplay.com`) → PIN de 6 cifras, válido unos minutos y de un solo uso → Ajustes → Acceso remoto → «Enlazar este PC». Requiere contraseña de administrador creada. Desactivar en la misma tarjeta.

**Horarios.** Por pantalla: días con franja, o 24/7. *Festivos*: mandan sobre el día y sobre el 24/7; apagada, otras horas o «solo esta imagen». Solo festivos y ningún día → el resto del año encendida.

**Telegram.** @BotFather → `/newbot` → token; @userinfobot → Id; **escribirle algo al bot primero** («chat not found» si no); Ajustes → Guardar avisos → mensaje de prueba. Avisa pantalla caída/recuperada (solo dentro de horario) y tasas viejas (recordatorio 9:00–22:00 cada hora por defecto; 0 h = uno al día). `/estado`: pantallas, tableros, versión y disco; **solo contesta al chat del dueño** y es solo lectura. El token está en `config.json` (entra en la copia): tratarlo como contraseña.

**Copia de seguridad** (Ajustes). *Completa* = 4 JSON + medios; *solo configuración* = 4 JSON (sin logos ni imágenes). Viajan: pantallas, playlists, librería, paquetes, divisas con su fecha, horarios, festivos, puerto, nombre, token de Telegram. **No viajan**: contraseña, token de extensión, secreto de sesión, PIN. Copia diaria automática en `copias` (sin vídeos, conserva 14) + carpeta externa opcional (si falta el pendrive, espera). Archivo dañado: cada guardado deja `.bak`; el dañado se aparta como `…corrupto-fecha` (no borrarlo hasta comprobar).

**Montar otra tienda desde una copia.** 1) instalar y crear contraseña; 2) restaurar copia completa; 3) cambiar «Nombre de instalación»; 4) borrar pantallas ajenas; 5) emparejar televisores (mismos nombres heredan playlist); 6) reconfigurar extensión con el token nuevo; 7) actualizar las tasas (llegan viejas).

**Actualizar.** Ajustes → Estado actual → «Actualizar ahora» (~1 min, pantallas siguen). Si no aparece: `Ctrl+Shift+R`. Fallo: `actualizacion\instalacion.log`.

## 5. Fallos frecuentes

- **Contraseña olvidada:** `restablecer-contrasena.bat` en la carpeta del programa (solo borra la contraseña); crear otra al instante. No hay recuperación por red a propósito.
- **Pantalla sin contenido:** ¿«en línea»? ¿red del televisor? ¿`http://IP/admin.html` responde?
- **Televisor cargando sin fin con la IP:** cortafuegos. Desde 1.0.14 el instalador crea la regla; si no, PowerShell como administrador: `New-NetFirewallRule -DisplayName "InTeks Display (HTTP)" -Direction Inbound -Protocol TCP -LocalPort 80,9000 -Action Allow -Profile Any`. **`-Profile Any`, no Private** (un wifi sin marcar es Público).
- **Smart TV cierra el navegador:** límite de memoria del televisor. Apagar ahorro de energía/protector. En LG, mini-app `webos\`: (1) TV: instalar «Developer Mode», cuenta de desarrollador LG, activar «Dev Mode Status» y «Key Server», anotar IP y Passphrase (dura ~999 h; «Extend Session Time»); (2) Panel → Ajustes → Televisores LG → «Instalar en un televisor LG» (IP, passphrase, servidor; baja ~60 MB la primera vez); (3) errores salen en rojo; (4) enlazar el código; (5) televisor dedicado: «Mantenerla abierta» (tarea «InTeks Display LG» cada 5 min). LG no puede autoarrancar apps. Alternativa: caja Android + «reenlazar a: …».
- **Contenido viejo:** hay caché local; punto tenue si el servidor lleva rato caído.
- **Disco lleno:** aviso al 90 %; fallan subidas y puede corromperse la config. Borrar vídeos antiguos.
- **Android no abre `signage.local`:** usar la IP.
- **Instalación nueva con 404:** falta un archivo en `[Files]`.

## 6. Dónde está cada cosa

| | |
|---|---|
| Programa | `C:\Program Files\InTeks Display\` |
| Datos, subidas, registro | `C:\ProgramData\InTeks Display\` (no se borra al desinstalar) |
| Extensión de Chrome | `C:\Program Files\InTeks Display\extension\` |

## 7. Pendiente

- Asistente de primer arranque para el puerto; unificar distribución Python vs Electron; conservar ediciones a medias al repintar por SSE; guarda de escritura en `screens.json`; rareza de `pick_data_dir()` con carpetas temporales.
- Sin verificar en aparato: corte de luz (1.0.32), CSS en Chrome 62 (1.0.33), Fire TV Stick, visor de cliente.
- Distribución/firmado del APK. El PC de desarrollo no tiene la tarea programada.
- Idea aparcada, no empezar sin que se pida: «carta de productos».

## 8. Resumen de cambios recientes

1.0.85 keep-awake LG + visor · 1.0.84 enlace propio de la mini-app LG · 1.0.83 prueba de despertar LG · 1.0.82–73 muro de pantallas · 1.0.72–71 bloques de Ajustes y asistente · 1.0.70–69 sonido de vídeo · 1.0.68 vigilante de vídeo LG · 1.0.67 acceso remoto · 1.0.66–65 miniaturas y festivos. Detalle completo en `CHANGELOG.md`.
