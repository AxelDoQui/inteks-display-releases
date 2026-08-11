# InTeks Display — Contexto para Claude Code

> Actualizado: 11 de agosto de 2026. Este documento describe el estado **real** del
> código. Si algo aquí no cuadra con lo que ves en los archivos, gana el código:
> avísalo y se corrige el documento.

## Qué es este proyecto

Sistema de digital signage (cartelería digital) para Windows. Gestiona varias
pantallas o tablets desde un PC central por WiFi local, o a través de internet
con un túnel de Cloudflare. Se distribuye como producto comercial a tiendas,
restaurantes, casas de cambio y similares.

## Restricciones de diseño (no negociables)

- **Sin frameworks JS.** HTML/CSS/JS puro en los `.html`. No React, no Vue.
- **Sin dependencias de Python.** Solo librería estándar, incluido el responder
  mDNS, que está escrito a mano sobre sockets.
- **Sin paso de build.** Los `.html` se editan y se sirven tal cual.
- **Funciona sin internet**, salvo clima y noticias, que lo requieren por
  naturaleza. Las librerías de terceros están volcadas en `vendor/`.
- Las tablets solo necesitan un navegador. Nada que instalar en ellas.
- Windows 10 y 11.

## Arquitectura

### Servidor — `server.py` (~42 KB, stdlib pura)

`ThreadingHTTPServer`: cada conexión en su propio hilo, imprescindible porque
las conexiones SSE de `/api/events` viven indefinidamente y bloquearían al
resto en un servidor de un solo hilo.

Responsabilidades: playlists por pantalla, subida y servido de archivos (con
soporte de HTTP Range para vídeo), SSE para refresco en tiempo real,
autenticación de administrador, emparejamiento de pantallas por PIN, y anuncio
mDNS del nombre de la instalación.

Puerto: lee `config.json`, acepta `--port` como override y **cae al puerto
alternativo automáticamente** si el principal está ocupado (`find_free_port`,
línea 194). Quien necesite saber el puerto real no puede fiarse de
`config.json`.

### Interfaces web

| Archivo | Papel |
|---|---|
| `index.html` | Raíz `/`. Router de arranque: si el dispositivo ya está enlazado (localStorage) redirige al player; si no, a emparejar. |
| `login.html` | Puerta de autenticación. En el primer arranque cambia a modo "crear contraseña". |
| `admin.html` | Panel de administración (~144 KB, monolito). |
| `player.html` | Reproductor para pantallas y tablets. |
| `pair.html` | Emparejamiento por PIN. |
| `sw.js` | Service worker de la PWA. Solo se activa bajo HTTPS o localhost. |

### Secciones del admin

Pantallas · Librería · Paquetes · Divisas · Clima · Noticias/ticker ·
Texto/precios · URLs web · Comparativa · Cuenta atrás · QR · Ficha de producto ·
Ajustes · Ayuda

**Paquetes** agrupa varios contenidos para asignarlos juntos a una pantalla
(p. ej. "Promo Enero"). No aparece en ningún roadmap; se añadió sobre la marcha.

### Tipos de slide en el player

`fx` (divisas) · `weather` · `ticker` · `text` · `url` · `video` · `comparison` ·
`countdown` · `qr` · `product`. La imagen es la rama por defecto cuando el tipo
no coincide con ninguno de los anteriores (`player.html:449`).

Cada fila de `fx` admite un `agent` opcional (la ventanilla/agente de pago,
caso Ria y similares con varios puntos de pago por moneda): si viene, el
player la muestra bajo el país (`COP · Davivienda`); si no, la fila se ve
igual que un tablero de cambio normal. La extensión de Chrome ya elegía un
agente para decidir la tasa (`elegirAgente` en `parser.js`) pero lo
descartaba antes de mandarlo — desde 1.0.11 viaja hasta la pantalla. También
se puede escribir a mano en el editor de filas del admin.

Otras capacidades del player: rotación arbitraria vía `config.rotation`,
videowall en dos pantallas (`wall_mode` + `wall_pos`, que recorta la imagen con
`object-position` a izquierda o derecha), horario con imagen de standby, barra
de progreso y refresco del clima cada 15 minutos.

**Resiliencia sin servidor:** el contenido nunca fuerza una recarga de la
página (llega por SSE, `connectSSE()`, y repinta solo); lo último reproducido
se cachea en IndexedDB (imágenes/vídeos) y localStorage (playlist/config) para
sobrevivir a un arranque en frío sin servidor. Aparte de eso hay una recarga de
seguridad cada 4 horas (`RELOAD_SEGURIDAD_MS`), pensada para navegadores de TV
con poca memoria (el de LG webOS es un caso documentado por el propio soporte
de LG) — segura porque la caché ya deja algo pintado antes de que llegue.

**Modo vista previa** — `player.html?preview=1`, sin `?screen=`. No conecta el
SSE, no se registra como pantalla y no aplica el horario. Renderiza el item que
le inyecta el admin por `postMessage` (`preview-item`) y devuelve cuántas
páginas le salieron (`preview-pages`).

El admin lo incrusta en un iframe dimensionado a los píxeles de la resolución
que **escribe el usuario** (no se autodetecta) y reducido con `transform:scale`.
Los `clamp()`/`vw`/`vh` se resuelven así contra el viewport real, de modo que la
cuenta de "cuántas divisas caben" la da el renderizador de verdad y no hay
lógica de maquetación duplicada que se desincronice al tocar el CSS.

### Extensión de Chrome — `inteks-extension/`

Manifest V3. Detecta tablas de tipos de cambio en cualquier web y las envía a
InTeks Display con un clic, vía `POST /api/fx-update` autenticado con el token de API
que se copia desde *Ajustes → Seguridad*. Sirve también en remoto a través del
túnel de Cloudflare.

**Varios agentes de pago por moneda (Ria y similares):** `scanPage()` agrupa
las filas detectadas por código de moneda; cuando hay más de un candidato
(`agentOpciones`), `elegirAgente()` decide con la lista de preferencia del
usuario (`chrome.storage.local.agentPrefs`, `{COP:["Davivienda",...]}`) — la
tasa más alta no siempre es la correcta (ver comentario de `elegirAgente` en
`parser.js`). El panel lateral ofrece un `<select>` con todos los candidatos
para elegir con un clic en vez de escribir el nombre a mano, y avisa
(`agentAlternativa`) cuando otro paga notablemente más sin cambiar la
elección. `extractRate`/`extractAgent` comparten `findRateMatch()`, que busca
el número desde el final del texto — necesario porque un nombre de agente con
dígitos ("4-72 Servici", real en Ria) se confundía con la tasa.

### Empaquetado

`electron/main.js` arranca `server.py` como proceso hijo y da icono de bandeja.
`installer/setup.iss` (Inno Setup) genera el instalador de la **variante
Python**, que es la ruta de distribución principal. Son dos caminos distintos:
`dist/` puede contener un build de Electron desfasado respecto al código.

## Endpoints

```
GET       /api/info            IP, puerto y nombre mDNS
GET       /api/auth-status     ¿hay contraseña? ¿hay sesión?  (público)
GET       /api/admin-info      token de API                   (requiere sesión)
GET/POST  /api/content         leer / guardar contenido completo
GET/POST  /api/config          leer / guardar ajustes
GET       /api/playlist        playlist + config de una pantalla
GET       /api/screens         pantallas registradas
GET       /api/events          SSE, conexión persistente
GET       /api/pin             PIN de emparejamiento vigente
POST      /api/login  /api/logout  /api/set-password
POST      /api/pair            enlazar una pantalla con el PIN
POST      /api/upload  /api/delete
POST      /api/screens/config  /api/screens/delete
POST      /api/fx-update       divisas desde la extensión (token)
POST      /api/restart         reiniciar el servidor
GET       /pair                atajo a pair.html
GET       /uploads/*           archivos subidos (soporta Range)
```

## Datos en disco

Todos son rutas **relativas**, así que el servidor debe ejecutarse con el
working directory en su propia carpeta. Es la razón de que
`abrir-panel.bat` haga `cd /d` antes de arrancar: lanzado desde el registro
de autoarranque, el CWD sería `System32` y crearía allí una base de datos
vacía.

| Archivo | Contenido | ¿Se versiona? |
|---|---|---|
| `config.json` | puerto, alternativo, nombre mDNS, autoarranque | Sí, es la plantilla por defecto |
| `content.json` | items, pantallas, paquetes, `rev` | No — lo crea vacío `init_file` |
| `screens.json` | registro de pantallas vistas | No — ídem |
| `admin.json` | salt, hash de contraseña, secret de sesión, api_token | **No — secretos** |
| `pin.json` | PIN activo, intentos fallidos, bloqueo | **No — secreto** |
| `uploads/` | archivos subidos | No |

**`content.json` solo se escribe por `contenido_en_edicion()`** (`server.py`).
Es un gestor de contexto que lee, deja modificar y guarda **sin soltar el
`file_lock` en medio**: el hueco entre `load_json` y `save_json` era una carrera
real, no teórica —de veinte subidas simultáneas sobrevivían seis—. Además sube
`rev` en cada escritura, y como es el único camino que escribe el archivo,
ningún manejador nuevo puede olvidarse de subirlo. Si añades un endpoint que
toque `content.json`, úsalo; no vuelvas a `load_json`/`save_json` sueltos.

Dos trampas al usarlo: salir con `return` desde dentro del `with` **sí** guarda
(solo una excepción aborta la escritura), así que las validaciones que puedan
rechazar la petición van *antes* de abrir el guardián; y en una escritura
condicional hay que entrar solo cuando vayas a mutar de verdad, porque subir
`rev` sin cambiar nada invalida a los paneles abiertos y les provoca un 409
espurio.

## Estilo visual del admin

Azul marino con acento naranja. Los valores vivos están en `:root` de
`admin.html`; esta es la referencia:

```
--bg     #07182b   fondo            --accent  #FF7F00   naranja (acento principal)
--s1     #0A2540   superficie 1     --a2      #3d9be0   azul
--s2     #0e2d4d   superficie 2     --a3      #ff9d3d   naranja claro
--s3     #13355a   superficie 3     --a4      #6aa9dd   azul claro
--b      #1d3a5c   borde            --text    #eaf1f9   texto
--b2     #274a72   borde 2          --muted   #7a8ca3   texto atenuado
                                    --danger  #f05050   error
```

Fuentes: Space Mono (monospace, títulos y datos), DM Sans (cuerpo).

## Desarrollo

```cmd
python server.py                  REM usa el puerto de config.json
python server.py --port 8080      REM override

npm test                          REM tests de lógica del player (Node stdlib)
```

Admin en `/admin.html`, player en `/player.html?screen=NOMBRE`, emparejar en
`/pair`.

**Tests:** `tests/schedule.test.js` extrae las funciones directamente de
`player.html` y las ejecuta en un `vm` de Node con un `Date` falso inyectado.
Se hace así porque el JS es inline en un HTML monolítico y no hay nada que
importar; copiar las funciones al test crearía una copia que se desincroniza al
primer cambio. Mismo patrón reutilizable para el resto de la lógica del player.

## Pendiente

1. **Asistente de primer arranque para el puerto** — `config.json` mantiene
   `first_run: true` pero nadie lo lee. El único flujo de "primera vez" que
   existe es el de contraseña, en `login.html`.
2. **Unificar las dos rutas de distribución** (Python vs Electron) o decidir
   explícitamente cuál se abandona.
3. **Cierre del navegador en TVs LG (webOS) sin causa clara** — un caso real
   en campo: el navegador integrado se cierra cada ~2 minutos incluso con una
   playlist de solo imágenes. Se descartaron protector de pantalla, ahorro de
   energía, HDMI-CEC/SimpLink y domótica. Se aplicaron dos mitigaciones del
   lado del código (fuga de reconexión SSE arreglada, recarga de seguridad
   cada 4h) que no explican por sí solas un cierre tan rápido y regular.
   Investigación en pausa a la espera de una prueba de control (una web
   cualquiera en el mismo navegador) que aísle si es del TV o de la página.

   **Revisado el 2026-08-11: la fuga explica el cierre mucho mejor de lo que
   decía este apunte.** La valoración anterior asumía acumulación lineal («se
   acumulaban con las horas»), y no lo es: un `EventSource` con error
   *reintenta solo*, por defecto. Sin el `es.close()` que faltaba, la conexión
   muerta seguía reintentando por su cuenta **y además** se creaba una nueva
   cada 4 s, que a su vez fallaba y hacía lo mismo. Crece multiplicándose, no
   sumando: con un WiFi flojo son decenas de conexiones en dos minutos.
   Queda por saber si el arreglo (1.0.8) llegó a la tienda. Que el código
   estuviera sin commitear hasta el 2026-08-10 no implica que no se compilara:
   los instaladores de 1.0.7, 1.0.8 y 1.0.9 están en `dist/installer/` con
   fecha de ese mismo día. **Primer paso, antes de teorizar nada: mirar qué
   versión corre la tienda** (`/api/info` lo devuelve, o el panel). Si es
   anterior a la 1.0.8, actualizar y volver a observar; si ya la tenía y sigue
   cayéndose, la fuga queda descartada y toca la prueba de control.
4. **Preservar ediciones a medias durante un repintado** — `admin.html` hace
   `es.onmessage=()=>loadAll()`, que reconstruye la interfaz ante cualquier
   aviso SSE y se lleva por delante lo que hubiera a medio escribir. Es un
   comportamiento anterior a la sincronización de dos paneles, no introducido
   por ella. Para que muerda hay que estar tecleando en un equipo en el mismo
   instante en que otro publica, y una sola persona no tiene dos pares de
   manos. Se arregla el día que haya dos empleados editando a la vez; el
   arreglo de raíz es guardado granular por entidad (`/api/items/<id>`), que
   hoy es desproporcionado: `saveContentLocal()` se llama desde doce sitios de
   un `admin.html` de 214 KB.

   **No confundir con el arreglo de la 1.0.11**, que es otro fallo distinto:
   `/api/screens/config` (crear pantalla, asignar playlist, videowall —
   `saveScreensConfig()`) sobrescribía `content["screens"]` sin comprobar
   `rev` y sin avisar a otros paneles, así que un panel con datos viejos
   podía borrar en silencio lo que acababa de guardar otro equipo — el mismo
   síntoma que el fallo de las tasas que arregló la 1.0.10, pero en la ruta
   de pantallas. Ya tiene el mismo `rev`/409 que `/api/content`. El punto 4
   de aquí arriba sigue sin arreglar: es el caso, más raro, de estar
   tecleando en el mismo instante en que llega un SSE.
5. **App propia de reproductor para Android TV** — un navegador de kiosco
   hecho a medida, para sticks tipo Xiaomi/Google TV. El núcleo es pequeño:
   un `WebView` a pantalla completa apuntado a
   `/player.html?screen=NOMBRE`, `keepScreenOn`, un receptor de
   `BOOT_COMPLETED` para arrancar al enchufar la tele, y reintento con espera
   creciente en `onReceivedError`. El `WebView` es Chromium, así que soporta
   SSE, IndexedDB y el caché offline que ya usa el player.

   **No se hace como parche de un fallo**, y menos del punto 3: la
   alternativa de mercado (Fully Kiosk Browser, ~7 €) lleva años resolviendo
   lo que de verdad muerde —fiabilidad del arranque automático en cada
   fabricante, restricciones de segundo plano, recuperación tras un cierre—,
   y eso no son 200 líneas. Además mete un segundo lenguaje y un SDK con
   Gradle en un proyecto cuya regla fundacional es *sin paso de compilación*.

   **Se hace el día que el problema sea la instalación en tienda nueva**, no
   una tele concreta: con app propia el cliente enchufa el stick y le sale la
   pantalla de emparejar, sin explicarle a nadie qué es un APK, la app
   Downloader ni un navegador de kiosco. Ahí deja de ser un parche y pasa a
   ser mejor producto.

   **Coste real, medido el 2026-08-11: menor de lo estimado.** El toolchain ya
   está instalado en el equipo de desarrollo —Android Studio con su JDK, SDK
   `android-36.1`, build-tools hasta `37.0.0`, `adb` y licencias aceptadas—,
   así que la descarga de 3-4 GB que se contaba como el grueso no existe.
   Ninguno está en el PATH: hay que invocarlos por ruta.

   Lo que sí manda sobre el calendario es que **esto no se puede probar sin el
   aparato**. Escribir la app y compilar el APK cabe en una sesión; que arranque
   y pinte el player, el mismo día. Pero fiarse de dejarla desatendida en una
   tienda son días de *observación*, no de trabajo: si vuelve tras un corte de
   luz, si aguanta que el WiFi caiga de madrugada, si arranca de verdad al
   encender el televisor. Ese bucle va al ritmo de quien tenga el stick
   delante, no al de quien escribe el código.

## Gotchas de despliegue

- **Windows Firewall bloquea el acceso desde otros dispositivos por
  defecto.** El servidor escucha en `0.0.0.0` sin problema, pero sin una
  regla de entrada explícita para el puerto usado (80/9000 típicamente), un
  TV o tablet en la misma red se queda cargando indefinidamente (no da error,
  simplemente no responde) aunque el PC vea al servidor perfectamente por
  `localhost`. El instalador no crea esta regla. Se soluciona con:
  `New-NetFirewallRule -DisplayName "InTeks Display (HTTP)" -Direction Inbound -Protocol TCP -LocalPort 80,9000 -Action Allow -Profile Private`
  (requiere PowerShell como administrador).

- **`pick_data_dir()` no siempre elige la carpeta esperada — sin explicar
  todavía.** Al montar una copia de prueba en una carpeta temporal (server.py
  + estáticos + `content.json` propio) para comprobar un cambio a mano,
  `/api/playlist?screen=X` devolvía `{"config": {}}` — como si el
  `content.json` de esa carpeta no existiera — a pesar de que el archivo en
  disco tenía la pantalla configurada y `APP_DIR` (junto al programa, que en
  ese caso era la propia carpeta temporal) debería pasar la prueba de
  escritura de `pick_data_dir()` sin caer a `ProgramData`. Ni `ProgramData\
  InTeks Display` ni `~\InTeks Display` tenían el `content.json` esperado
  tampoco. Sin investigar a fondo — quedó rodeado en vez de resuelto,
  verificando el cambio con la función real de `player.html` ejecutada en
  Node en lugar de contra un servidor vivo. Si vuelve a pasar: mirar primero
  si `pick_data_dir()` cachea `DATA_DIR` en algún sitio entre arranques, o si
  la prueba de escritura (`.signalos-escritura`) puede fallar por un
  antivirus/EDR que bloquee la escritura en `%TEMP%` sin lanzar `OSError`.
