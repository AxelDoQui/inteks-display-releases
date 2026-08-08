# InTeks Display — Contexto para Claude Code

> Actualizado: 7 de agosto de 2026. Este documento describe el estado **real** del
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

Otras capacidades del player: rotación arbitraria vía `config.rotation`,
videowall en dos pantallas (`wall_mode` + `wall_pos`, que recorta la imagen con
`object-position` a izquierda o derecha), horario con imagen de standby, barra
de progreso y refresco del clima cada 15 minutos.

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
| `content.json` | items, pantallas, paquetes | No — lo crea vacío `init_file` |
| `screens.json` | registro de pantallas vistas | No — ídem |
| `admin.json` | salt, hash de contraseña, secret de sesión, api_token | **No — secretos** |
| `pin.json` | PIN activo, intentos fallidos, bloqueo | **No — secreto** |
| `uploads/` | archivos subidos | No |

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

1. **Modo festivos** — fechas concretas con horario distinto al del día de la
   semana. Sin implementar.
2. **Asistente de primer arranque para el puerto** — `config.json` mantiene
   `first_run: true` pero nadie lo lee. El único flujo de "primera vez" que
   existe es el de contraseña, en `login.html`.
3. **Unificar las dos rutas de distribución** (Python vs Electron) o decidir
   explícitamente cuál se abandona.
