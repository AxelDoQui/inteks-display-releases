# InTeks Display — Contexto para Claude Code

> Actualizado: 21 de noviembre de 2026 (v1.0.85). Este documento describe el estado **real** del
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

### Servidor — `server.py` (~197 KB, stdlib pura)

`ThreadingHTTPServer`: cada conexión en su propio hilo, imprescindible porque
las conexiones SSE de `/api/events` viven indefinidamente y bloquearían al
resto en un servidor de un solo hilo.

Responsabilidades: playlists por pantalla, subida y servido de archivos (con
soporte de HTTP Range para vídeo), SSE para refresco en tiempo real,
autenticación de administrador, emparejamiento de pantallas por PIN, y anuncio
mDNS del nombre de la instalación.

Puerto: lee `config.json`, acepta `--port` como override y **cae al puerto
alternativo automáticamente** si el principal está ocupado (`find_free_port`,
línea 403). Quien necesite saber el puerto real no puede fiarse de
`config.json`.

### Interfaces web

| Archivo | Papel |
|---|---|
| `index.html` | Raíz `/`. Router de arranque: si el dispositivo ya está enlazado (localStorage) redirige al player; si no, a emparejar. |
| `login.html` | Puerta de autenticación. En el primer arranque cambia a modo "crear contraseña". |
| `admin.html` | Panel de administración (~371 KB, monolito). Responsive desde la 1.0.29. |
| `player.html` | Reproductor para pantallas y tablets (~103 KB). |
| `pair.html` | Emparejamiento por PIN. |
| `sw.js` | Service worker de la PWA. Solo se activa bajo HTTPS o localhost. |
| `visor-cliente/` | Visor de cliente: recuadro del mostrador en la tablet, servido por InTeks Display (`/api/visor/*`). Trae `LEEME.md` y `PRUEBAS.md`; tests en `tests/test_visor_cliente.py` y `tests/visor-cliente-player.test.js`. **Sin commit y sin probar en aparatos reales.** |

### Secciones del admin

Pantallas · Librería · Paquetes · Divisas · Clima · Noticias/ticker ·
Texto/precios · URLs web · Comparativa · Cuenta atrás · QR · Ficha de producto ·
Ajustes · Ayuda

**Ayuda es el texto largo sobre aparatos, y `MANUAL.md` el resumen** (desde la
1.0.34). Se decidió así porque no hay paso de compilación con el que generar uno
del otro, y dos textos escritos a mano se separan — ya pasó con las divisas y
con `CURRENCY_DB`. `tests/ayuda-aparatos.test.js` vigila tres cosas: que no
vuelvan las instrucciones caducadas (`python server.py`, el puerto `8080`), que
estén las seis fichas de aparato y las seis de diagnóstico, y que **el Fire TV
Stick siga marcado como no probado** — cuando alguien lo pruebe de verdad, se
quita el aviso y ese test en el mismo commit. Las fichas son `<details>`
nativos: cero JavaScript.

**Paquetes** agrupa varios contenidos para asignarlos juntos a una pantalla
(p. ej. "Promo Enero"). No aparece en ningún roadmap; se añadió sobre la marcha.

### Tipos de slide en el player

`fx` (divisas) · `weather` · `ticker` · `text` · `url` · `video` · `comparison` ·
`countdown` · `qr` · `product`. La imagen es la rama por defecto cuando el tipo
no coincide con ninguno de los anteriores (`player.html:960`).

Cada fila de `fx` admite un `agent` opcional (la ventanilla/agente de pago,
caso Ria y similares con varios puntos de pago por moneda): si viene, el
player la muestra **en su propia línea** bajo la moneda; si no, la fila se ve
igual que un tablero de cambio normal. Iba pegada a la moneda en la misma línea
hasta la 1.0.27, dentro de un `.fx-currency` con `nowrap` + `ellipsis`, y en
cuanto la fila se estrechaba se cortaba justo el dato que distingue una
ventanilla de otra («Peso filipino · RIA & Pala…»). De las ocho ventanillas
configuradas en campo, siete pasan de 21 caracteres y el corte empezaba sobre
los 27. La extensión de Chrome ya elegía un
agente para decidir la tasa (`elegirAgente` en `parser.js`) pero lo
descartaba antes de mandarlo — desde 1.0.11 viaja hasta la pantalla. También
se puede escribir a mano en el editor de filas del admin.

Otras capacidades del player: rotación arbitraria vía `config.rotation`,
videowall en dos pantallas (`wall_mode` + `wall_pos`, que recorta la imagen con
`object-position` a izquierda o derecha), horario con imagen de standby, barra
de progreso y refresco del clima cada 15 minutos.

**Prioridad en el orden aleatorio (desde 1.0.20).** Un contenido de la
playlist con `priority: true` (se marca con ⭐ en el editor del admin) se
reparte aparte del resto en `ordenReproduccion()` (`player.html`) para
garantizar una cadencia fija — `config.priority_every` pases, 4 por defecto —
en vez de quedar sujeto al azar. El resto de la vuelta se sigue barajando y
sin repetirse; solo lo marcado ⭐ puede repetirse dentro de la misma vuelta,
si eso es lo que hace falta para cumplir su cadencia con pocos contenidos
prioritarios y una vuelta larga. Con varios marcados, se turnan en vez de
amontonarse en el mismo hueco. Solo tiene efecto con `shuffle` activo: con
orden fijo la posición ya la decide quien arrastra la playlist.

**Resiliencia sin servidor:** el contenido nunca fuerza una recarga de la
página (llega por SSE, `connectSSE()`, y repinta solo); lo último reproducido
se cachea en IndexedDB (imágenes/vídeos) y localStorage (playlist/config) para
sobrevivir a un arranque en frío sin servidor. Aparte de eso hay una recarga de
seguridad cada 4 horas (`RELOAD_SEGURIDAD_MS`), pensada para navegadores de TV
con poca memoria (el de LG webOS es un caso documentado por el propio soporte
de LG) — segura porque la caché ya deja algo pintado antes de que llegue.

**Recarga al actualizar (desde 1.0.18).** `/api/playlist` devuelve `version`;
el player guarda la que vio al cargar y, si en un refresco posterior es otra,
hace `location.reload()` (`debeRecargarPorVersion`). Sin esto, **instalar no
cambiaba lo que la pantalla estaba mostrando**: el archivo del disco cambia,
pero la página que el televisor lleva horas abierta sigue ejecutando el JS
viejo —el contenido se refresca por SSE, el código no— hasta la recarga de
seguridad de las 4 h o hasta que alguien reinicie el aparato. Pasó en campo con
la 1.0.17: `/api/info` decía 1.0.17 y el televisor pintaba el fallo anterior.

Dos consecuencias que hay que tener presentes: **`/api/info` dice qué sirve el
servidor, no qué ejecuta la pantalla**, y una pantalla solo empieza a
auto-recargarse cuando ya ha cargado el código de 1.0.18 o posterior — al
actualizar desde una versión anterior hay que recargarla a mano una última vez.
La regla es tacaña a propósito: exige dos versiones presentes y distintas, así
que ni un servidor que no manda el dato ni un reinicio con la misma versión
provocan una recarga.

**Ventana de materialización (desde 1.0.16).** `rebuildSlides()` monta todas
las diapositivas en el DOM, pero **sin `src`**: guarda la ruta en
`data-medio` y `materializarVentana()` la pone solo a las que caen dentro de
`ventanaSlides(orden, posOrden, RADIO_VENTANA)` —la anterior, la actual y las
dos siguientes—, quitándosela a las demás (y en vídeo, `preload` y `load()`
para soltar el búfer).

Sin esto, 50 contenidos son 50 imágenes decodificadas a la vez: las
diapositivas en espera están en `opacity:0`, que **se sigue pintando**, no en
`display:none`. Un 1080p descomprimido son ~8 MB, y una caja Android de 1-2 GB
se muere. La ventana se calcula sobre el **orden de reproducción**, no sobre
los índices: con el orden aleatorio la siguiente no es la de al lado.

Dos cosas que se dan por sabidas al tocar esto: la anterior sigue en la ventana
porque aún se está animando su salida, y el radio ≥1 existe para que la
siguiente llegue ya decodificada — materializar justo al mostrarla da un
parpadeo negro. **Sin cubrir todavía:** las imágenes internas de los módulos
`product` y `comparison`, que se crean con `src` directo dentro de su
`build*Slide`.

**Cabecera del tablero de divisas.** El título compite por el ancho con el
logo y la fecha. Dos cosas que hay que saber antes de tocarla:

- Las reglas de pantalla completa están acotadas a **hijos directos**
  (`.slide>img`, `.slide>video`, `.slide>iframe`). Con `.slide img` a secas
  (especificidad 0,1,1) ganaban a `.mod-fx-logo` (0,1,0) y el logo recibía
  `height:100%`: salía a 99 px donde su CSS pedía 20, se llevaba el 26 % del
  ancho y dejaba el título en «TIPOS DE…». Les pasaba igual a las imágenes de
  `product` y `comparison`.
- `ajustarCabeceraFx()` (`player.html:1158`) apila el título en su propia fila
  cuando ocupa dos líneas, para pantallas verticales. Corre **antes** de medir
  el hueco de las filas, porque la cabecera cambia de alto al apilarse.
  Preguntar al DOM si el texto está recortado **no funciona**:
  `-webkit-line-clamp` recorta durante el diseño y el elemento jura que cabe.
  Y hay que remedir al cargar el logo: hasta que la imagen llega ocupa cero y
  el título parece caber de sobra.

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

Manifest V3. Envía tipos de cambio a InTeks Display con un clic, vía
`POST /api/fx-update` autenticado con el token de API que se copia desde
*Ajustes → Seguridad*. Sirve también en remoto a través del túnel de
Cloudflare.

**Desde 1.0.24: sin detección automática de página.** Hasta la 1.0.23,
`content.js` escaneaba el DOM de la pestaña activa cada vez que se abría el
panel (y cada 30 s mientras seguía abierto) y ofrecía lo detectado bajo
«DETECTADO EN ESTA PÁGINA». Se quitó de la parte que corre sola —el usuario no
podía verificarlo en todas las webs que usa— y el panel lateral pasó a un
selector de país/moneda con buscador (`fxPickerOptions`/`fxFilterOptions` en
`parser.js`, duplicadas de `FX_COUNTRIES` en `admin.html`, mismo patrón y
mismo test de sincronización que ya existía para `CURRENCY_DB`: ver
`tests/fx-countries-sync.test.js` y `tests/currency-db-sync.test.js`), más un
formulario de código a mano para lo que no esté en la lista. `content.js`
ahora solo inyecta y muestra/oculta el iframe del panel; ya no escanea nada.

El motor de escaneo (`scanPage`, `detectInText`, `extractRate`, `extractAgent`,
`elegirAgente`) **sigue en `parser.js`, sin usarse** — no se borró porque
tiene su propia cobertura de tests (`ria-agente-en-scan.test.js`,
`ria-eleccion-agente.test.js`, `extension-rate-agent-digits.test.js`,
`extension-rate-format.test.js`) y borrarlo no era parte de lo pedido. Si
algún día hace falta un escaneo manual (botón "leer esta página" en vez de
automático), la lógica ya está.

**Consecuencia:** el selector multi-agente (Ria y similares, `agentOpciones`/
`chrome.storage.local.agentPrefs`) solo tenía sentido cuando la página traía
varias filas para la misma moneda a la vez —eso solo lo daba el escaneo—, así
que desapareció del panel lateral con él. El campo `agent` de una fila (la
ventanilla/agente de pago) solo se puede fijar ahora desde el editor de filas
del admin, como cualquier tablero que no usa la extensión.

### Bot de Telegram (desde 1.0.19)

Hasta la 1.0.18, Telegram era de una sola dirección: `enviar_telegram()`
empuja avisos (pantalla caída, tasas viejas, disco lleno) y nadie puede
preguntarle nada. `_bot_loop()` (hilo de fondo, junto a `_vigilante`) añade
un único comando de solo lectura, `/estado`, por long-poll
(`getUpdates`, sin webhook ni URL pública) contra el mismo `telegram_token` y
`telegram_chat_id` que ya usan los avisos — no hay ajuste nuevo que configurar.

`construir_estado()` arma la respuesta con los mismos datos que ya calcula
`revisar_avisos()` (pantallas en línea/caídas, tableros al día/vencidos) más
disco y versión. `_responder_mensaje()` solo contesta al `chat_id` que
coincide con `telegram_chat_id`; a cualquier otro, silencio total —ni
siquiera un error, para no confirmarle a un desconocido que el bot existe.
No puede reiniciar el servidor ni dar el PIN de emparejamiento: es un chat,
no una llave.

Al arrancar (o al activar el token desde el panel sin reiniciar: el hilo
relee la configuración en cada vuelta) descarta con `offset=-1` lo que
Telegram tuviera pendiente de hasta 24 h atrás, para no contestar un
`/estado` de ayer con los datos de ahora como si fuera de este momento.

### App de kiosco Android — `android/` (desde 1.0.26)

Sustituye a Fully Kiosk Browser en las cajas Android que reproducen el player.
Kotlin, sin dependencias de terceros (`HttpURLConnection` de la stdlib, nada de
OkHttp ni Compose). **Es lo único del repo que necesita compilarse**, y por eso
está acotada a su carpeta: el servidor y las páginas se siguen editando y
sirviendo tal cual.

La app es pequeña a propósito porque la inteligencia de producto ya estaba en la
web —identidad, emparejamiento, caché offline, SSE, recarga por versión—. Solo
aporta lo que un navegador no puede:

- **Encuentra el servidor sola**: barre la subred contra `/api/info` (puertos 80
  y 9000, 32 sondas en paralelo, 8 s de tope) y valida que la respuesta trae
  `mdns_name` y `player_url`. Sin mDNS y sin tocar `server.py`. Solo barre redes
  de /24 o menores; en una más grande pide la dirección a mano.
- **Arranca al encender y ENCIENDE LA PANTALLA.** `FLAG_KEEP_SCREEN_ON` solo
  impide que se duerma; no despierta una apagada. Tras un corte de luz la caja
  tarda ~118 s en llegar a `BOOT_COMPLETED` y se duerme por el camino, así que
  hace falta `FLAG_TURN_SCREEN_ON` más un wake lock con `ACQUIRE_CAUSES_WAKEUP`.
- **Se levanta sola** con un latido de `AlarmManager` (2 min), que vive en el
  sistema y sobrevive a que muera el proceso. En API 25 no existe
  `onRenderProcessGone`, así que un render sin memoria se lleva la app entera.
- **Sobrevive a un cambio de IP**: guarda el nombre de pantalla en
  `SharedPreferences`, **fuera del WebView**, porque `localStorage` y las
  cookies van por origen y un cambio de IP dejaría la pantalla sin identidad.
- **Nunca pide la direccion en un escaparate (desde 1.0.32).** Ver el gotcha
  del corte de luz mas abajo. `queHacerSinServidor()` (`Arranque.kt`) decide:
  solo se abre el formulario si la caja **no ha visto un servidor jamas** —la
  estan instalando— o si alguien **pulsa OK** en la pantalla de busqueda. Y la
  direccion guardada **ya no se borra nunca**: solo la reemplaza un barrido que
  encuentre otra.
- **Kiosco reversible**: pantalla completa inmersiva, `ATRAS` ignorada, y vuelve
  al frente a los 4 s si algo la tapa. `INICIO` y `RECIENTES` **no se pueden
  bloquear** desde una app normal. Salida de mantenimiento: **cinco pulsaciones
  de `ATRAS` en menos de tres segundos** apartan la app cinco minutos.

Ajustes del `WebView` que, si faltan, dan fallos que no parecen lo que son:
`usesCleartextTraffic` (el servidor es HTTP plano), `domStorageEnabled` (sin él
la pantalla pierde su identidad en cada reinicio) y
`mediaPlaybackRequiresUserGesture=false` (sin él los vídeos no arrancan solos).

**Compilar:** `JAVA_HOME` al JDK de Android Studio y `gradlew assembleDebug`.
AGP 9 **trae Kotlin dentro**: aplicar `org.jetbrains.kotlin.android` aparte
revienta. `local.properties` lleva las barras **dobles** o el build muere con un
`java.io.IOException: Invalid file path` que no menciona ni el SDK ni las
barras. `tools/subir-version.ps1` toca también su `versionName`.

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
GET       /api/playlist        playlist + config + versión del servidor
GET       /api/screens         pantallas registradas
GET       /api/events          SSE, conexión persistente
GET       /api/pin             PIN de emparejamiento vigente
GET       /api/pair-pending    pantallas esperando nombre
GET       /api/update-check    ¿hay versión nueva? (token; ?force=1 salta la caché)
GET       /api/backup          descargar copia de seguridad
POST      /api/login  /api/logout  /api/set-password
POST      /api/pair            enlazar una pantalla con el PIN
POST      /api/pair-request  /api/pair-status  /api/pair-claim
POST      /api/upload  /api/delete
POST      /api/screens/config  /api/screens/delete
POST      /api/screen-unlink   soltar el aparato sin borrar la pantalla
POST      /api/fx-update       divisas desde la extensión (token)
GET/POST  /api/visor/oferta    Visor de cliente: oferta WebRTC del PC (POST con token; GET público, lo lee la pantalla)
GET/POST  /api/visor/respuesta respuesta de la pantalla (POST público, una por oferta; GET con token). /api/visor/cerrar (token). Solo memoria; ver `visor-cliente/`
POST      /api/restore         restaurar una copia
POST      /api/alert-test      mensaje de prueba de Telegram
POST      /api/restart         reiniciar el servidor
GET       /pair                atajo a pair.html
GET       /uploads/*           archivos subidos (soporta Range)
```

## Datos en disco

**Dónde viven lo decide `pick_data_dir()` por la ruta de instalación, no por
los permisos** (desde 1.0.12). Si `APP_DIR` cuelga de `%ProgramFiles%`, los
datos van a `%PROGRAMDATA%\InTeks Display`; en cualquier otro sitio —una copia
de desarrollo— se quedan junto al programa. `SIGNALOS_DATA` manda sobre todo lo
demás y es lo que usan las pruebas.

Antes esto lo decidía **solo** una prueba de escritura sobre `APP_DIR`, escrita
dando por hecho que nadie puede escribir en Archivos de programa. Pero el
servidor arranca como SYSTEM desde la tarea programada, y SYSTEM sí puede: la
prueba pasaba y `DATA_DIR == APP_DIR`, con los datos dentro de Program Files
—justo donde el manual jura que no están, y donde `restablecer-contrasena.py`
se niega a buscar a propósito, así que la recuperación de contraseña no
encontraba la instalación—. Un cambio en el *contexto de ejecución* (clave
`Run` del registro → tarea como SYSTEM) alteró el comportamiento de una
función que nadie tocó. Las instalaciones que vienen de esa época se migran
solas al arrancar (`migrar_datos_antiguos()`), sin borrar la copia vieja.

| Archivo | Contenido | ¿Se versiona? |
|---|---|---|
| `config.json` | puerto, alternativo, nombre mDNS, autoarranque | Sí, es la plantilla por defecto |
| `content.json` | items, pantallas, paquetes, `rev` | No — lo crea vacío `init_file` |
| `screens.json` | registro de pantallas vistas, y `unlink_pending` | No — ídem |
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

**Responsive desde la 1.0.29.** Todo lo que hace usable el panel en tableta y
móvil vive en un bloque propio al final del `<style>`, y **no toca ninguna
regla del CSS de escritorio**: si un cambio obliga a modificar una de arriba,
es señal de que se está haciendo mal. Dos puntos de corte con reparto fijo:

- **≤860 px** — lo que sobra es *ancho de layout*: la barra lateral de 220 px
  pasa a cajón deslizante (`toggleMenu()`), las rejillas fijas se estrechan y
  los botones suben a 44 px.
- **≤560 px** — lo que falta es *sitio para el dedo*: modal a pantalla
  completa, y **campos a 16 px porque iOS hace zoom al enfocar uno con letra
  menor**, lo que obliga a alejar a mano en cada toque.

El **arrastrar y soltar de HTML5 no existe en táctil**, así que playlists y
filas de divisas llevan botones subir/bajar que llaman a `moverPlItem()` /
`moverFxRow()` — las mismas funciones que usa el arrastre, sin abrir rutas de
escritura nuevas. Van también en escritorio a propósito: mantener dos
comportamientos según el ancho hace que el de móvil solo se pruebe en móvil.

**Para fotografiar el panel** hace falta un arnés, por tres razones que no son
obvias: exige sesión (se entra por `/api/login` desde una página del mismo
origen); **abre un `EventSource` que no termina nunca**, y con una petición
viva el presupuesto de tiempo virtual de Chrome no avanza y la captura se
cuelga —hay que inyectar un stub de `EventSource` antes de su JS, que es el
equivalente del `?preview=1` del player—; y **Chrome headless impone un ancho
mínimo de ventana de ~504 px**, así que `--window-size=390` no da un viewport
de 390: hay que meterlo en un **iframe** del tamaño exacto.

## Desarrollo

```cmd
python server.py                  REM usa el puerto de config.json
python server.py --port 8080      REM override

npm test                          REM 266 tests de logica (Node stdlib)
python tests\test_<nombre>.py     REM 19 suites que arrancan el servidor
cd android ^&^& gradlew.bat test  REM 40 tests de la app, sin aparato
```

Para los de la app hay que poner antes `JAVA_HOME` al JDK de Android Studio
(`C:\Program Files\Android\Android Studio\jbr`): no hay `java` en el PATH, así
que un `where java` da falso negativo.

**Trampa al ejecutar las suites de Python:** tener **otro servidor InTeks
levantado** hace fallar `test_reset_password.py` con un `has_password: True`
engañoso. No es el test ni el código: es que se cuela el servidor de al lado.
Pararlo antes de sacar conclusiones.

Admin en `/admin.html`, player en `/player.html?screen=NOMBRE`, emparejar en
`/pair`.

**Un fallo visual se verifica renderizando, no leyendo.** Costó dos arreglos
fallidos el 2026-08-11 (un título que se recortaba: el primer arreglo parecía
impecable y no hacía nada). La receta que funciona, sin dependencias nuevas:

```
SIGNALOS_DATA=<temporal> python server.py --port 8099     # servidor de pruebas
```

y una página con un `<iframe src="player.html?preview=1">` que le inyecta el
item por `postMessage` — igual que hace el admin. **El modo previa no abre
SSE**, así que la página se queda quieta y se deja fotografiar; contra
`player.html?screen=X` el navegador nunca termina de cargar y la captura se
cuelga. Después:

```
chrome --headless --disable-gpu --virtual-time-budget=6000 \
       --window-size=1280,720 --screenshot=out.png  http://127.0.0.1:8099/marco.html
chrome ... --dump-dom                       # para LEER medidas en vez de mirarlas
```

Con `--dump-dom` y un `<div>` donde el marco escribe `getBoundingClientRect()`
del iframe (mismo origen, se puede leer) se miden alineaciones y tamaños reales.
Así se descubrió que el logo medía 92 px donde su CSS pedía 20, y que un
supuesto desalineado de las cotizaciones era 1 px —la foto estaba tomada de
lado—. **Ojo:** `Select-Object -First N` en PowerShell corta la tubería y mata
al compilador o al navegador a media faena; dejó un instalador truncado que
parecía bueno.

**Tests:** `tests/schedule.test.js` extrae las funciones directamente de
`player.html` y las ejecuta en un `vm` de Node con un `Date` falso inyectado.
Se hace así porque el JS es inline en un HTML monolítico y no hay nada que
importar; copiar las funciones al test crearía una copia que se desincroniza al
primer cambio. Mismo patrón reutilizable para el resto de la lógica del player.

## Pendiente

1. **Asistente de primer arranque para el puerto** — `config.json` mantiene
   `first_run: true` pero nadie lo lee. El único flujo de "primera vez" que
   existe es el de contraseña, en `login.html`.

   ~~Del mismo tipo y peor: la casilla «Iniciar con Windows» de Ajustes no la
   lee nadie~~ — **cableada de verdad en la 1.0.21.** `_tarea_autoarranque_estado()`
   y `_fijar_autoarranque()` (`server.py`) consultan y tocan la tarea
   programada real vía `schtasks.exe` en vez de un valor decorativo en
   `config.json`: `GET /api/config` devuelve el estado real, y `POST
   /api/config` la crea (reutilizando `registrar-tarea.ps1`, sin duplicar la
   búsqueda de `pythonw.exe`), habilita o deshabilita según corresponda.
   Como hace falta ser administrador para tocar el Programador de tareas de
   Windows, el guardado puede fallar —normalmente por permisos—; cuando pasa,
   el panel lo dice explícitamente en vez de fingir que se aplicó.

   **En este equipo de desarrollo concreto, la tarea sigue sin registrar**
   (comprobado de nuevo el 2026-08-13: `Get-ScheduledTask "InTeks Display"` no
   encuentra nada). La sesión de Claude Code no tiene permisos de
   administrador para registrarla desde aquí; el comando, que hay que correr
   elevado y **apuntando a la instalación, no a la copia de desarrollo**, es:

   ```powershell
   & "C:\Program Files\InTeks Display\registrar-tarea.ps1" -AppDir "C:\Program Files\InTeks Display"
   ```

   Se le ha dado ya varias veces, sin confirmación de que lo haya hecho. Si
   este PC pierde corriente,
   el servidor no arrancaría solo hasta que se registre.

2. **Unificar las dos rutas de distribución** (Python vs Electron) o decidir
   explícitamente cuál se abandona.
3. ~~**Cierre del navegador en TVs LG (webOS)**~~ — **cerrado el 2026-08-11**,
   y no por código. Ver «El navegador de un Smart TV se cierra solo» en
   *Gotchas de despliegue*.
4. **Preservar ediciones a medias durante un repintado** — `admin.html` hace
   `es.onmessage=()=>loadAll()`, que reconstruye la interfaz ante cualquier
   aviso SSE y se lleva por delante lo que hubiera a medio escribir. Es un
   comportamiento anterior a la sincronización de dos paneles, no introducido
   por ella. Para que muerda hay que estar tecleando en un equipo en el mismo
   instante en que otro publica, y una sola persona no tiene dos pares de
   manos. Se arregla el día que haya dos empleados editando a la vez; el
   arreglo de raíz es guardado granular por entidad (`/api/items/<id>`), que
   hoy es desproporcionado: `saveContentLocal()` se llama desde doce sitios de
   un `admin.html` de 371 KB.

   **No confundir con el arreglo de la 1.0.11**, que es otro fallo distinto:
   `/api/screens/config` (crear pantalla, asignar playlist, videowall —
   `saveScreensConfig()`) sobrescribía `content["screens"]` sin comprobar
   `rev` y sin avisar a otros paneles, así que un panel con datos viejos
   podía borrar en silencio lo que acababa de guardar otro equipo — el mismo
   síntoma que el fallo de las tasas que arregló la 1.0.10, pero en la ruta
   de pantallas. Ya tiene el mismo `rev`/409 que `/api/content`. El punto 4
   de aquí arriba sigue sin arreglar: es el caso, más raro, de estar
   tecleando en el mismo instante en que llega un SSE.
5. ~~**App propia de reproductor para Android TV.**~~ — **hecha en la 1.0.26**
   (2026-08-13). Ver «App de kiosco Android» más arriba. Se escribio y se probo
   en una caja real -MXQ PRO 4K, Amlogic S905W, Android 7.1.2 API 25, 990 MB de
   RAM, la mas basica del mercado- y no en un emulador.

   La vara de medir que se puso aqui era «igual de fiable que Fully, sin pagar
   7 EUR por pantalla». En dos cosas la supera y conviene saber por que: Fully
   necesita que alguien pegue la URL a mano, y si el PC cambia de IP hay que ir
   pantalla por pantalla. Esta la encuentra sola y se rebusca.

   **Lo que sigue sin poder responderse desde aqui** es lo que ya decia este
   punto: si aguanta dias encendida, si vuelve tras un corte de luz de verdad
   -no un `adb reboot` ordenado- y como renderiza el tablero de divisas con el
   WebView que carga esa caja, que resulta ser **Chrome 62 y no soporta
   `clamp()`**. Ese bucle va al ritmo de quien tenga el aparato delante.

   Queda tambien **distribuir el APK**: hoy se instala con `adb install`, y va
   firmado con la clave de depuracion, asi que el dia que se firme con otra
   habra que desinstalar antes.

6. ~~**Bot de Telegram que responda, no solo que avise.**~~ — **hecho en la
   1.0.19.** Ver «Bot de Telegram» más abajo.

7. **IDEA APARCADA — carta de productos a la carta, lanzada a una pantalla.**
   Planteada el 2026-09-01 y **aparcada por coste**: «después veo si la
   implemento, ya que sale algo cara». **No empezar sin que lo pida.**

   Lo que quiere: enseñarle al cliente un listado de productos con sus sabores
   en una pantalla concreta, **manejándolo él desde el móvil** mientras
   atiende, y que la pantalla vuelva luego sola a su programación.

   **Son dos piezas de coste muy distinto, y por eso sale cara:**

   - **El mando a distancia — pequeño.** Casi todo existe: `notify_screen(sid)`
     ya empuja a una sola pantalla, `/api/playlist` ya es el embudo donde el
     servidor decide qué ve cada una (el mismo por el que se resuelven los
     paquetes), y el player repregunta cada 15 s por su cuenta. Si el estado
     («la pantalla 3 muestra X hasta las 18:42») vive en el servidor, **la
     vuelta atrás sale gratis y funciona aunque el SSE no llegue nunca** — que
     es la lección de la 1.0.31 aplicada: el temporizador no puede estar dentro
     del televisor, o una tele que se apaga y enciende se queda con la carta
     puesta para siempre.
   - **El módulo de carta — esto es lo caro, y no por el player.** Añadir un
     tipo de diapositiva es rutina, hay diez y todos siguen el mismo patrón. Lo
     costoso es **su editor en el panel**: sería el formulario más complejo que
     tendría `admin.html` —una lista dentro de otra lista, productos con sus
     sabores— en un monolito de 371 KB, y el único precedente parecido son las
     filas de divisas.

   **Orden natural si se retoma:** módulo primero, mando después. El mando sin
   nada que lanzar no se puede probar de verdad.

   **Botón físico: viable, y hay una opción claramente mejor.** Un botón wifi
   (Shelly Button o similar, ~10-15 €) que haga una petición HTTP con
   `X-SignalOS-Token` — **el mismo camino que ya usa la extensión de Chrome**,
   sin tocar el servidor ni la app Android. Un mando Bluetooth emparejado a la
   caja también valdría, pero hablaría con la *pantalla* en vez de con el
   *servidor*, que es donde vive la verdad, y limita el alcance a unos metros.
   Límite de cualquier botón: **es un solo bit**, así que la pantalla y el
   contenido van preconfigurados; para elegir entre varias cartas, gana el
   móvil.

   **Dos decisiones que hay que tomar antes de escribir código:** caducidad en
   el servidor **sí o sí** (que el escaparate no amanezca con la carta puesta
   porque alguien no pulsó «Terminar»), y qué hacer al lanzar a una pantalla
   apagada o fuera de horario — avisar, no fallar en silencio.

## Gotchas de despliegue

- **No te fíes de «el aviso por SSE se entregó» (desde 1.0.31).** El servidor
  **no sabe que una conexión está muerta hasta que le falla una escritura**, y
  las primeras se limitan a encolarse en el búfer del sistema sin dar error
  (ver `tests/test_sse_reconexion.py`). Así que contar a cuántos clientes se
  escribió **no distingue una tele viva de una cuyo wifi acaba de caerse**.

  Mordió al arreglar el desenlace: desenlazar era un *mensaje al aire*, no un
  estado — se mandaba `unlink:<sid>` a quien escuchara en ese instante y no
  quedaba constancia. Con la tele apagada el aviso se perdía en silencio, el
  aparato volvía creyéndose la misma pantalla y el nombre quedaba ocupado: «a
  veces al desvincular no se desvincula y no me deja reciclarla». La primera
  versión del arreglo solo apuntaba el desenlace *si no se había podido
  entregar*, y el propio test la tumbó por lo de arriba.

  **Ahora `unlink_pending` se apunta SIEMPRE** en `screens.json` y se entrega en
  la primera conexión `/api/events` del aparato, en el mismo sitio y con la
  misma forma que la «anti-resurrección» de las pantallas borradas. Se borra al
  entregarlo —si no, un aparato reenlazado se desenlazaría en bucle— y también
  al reenlazar, porque `pair-claim` rehace la entrada entera. **El player no
  cambió**: ya sabía reaccionar a `unlink:`, así que las pantallas instaladas se
  benefician sin tocarlas. Regla general: **si algo tiene que pasar sí o sí, no
  puede depender de que el aparato esté escuchando justo entonces.**

- **El player usaba CSS que el navegador de la caja no entiende (cerrado en la
  1.0.33).** Aviso de campo: «a veces el contenido no se ve como debe», y
  «depende del televisor». No era sobrebarrido: la caja carga
  `com.android.chrome` **62**, de 2017, y en CSS **una declaracion con propiedad
  desconocida o valor invalido se descarta entera y en silencio**. El `<style>`
  de `player.html` tenia **58** de esas.

  Medido con el arnés de render, mismo tablero a 1280x720: `.slide` salia
  **1116x106** en vez de 1280x720, las filas desbordaban (300 px en un hueco de
  23) y toda la letra caia a 16 px. La causa estructural era **una linea**:
  `.slide{position:absolute;inset:0}` — `inset` es Chrome 87, y sin el un
  elemento absoluto se encoge al tamaño de su contenido.

  **Por que no se vio antes:** la previa del admin corre en el navegador del
  usuario, que es moderno. **Lo que el panel enseña no es lo que pinta la caja.**

  Lo que hay que saber al tocar el `<style>`, y lo vigila
  `tests/css-respaldos.test.js`:

  - El respaldo va **delante** y la declaracion moderna **detras**. Al reves no
    hace nada.
  - El respaldo de `clamp(A,B,C)` es **B**, el termino de en medio, no el
    minimo: `vw`/`vh`/`vmin` son de Chrome 26 y asi una pantalla vieja conserva
    la letra fluida. Con A, un 4K se quedaria con letra de movil.
  - **Hay dos formas de fallar y solo una admite respaldo.** `font-size:clamp(…)`
    es un **error de parseo**: se descarta y gana la anterior. Pero
    `font-size:var(--x)` con un `clamp()` dentro de `--x` es **invalida en tiempo
    de valor calculado**, y eso **no** vuelve a la anterior: pone la propiedad en
    «heredado». Por eso **ninguna custom property puede llevar sintaxis moderna
    dentro** — el test lo prohibe. Se descubrio renderizando: con el respaldo
    puesto, el titulo seguia saliendo a 16 px.
  - Los seis `min()` del tablero **no tenian respaldo estatico posible** (en
    horizontal manda el alto, en vertical el ancho). Los resuelve `fitRows()`,
    que ya medía ambos, publicando el resultado en variables.
  - En **grid** hay respaldo exacto y gratis: `grid-gap`, de Chrome 57. En
    **flex** no, y los margenes van dentro de `@supports not (gap:1px)`: sueltos
    se sumarian al `gap` en los navegadores modernos.

  Resultado medido: Chrome 62 y un navegador moderno dan **el mismo pixel** en
  las seis medidas del tablero. **Sin verificar en aparato**: falta instalarlo y
  mirar la caja de la tienda.

- **Un corte de luz ponia el formulario de la direccion en el escaparate
  (cerrado en la 1.0.32).** Caso real en tienda: vuelve la luz, la caja Android
  arranca en ~118 s, el PC tarda mas —Windows y luego el servidor—, y el
  escaparate amanecia con «Escribe la direccion del servidor» y un campo de
  texto a la vista de la calle. **No era una carrera desafortunada: pasaba
  siempre.** La escalera de reintentos (2-4-8-16 s) esta calibrada para «el
  servidor se ha reiniciado», que son segundos; a los ~35 s daba por mala una
  IP guardada perfectamente buena, **la borraba**, barria 8 s sin exito y —como
  `algoPintado` seguia en `false`— concluia que tocaba pedir la direccion.

  Dos errores encadenados, y el segundo es el que enseña algo: **`algoPintado`
  era la pregunta equivocada.** Pedir una direccion solo tiene sentido si hay
  **alguien delante**, y «¿he pintado algo?» no responde a eso — en un arranque
  en frio es `false` justo cuando mas desatendida esta la pantalla. Ahora la
  señal es explicita: `base == null` (nadie la ha instalado todavia) o una
  **pulsacion de OK** en el mando, que un escaparate no produce solo.

  Y el primero: **no se tira un dato bueno antes de tener con que sustituirlo.**
  `base` solo se reemplaza cuando un barrido encuentra otra cosa. Ojo al
  arreglar esto de nuevo: la espera de reintento **no puede ser la misma** con
  el escaparate en marcha (60 s, la tienda ya esta servida desde la cache) que
  con la pantalla en gris (15 s, cada segundo es escaparate vacio) —
  `esperaSinServidorMs()`.

  **Sin verificar en aparato:** el arreglo esta cubierto por
  `ArranqueTest.kt` (9 tests) pero **no se ha reproducido un corte de luz real**
  con la 1.0.32 instalada. Es lo que falta para darlo por cerrado.

- **Dos instalaciones con el mismo token de Telegram se pelean por el bot.**
  Visto el 2026-08-13 en el registro: `[bot] no se pudo leer mensajes: HTTP
  Error 409: Conflict`, cada pocos segundos. **`sendMessage` admite muchos
  emisores a la vez —por eso los avisos llegan de todas las tiendas— pero
  `getUpdates` solo admite UN lector por token.** Así que `/estado` lo contesta
  la instalación que tenga la conexión en ese instante, y la otra ni se entera
  de que le preguntaron. No es que el bot «no detecte» una tienda.

  Viene de montar la tienda restaurando una copia: `config.json` viaja con el
  token **y el nombre de instalación** dentro, así que además las dos firman
  igual y cuesta saber cuál te contestó. Arreglo de quince minutos y cero
  código: **un bot por instalación**, otro token de @BotFather. Se propuso un
  bot central que agregara todas y el usuario lo aparcó el 2026-08-13.

- **El proveedor de WebView que carga una caja Android no es el que dice la
  versión instalada.** En la MXQ de pruebas está instalado
  `com.google.android.webview` 119, pero el sistema carga
  `com.android.chrome` **62**, de 2017. `dumpsys webviewupdate` no devuelve
  nada en API 25: la única forma de saberlo es el `logcat`
  (`WebViewFactory: Loading …`). Importa porque **Chrome 62 no soporta
  `clamp()`**, que llegó en el 79, y el player lo usa para dimensionar el
  tablero. Se puede forzar el otro con
  `cmd webviewupdate set-webview-implementation com.google.android.webview`.

- **Una captura en negro no significa que el WebView no pinte.** `screencap`
  devuelve negro puro con el display apagado. **Mirar `dumpsys power`
  (`mWakefulness`) antes de culpar al renderizador**, y medir el píxel en vez
  de mirarlo: el fondo del player es `#07182b`, muy oscuro, y a ojo pasa por
  negro.

- **Una pantalla viva podía quedar marcada «offline» para siempre (cerrado en
  la 1.0.21).** Caso real: «Pantalla Exterior (LG)» servía contenido con
  normalidad —el bot de `/estado` la veía conectada— y el panel la mostraba
  caída. Causa: carrera entre hilos de `/api/events`. Cada conexión SSE corre
  en su propio hilo (`ThreadingHTTPServer`), y un `EventSource` reconecta solo
  por su cuenta ante un corte de wifi. Si la reconexión llegaba **antes** de
  que el hilo de la conexión vieja se enterara de que la suya había muerto
  —eso tarda hasta el siguiente ping, cada 10 s, porque el hilo solo lee
  fallos de escritura, nunca hace `recv()`—, el hilo viejo, al fin
  detectarlo, pisaba el `connected=True` que acababa de poner la conexión
  nueva con su propio `connected=False`. Sin otro evento que lo corrigiera
  —`connected` solo se pone en `True` una vez, al conectar; los pings
  correctos solo tocan `last_seen`—, quedaba mal indefinidamente aunque la
  pantalla siguiera respondiendo.

  Arreglo: antes de marcar `connected=False`, el hilo que detecta el fallo
  comprueba si `sse_clients[sid]` sigue teniendo alguna conexión registrada
  —una reconexión ya habría quedado ahí—; si es así, no toca nada. Ver
  `tests/test_sse_reconexion.py`: reproduce la carrera con sockets de verdad
  (un simulacro no la reproduce) forzando un cierre abortivo (`SO_LINGER=0`,
  RST) en vez de uno normal, porque un cierre normal no se detectaba dentro
  de un tiempo razonable de prueba en esta máquina.

  Nota aparte, sin resolver: `screens.json` se lee-modifica-escribe sin
  ningún guardián (a diferencia de `content.json`, que tiene
  `contenido_en_edicion()` justo por este motivo). El arreglo de arriba cierra
  la carrera concreta que se vio en campo, pero la clase general de carrera
  —dos hilos escribiendo `screens.json` a la vez— sigue abierta en teoría.

- **El navegador de un Smart TV se cierra solo, y no hay arreglo por código.**
  Caso real y cerrado: un LG con webOS cerraba el navegador integrado cada ~2
  minutos, incluso con una playlist de solo imágenes. Se descartaron protector
  de pantalla, ahorro de energía, HDMI-CEC/SimpLink y domótica. Se aplicaron
  dos mitigaciones —la fuga de reconexión SSE y la recarga de seguridad cada
  4 h— y **con la 1.0.8 o posterior ya instalada en esa tienda, la tele se
  seguía cerrando igual**. Se resolvió sustituyendo el navegador del televisor
  por una caja Android con **Fully Kiosk Browser**, que lleva funcionando
  desde entonces.

  **La fuga de SSE queda descartada como causa** de este caso. El arreglo se
  queda por mérito propio: era un fallo real y feo —un `EventSource` con error
  reintenta solo por defecto, así que sin el `es.close()` la conexión muerta
  seguía reintentando **y además** se creaba una nueva cada 4 s—, pero no era
  esto. La prueba de control que quedaba pendiente (una web cualquiera en el
  mismo navegador) ya no se hará: el televisor está fuera de producción.

  **Qué sacar en limpio:** ante un navegador de fábrica que se cierra, el
  camino corto es cambiar el aparato, no seguir apuntalando la página. El
  player ya sobrevive a un arranque en frío sin servidor, así que sustituir el
  reproductor no cuesta nada más que enchufarlo y pegar el enlace directo. La
  configuración concreta está en `MANUAL.md` → *Con qué reproducir*.

- **Windows Firewall bloquea el acceso desde otros dispositivos por
  defecto.** El servidor escucha en `0.0.0.0` sin problema, pero sin una
  regla de entrada explícita para el puerto usado (80/9000 típicamente), un
  TV o tablet en la misma red se queda cargando indefinidamente (no da error,
  simplemente no responde) aunque el PC vea al servidor perfectamente por
  `localhost`. **Desde 1.0.14 la crea el instalador**, en
  `installer\registrar-tarea.ps1` (`AbrirCortafuegos`), leyendo los puertos de
  `config.json`. A mano:
  `New-NetFirewallRule -DisplayName "InTeks Display (HTTP)" -Direction Inbound -Protocol TCP -LocalPort 80,9000 -Action Allow -Profile Any`

  **`-Profile Any`, no `Private`** —esto costó una sesión entera de campo el
  2026-08-11—. Windows clasifica como **Pública** toda red nueva que no se
  marque a mano, y una regla de perfil Privado **no se aplica** en una red
  Pública: la instalación parece correcta, el comando del manual «funciona», y
  la pantalla sigue sin entrar. Además Windows puede reclasificar una red más
  tarde y tirar las pantallas sin que nadie haya tocado nada.

  Dos cosas que despistan al diagnosticar esto:
  - Las reglas **por programa** van atadas a la ruta exacta del `.exe`. Las que
    Windows crea al preguntar «¿permitir?» cuando arrancas el servidor a mano
    apuntan al Python de desarrollo, no a `{app}\vendor\python\pythonw.exe`,
    así que la versión instalada no hereda ese permiso.
  - Probar `http://<IP-del-propio-PC>/api/info` **desde el propio PC no
    demuestra nada**: ese tráfico no pasa por el filtro de entrada. Hace falta
    otro aparato.

- **En Android hay que usar la IP, no `signage.local`.** Su navegador no
  resuelve mDNS; iOS y macOS sí. Un enlace que funciona en un iPhone puede
  quedarse cargando para siempre en una caja de TV Android, y parece un
  problema de red cuando es de nombres.

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
