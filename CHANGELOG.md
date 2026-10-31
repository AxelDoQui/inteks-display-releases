# Cambios de InTeks Display

Qué cambió en cada versión, en cristiano. Sirve para dos cosas: saber qué tiene
instalada cada tienda cuando algo falla, y tener el texto listo si algún día se
enciende el aviso de versión nueva (`update_url` en `config.json`).

Para subir de versión: `powershell -File tools\subir-version.ps1 1.0.2`

---

## 1.0.54 — 2026-10-31

- Editor de playlist: «prioridad ⭐ cada N pases» sale junto a «Orden aleatorio» en vez de esconderse en «Más ajustes». Las estrellas de las filas solo salen con orden aleatorio (que es cuando tienen efecto), salvo en un contenido que ya la tenga marcada, para poder quitársela.

## 1.0.53 — 2026-10-31

- Televisores LG: el navegador del LG cierra la página cada ~2 minutos, así que ahora hay una mini-app para webOS (carpeta `webos\`) que abre el reproductor desde el entorno de apps del TV. `instalar-lg.ps1` la instala pidiendo solo la IP del TV, su passphrase (app «Developer Mode») y la IP del servidor.
- Instalador de Windows: nueva casilla opcional «Herramientas para instalar la pantalla en un televisor LG». Descarga un Node.js portable (comprobando su firma) y la herramienta de LG dentro de la carpeta de la app, sin tocar ningún Node del equipo, y añade «Instalar la pantalla en un TV LG» al menú Inicio. Desmarcada por defecto: usa unos 200 MB.

## 1.0.52 — 2026-10-30

- Ajustes → Opciones avanzadas: nueva casilla «Este PC reproduce en su propia pantalla (mini PC del televisor)». Desmarcada, la pantalla a pantalla completa de ese PC se cierra y la tarea programada deja de reabrirla cada 5 minutos, sin necesitar permisos de administrador. Al volver a marcarla reaparece en unos 5 minutos. Para que un PC la respete hay que instalar esta versión en él.

## 1.0.51 — 2026-10-30

- Editor de playlist: el selector de contenido tiene buscador, carpeta, etiquetas y tipo; se pueden marcar varios y añadirlos de golpe, se ve qué ya está en la playlist y se puede arrastrar un contenido al punto exacto.
- Editor de playlist: las filas son compactas (miniatura, nombre, duración, estrella y «⋯» con fechas, subir/bajar y quitar), hay una línea que marca dónde se suelta al arrastrar, un pie con «N elementos · M min S s por vuelta» (los vídeos cuentan como elemento, sin segundos) y los ajustes poco usados se pliegan en «Más ajustes».

## 1.0.50 — 2026-10-30

### Nuevo

- **Mandar archivos a pantallas desde la Librería.** Marca uno o varios archivos
  con la casilla de su miniatura (o abre su ficha) y pulsa «Mandar a pantallas»:
  eliges las pantallas, la duración por imagen y se añaden al final de su lista.
  Si una pantalla ya lo tenía, se salta. El panel dice cuántos sitios se añadieron.

- **Carpetas y etiquetas en la Librería.** Cada archivo puede estar en una carpeta y llevar
  varias etiquetas. Se ponen desde su ficha o, en bloque, con «Poner en carpeta…» y
  «Añadir etiqueta…» sobre los archivos marcados. La barra de la Librería filtra por
  carpeta («Sin carpeta» incluido) y por etiquetas, y el buscador también las encuentra.

- **Versión del APK visible en el panel.** La tarjeta de cada pantalla muestra «APK 1.0.49»
  junto al «Ahora»; si la caja lleva otra versión que el servidor, sale en ámbar
  («APK antiguo: 1.0.40 (servidor 1.0.49)»). Sin dato (navegador o APK anterior) no sale nada.

## 1.0.49 — 2026-10-30

### Mejorado

- **Librería más útil.** Buscador por nombre (sin fijarse en acentos), filtro por
  tipo (imágenes, vídeos, otros) y orden (más nuevos, nombre, tamaño, más usados).
- Cada archivo enseña su tamaño y tipo, una insignia «en uso» y, en los vídeos,
  la duración.
- **Ficha lateral** al pulsar un archivo: vista previa, resolución, duración,
  fecha de subida y dónde se usa (pantallas y paquetes).
- **Renombrar** desde la ficha: solo cambia el nombre que se ve.
- **Borrar con aviso:** si el archivo está en alguna pantalla o paquete, el panel
  lo dice con los nombres, y al confirmar lo quita también de ahí.

## 1.0.48 — 2026-10-30

### Mejorado

- **Subida de archivos más robusta.** Los archivos se envían directamente y por
  trozos, así que un vídeo grande ya no tumba el mini PC. Se ve una barra de
  progreso por archivo, se puede cancelar, y si algo falla el panel dice cuál y
  por qué (antes decía «subido» igualmente).
- El servidor comprueba que el archivo es de verdad una imagen o un vídeo y que
  cabe en el disco; el panel avisa antes de enviar lo que no vale o pasa del
  máximo. Nuevo ajuste «Subida de archivos» con el tamaño máximo por archivo
  (2048 MB por defecto).
- Los nombres de archivo con caracteres que Windows no admite se limpian solos.

### Arreglado

- **Borrar un archivo de la Librería ahora lo borra también del disco** en los
  PC con el programa instalado. Antes desaparecía de la lista pero seguía
  ocupando espacio.
- Las subidas a medias ya no dejan restos ni entran en las copias de seguridad.

### Limitación conocida

- La copia de seguridad «con multimedia» se arma en memoria y no se puede
  restaurar si pasa de 512 MB. La copia diaria automática no lleva vídeos, así
  que no le afecta.

---

## 1.0.47 — 2026-10-28

### Mejorado

- **Tarjetas de pantalla más limpias.** Los botones de uso diario (Playlist, Horario,
  Girar) siguen a la vista; Duplicar, Copiar enlace, Soltar TV y Eliminar están bajo
  «Más», ahora con su nombre escrito en vez de iconos sueltos.

---

## 1.0.46 — 2026-10-28

### Mejorado

- **Página de Pantallas más clara.** Las pantallas y sus contadores salen arriba;
  «Conectar una pantalla nueva» queda plegado (se abre solo si hay una pantalla
  esperando código). Antes ocupaba el primer pantallazo entero, sobre todo en el móvil.
- En cada tarjeta ya no se muestra la dirección cortada (el botón de copiar enlace
  sigue funcionando) y una pantalla sin nada pone «Sin contenido todavía».

---

## 1.0.45 — 2026-10-28

### Nuevo

- **«▶ Ahora: …» en cada pantalla.** En la tarjeta de cada pantalla del panel se
  ve qué contenido está mostrando en ese momento. Se actualiza solo cada pocos
  segundos y desaparece si la pantalla está apagada. El dato vive solo en memoria:
  no escribe nada en el disco.

---

## 1.0.44 — 2026-10-28

### Mejorado

- **El servidor ya no se traga la señal de cierre.** Varios `except:` desnudos
  atrapaban también `Ctrl+C` y el apagado del programa; ahora solo atrapan
  errores de verdad. No cambia nada de lo que se ve.
- **El manual cuenta lo nuevo:** el mini PC servidor y pantalla en uno, la copia
  diaria con carpeta externa, qué hacer con un archivo dañado y cómo se actualiza
  con el botón.

---

## 1.0.43 — 2026-10-28

### Corregido

- **El panel mostraba una versión vieja de sí mismo tras actualizar.** El
  navegador guardaba la página del panel en una caché y la servía primero, así
  que el botón «Actualizar ahora» (y cualquier novedad del panel) no aparecía
  hasta recargar varias veces. Ahora el panel y el login se piden siempre al
  servidor; la caché solo se usa para el reproductor, que sí tiene que funcionar
  sin red. La caché anterior se limpia sola.

---

## 1.0.42 — 2026-10-28

### Corregido

- **Un archivo de datos dañado ya no se convierte en «vacío».** Tras un corte de
  luz, `content.json` o `screens.json` podían quedar a medias, y el servidor
  los leía como vacíos: el siguiente guardado borraba todas las pantallas y
  playlists sin avisar. Ahora cada guardado se escribe a disco de verdad y deja
  una copia `.bak` de la versión anterior; si un archivo está dañado, se aparta
  con otro nombre (nunca se borra) y se recupera de esa copia.

---

## 1.0.41 — 2026-10-28

### Nuevo

- **Copia diaria también fuera del ordenador.** En Ajustes → Copia de seguridad
  se puede poner una carpeta externa (Google Drive, un pendrive, otro disco). La
  copia automática de cada día se copia también allí, en una subcarpeta con el
  nombre de la instalación, se comprueba y se conservan las últimas 14. Si la
  carpeta no está (pendrive sin enchufar) no se inventa: se espera y se copia
  cuando vuelva.

---

## 1.0.40 — 2026-10-28

### Mejorado

- **Las actualizaciones vienen configuradas de fábrica.** El panel consulta las
  versiones publicadas en GitHub sin tocar ningún ajuste (también en las tiendas
  que ya estaban instaladas). Solo se consulta cuando se abre el panel. Para
  apagarlo en una tienda: `"update_url": "off"` en `config.json`.

---

## 1.0.39 — 2026-10-28

### Nuevo

- **Botón «Actualizar ahora» en el panel.** Cuando hay una versión nueva
  publicada, el panel la anuncia y, al pulsar el botón, el servidor baja el
  instalador, comprueba su huella SHA-256 y lo ejecuta en silencio. Las
  pantallas siguen con su contenido mientras el servidor se reinicia. Nada se
  instala sin que alguien con sesión lo pida. Las versiones se publican con
  `tools\publicar-version.ps1` en GitHub Releases, y cada tienda apunta su
  `update_url` a `.../releases/latest/download/version.json`.
- **La pantalla del mini PC vuelve sola tras actualizar.** Una tarea programada
  la abre al iniciar sesión y cada 5 minutos si no está abierta.

---

## 1.0.38 — 2026-10-28

### Mejorado

- **La pantalla del mini PC se arregla sola.** Si el motor de la ventana se cae,
  o la app falla, se vuelve a abrir en unos segundos. Si la página no carga (el
  servidor aún arranca), reintenta cada 5 segundos en vez de dejar un error.
- **Pedir un PIN nuevo ya no se hace con un enlace.** Leer el PIN no lo cambia;
  regenerarlo es una petición aparte (`POST /api/pin/regenerate`) y exige sesión.

---

## 1.0.37 — 2026-10-28

### Nuevo

- **Copia de seguridad automática diaria.** Una al día (playlists, pantallas y
  ajustes, sin vídeos) en la carpeta `copias` junto a los datos. Se comprueba
  que el zip abre antes de darla por buena y se guardan las últimas 14. Se
  puede apagar con `copia_auto: false` en `config.json`.

### Mejorado

- **La contraseña del panel es más difícil de adivinar.** El hash usa 600.000
  iteraciones (antes 100.000). Las contraseñas actuales siguen valiendo y se
  actualizan solas la primera vez que entran. Las nuevas piden 8 caracteres.

---

## 1.0.36 — 2026-10-28

### Nuevo

- **Mini PC del televisor: el mismo equipo es servidor y pantalla.** El
  instalador tiene una casilla nueva, «Este equipo reproduce en su propia
  pantalla». Al marcarla, al iniciar sesión se abre el reproductor a pantalla
  completa (sin marco, sin cursor y sin atajos del navegador) y se desactiva la
  suspensión y el apagado de pantalla. Espera solo a que el servidor esté listo,
  también tras un corte de luz. Funciona con `InTeksDisplay.exe --pantalla`.
  Python ya iba dentro del instalador: no hay que instalar nada más.

---

## 1.0.35 — 2026-10-28

### Nuevo

- **El panel de administración es ahora una app de escritorio.** Una ventana
  propia, con su icono y su identidad en la barra de tareas: al anclarla se ancla
  «InTeks Display» y no Chrome. Los accesos directos del menú de inicio y del
  escritorio abren esta ventana; `abrir-panel.bat` queda como respaldo. Usa
  WebView2, que ya viene con Windows 10 y 11.

### Corregido

- **Un envío enorme sin sesión ya no tumba el servidor.** Antes se leía el
  cuerpo entero (hasta 512 MB) antes de mirar quién llamaba. Ahora la sesión se
  comprueba primero y las rutas públicas tienen un tope de 64 KB.
- **Una cabecera `Content-Length` negativa o no numérica** ya no deja un hilo
  colgado ni lanza una excepción: responde 400.
- **El login limita los intentos.** Tras 5 fallos desde una misma dirección se
  bloquea un minuto.
- **El PIN de emparejamiento y el código de pantalla** se generan con `secrets`
  en vez de `random`.
- **Una subida podía pisar a otra** si antes se había borrado algún archivo, y
  el nombre del archivo no se limpiaba. Ahora se usa el primer número libre y
  solo el nombre, sin carpetas.

---

## 1.0.34 — 2026-09-01

### Nuevo

- **La ayuda del panel explica con qué reproducir.** Una ficha por tipo de
  aparato —tablet o móvil, televisor con su propio navegador, caja Android TV,
  Amazon Fire TV Stick y mini PC— con cómo dejarlo montado y las pegas de cada
  uno. Del Fire TV Stick se dice claramente que **todavía no está probado**, para
  que nadie monte una tienda dándolo por hecho.
- **Y una lista de «si algo se ve mal»** con los fallos que ya han pasado en
  tienda y qué hacer en cada caso: bordes recortados, contenido que no llena la
  pantalla, el enlace que no carga en una caja Android, la pantalla que no
  responde al tacto, el «Buscando…» tras un corte de luz y el cortafuegos.

### Corregido

- **La ayuda de conectar pantallas explicaba un flujo que ya no existe.** Pedía
  ejecutar Python a mano y usar el puerto 8080, cuando hoy las pantallas se
  emparejan escribiendo un PIN. Quien la siguiera no conectaba nada.

---

## 1.0.33 — 2026-09-01

### Corregido

- **El contenido se veía mal en las cajas de TV con navegador antiguo.** No
  llenaba la pantalla, la letra salía diminuta y el tablero de divisas se
  desbordaba. Pasaba solo en algunas pantallas, lo que despistaba: el panel lo
  enseñaba bien porque el ordenador tiene un navegador moderno, y la caja de la
  tienda carga uno de 2017 que se saltaba en silencio medio centenar de reglas
  de estilo. Ahora se ve **igual en cualquier pantalla**.

### Nuevo

- **Margen de seguridad por pantalla** (de 0 a 5 %), en la ventana de playlist.
  Para televisores que recortan los bordes de la imagen y se comen lo que haya
  pegado al filo. **Por defecto está a 0**: solo hay que tocarlo en la pantalla
  que lo necesite.

---

## 1.0.32 — 2026-09-01

### Corregido

- **Tras un corte de luz, la caja de TV pedía la dirección del servidor en el
  escaparate.** Al volver la luz la caja arranca en unos dos minutos y el
  ordenador de la tienda tarda más. La app probaba la dirección que ya conocía
  durante **40 segundos**, la daba por mala, la **borraba**, y como todavía no
  había pintado nada ponía el formulario de «escribe la dirección» en la
  pantalla del escaparate. Ahora **no tira nunca la dirección que funcionaba**
  —solo la reemplaza cuando encuentra otra— y una caja ya instalada **se queda
  esperando el tiempo que haga falta**, con el aviso de «Buscando…», hasta que
  el ordenador aparece. El formulario solo sale al instalar una caja nueva.

### Cambiado

- **Se puede pedir el formulario de la dirección a propósito**: pulsando OK en
  el mando mientras la pantalla dice «Buscando…». Hacía falta porque, con lo
  anterior, una caja que se lleve a otra red ya no lo abre sola.

---

## 1.0.31 — 2026-08-13

### Corregido

- **Desenlazar una pantalla apagada no servía de nada.** El aviso se le mandaba
  al televisor en ese momento y, si estaba apagado o sin red, se perdía: al
  encenderlo volvía a creerse la misma pantalla, el nombre seguía ocupado y no
  se podía reutilizar. Ahora el desenlace **queda apuntado** y se le entrega al
  aparato en cuanto vuelve a encender, aunque pasen días.

---

## 1.0.30 — 2026-08-13

### Nuevo

- **Resolución 4K vertical (2160×3840) en la vista previa del tablero de
  divisas**, junto a las que ya había. Para pantallas 4K giradas.

---

## 1.0.29 — 2026-08-13

### Nuevo

- **El panel se usa desde el móvil.** Antes estaba pensado solo para el
  ordenador: la barra lateral se comía media pantalla y el editor de divisas
  no cabía. Ahora:
  - El menú se abre con un botón y se cierra solo al elegir sección.
  - **Actualizar tasas desde el móvil**: cada divisa muestra su país y su
    código, y un campo grande para la tasa. El resto de datos —bandera,
    moneda, ventanilla— se despliega con el botón del lápiz cuando hace falta.
  - Las ventanas de playlist se abren a pantalla completa.
  - Los campos son lo bastante grandes para que el móvil no haga zoom solo al
    tocarlos.
- **Botones para subir y bajar** contenidos de una playlist y divisas de un
  tablero. Arrastrar sigue funcionando con el ratón, pero con el dedo no era
  posible; y para mover una cosa **un** puesto, el botón es más rápido.

---

## 1.0.28 — 2026-08-13

### Corregido

- **La app de la caja de TV se rendía si el ordenador tardaba en arrancar.**
  Al volver la luz, la caja arranca en unos dos minutos y el ordenador de la
  tienda tarda más —primero Windows, luego el programa—. La app buscaba, no
  encontraba nada, y se quedaba con la pantalla de «escribe la dirección»
  puesta en el escaparate hasta que alguien fuera con el mando. Ahora **esa
  pantalla sigue buscando de fondo** y continúa sola en cuanto el ordenador
  aparece, sin perder el nombre de la pantalla.

---

## 1.0.27 — 2026-08-13

### Corregido

- **El nombre de la ventanilla se cortaba en el tablero de divisas.** Iba
  pegado a la moneda en la misma línea —«Peso filipino · RIA & Palawan»— y en
  cuanto la fila se estrechaba desaparecía justo el dato que distingue una
  ventanilla de otra: se leía «RIA & Pala…». Ahora va en su propia línea, con
  el ancho entero para él, y se ve entero.

### Cambiado

- **El aviso del pie del tablero se ve más grande.** El texto legal de las
  tasas era demasiado pequeño para leerlo desde el otro lado del mostrador.

---

## 1.0.26 — 2026-08-13

### Nuevo

- **App propia para las cajas Android de TV**, para no depender de Fully Kiosk
  Browser ni pagar sus 7 € por pantalla. Se instala en la caja y hace tres
  cosas que un navegador normal no hace:
  - **Encuentra el servidor sola.** Busca InTeks Display por la red y se
    conecta; no hay que escribir ninguna dirección con el mando. Si no lo
    encuentra, entonces sí la pide.
  - **Arranca al encender el televisor y enciende la pantalla**, así que tras
    un corte de luz el escaparate vuelve solo, sin que nadie toque nada.
  - **Se levanta sola si se cierra**, en menos de dos minutos.
  - A pantalla completa, sin barras de navegador: se gana el 12 % de pantalla
    que se comía la barra de direcciones.
  - Si el ordenador cambia de dirección en la red, la pantalla **la vuelve a
    buscar y sigue siendo la misma pantalla**, con su playlist y su horario.
    Con el enlace pegado a mano había que reconfigurarla una por una.

  - **Nadie saca el escaparate con el mando sin querer.** La tecla «atrás» no
    hace nada, y si alguien pulsa «inicio», el reproductor vuelve solo en unos
    segundos.
  - **Para poder tocar la caja** (cambiar el wifi, entrar en sus ajustes):
    pulsa **cinco veces seguidas «atrás»** y el reproductor te deja cinco
    minutos tranquilo. Pasado ese rato vuelve solo.

  Está probada en una caja Android de las más básicas del mercado (1 GB de RAM,
  Android 7.1). Se instala con un archivo `.apk`; de momento hace falta un
  ordenador para pasarlo.

---

## 1.0.25 — 2026-08-12

### Corregido

- **Hueco vacío entre la lista de divisas seleccionadas y "Servidor/Token"
  en el panel lateral de la extensión.** La lista tenía una altura fija de
  150px con scroll propio; ahora usa el espacio libre real del panel
  (`flex:1`), así que el botón de enviar y la configuración quedan pegados
  abajo en vez de flotar en medio de una zona vacía.

---

## 1.0.24 — 2026-08-12

### Cambiado

- **La extensión de Chrome ya no detecta divisas automáticamente en la
  página.** No se podía verificar que funcionara bien en todas las webs. En
  su lugar, el panel lateral trae un buscador de país/moneda —igual que en
  Divisas del panel de administración— para añadir con un clic, más un
  formulario para escribir un código a mano si no está en la lista.
  Consecuencia directa: el selector de varios agentes de pago (Ria y
  similares) desaparece de la extensión, porque solo tenía sentido cuando
  el escaneo traía varias filas de la misma moneda a la vez. El campo
  «agente/ventanilla» de una fila se sigue pudiendo escribir a mano desde el
  editor del admin, como siempre se pudo.
- La extensión ahora admite varios países con la misma moneda seleccionados
  a la vez (antes, elegir un segundo país en dólares después de uno ya
  puesto no hacía nada).

---

## 1.0.23 — 2026-08-12

### Nuevo

- **La sección Ayuda del panel explica cómo conectar la extensión de Chrome
  desde otro ordenador.** No hacía falta buscarlo en el manual: el panel
  mismo dice qué poner en "Servidor" (misma red vs. acceso remoto) y dónde
  copiar el token, con la misma información que ya usa la extensión al
  fallar con un 401.

---

## 1.0.22 — 2026-08-12

### Corregido

- **Una pantalla que seguía funcionando podía quedar marcada "offline" en el
  panel para siempre.** Caso real: una pantalla servía contenido con
  normalidad -el bot de `/estado` la veía conectada- pero el panel la
  mostraba caída. Era una carrera entre hilos: si el televisor se
  reconectaba solo (típico tras un corte de wifi) justo antes de que el
  servidor notara que la conexión vieja había muerto, la limpieza de esa
  conexión vieja pisaba el estado "conectada" que acababa de poner la nueva.
  No se corregía sola: quedaba mostrando "offline" indefinidamente aunque la
  pantalla siguiera respondiendo. Ahora el servidor comprueba si ya hay una
  reconexión viva antes de marcar la pantalla como caída.

---

## 1.0.21 — 2026-08-12

### Corregido

- **La casilla «Iniciar con Windows» ahora hace lo que dice.** Antes se
  guardaba en `config.json` y no la leía nadie: desmarcarla no apagaba nada,
  y marcarla no encendía nada — el arranque real dependía solo de si el
  instalador había registrado la tarea programada. Ahora el panel consulta y
  cambia esa tarea de verdad al guardar Ajustes. Si falla (hace falta ser
  administrador para tocar el Programador de tareas de Windows), el panel lo
  avisa en vez de fingir que se aplicó.

---

## 1.0.20 — 2026-08-12

### Nuevo

- **Prioridad en el orden aleatorio.** Se puede marcar con ⭐ un contenido de
  la playlist (por ejemplo, el tablero de divisas) para que salga con una
  cadencia fija — "cada 4 pases", configurable — en vez de quedar sujeto al
  azar como el resto. El resto de la playlist se sigue barajando y sin
  repetirse dentro de la misma vuelta; solo lo marcado ⭐ puede volver a
  salir dentro de la misma vuelta, si hace falta para cumplir su cadencia.
  Solo tiene efecto con "Orden aleatorio" activado — con orden fijo ya se
  controla la posición arrastrando.

---

## 1.0.19 — 2026-08-12

### Nuevo

- **El bot de Telegram ahora contesta.** Hasta ahora solo empujaba avisos
  (pantalla caída, tasas viejas); ahora responde `/estado` con una pasada de
  todas las pantallas (en línea o desde cuándo caídas) y todos los tableros de
  divisas (al día o cuánto llevan vencidos), más disco y versión. Es de solo
  lectura — no reinicia nada ni da el PIN de emparejamiento. Responde solo al
  `telegram_chat_id` configurado; a cualquier otro chat, silencio total. No
  hace falta configurar nada nuevo: usa el mismo token que ya usan los avisos.

---

## 1.0.18 — 2026-08-12

### Corregido

- **Las pantallas se enteran de que has actualizado.** Hasta ahora, instalar
  una versión nueva cambiaba el programa pero **no lo que estaba mostrando el
  televisor**: la página llevaba horas abierta y seguía funcionando con el
  código viejo. El arreglo tardaba hasta cuatro horas en verse —lo que tarda la
  recarga de seguridad— o no se veía nunca si nadie reiniciaba el aparato.
  Ahora, cuando el servidor cambia de versión, cada pantalla se recarga sola en
  menos de un minuto.

  Es la razón de que la 1.0.17 pareciera no haber arreglado nada: el servidor
  ya estaba actualizado y el televisor seguía pintando lo de antes.

---

## 1.0.17 — 2026-08-11

### Nuevo

- **El tablero de divisas dice también a qué hora se actualizaron las tasas**,
  no solo el día: `11/08/2026 22:28`. Un tablero se actualiza varias veces al
  día y unas tasas de las 9:00 y otras de las 19:00 se veían idénticas.

### Corregido

- **El título del tablero salía cortado** («TIPOS DE…»). El logo se estaba
  dibujando mucho más grande de lo previsto y se comía el ancho del título.
  Ahora el logo tiene el tamaño que debía y el título cabe entero.
- **Las imágenes de los módulos salían deformadas por la misma causa**: la
  ficha de producto y la comparativa las estiraban a pantalla completa en vez
  de respetar su hueco.
- En pantallas muy estrechas —verticales—, si aun así el título no cabe en una
  línea, **pasa a ocupar su propia fila** y el logo y la fecha van debajo, en
  vez de recortarse.

---

## 1.0.16 — 2026-08-11

### Por dentro

- **Playlists largas dejan de comerse la memoria del reproductor.** Hasta ahora
  la pantalla cargaba de golpe las imágenes y los vídeos de **todos** los
  contenidos, aunque tardaran media hora en salir. Con cuatro o cinco no se
  nota; con cincuenta, un aparato pequeño —una caja Android de 1 o 2 GB— se
  queda sin memoria y el sistema cierra la aplicación: pantalla en negro sin
  ningún aviso.
- Ahora solo se mantienen cargados el contenido actual, el anterior y los dos
  siguientes. El resto se suelta y se vuelve a cargar cuando le toca, con
  margen suficiente para que **no haya parpadeo** al cambiar. Los vídeos, que
  eran lo más pesado, ya no se descargan todos a la vez.
- Efecto práctico: una playlist de 50 contenidos ocupa en la pantalla más o
  menos lo mismo que una de 5.

---

## 1.0.15 — 2026-08-11

### Corregido

- **La pantalla se quedaba repitiendo siempre el mismo contenido.** Con una
  playlist de varios elementos, al cabo de la primera vuelta la pantalla se
  atascaba en el segundo y los demás no volvían a salir. Se veía sobre todo
  con pases de unos diez segundos: el reproductor pregunta al servidor por
  novedades cada quince, y cada una de esas consultas devolvía el turno al
  principio de la lista aunque no hubiera cambiado nada. Está en todas las
  versiones desde que existe el orden aleatorio (1.0.5).
- Como efecto de lo anterior, un tablero de divisas podía parecer que **duraba
  mucho más de los segundos configurados**: en realidad volvía a empezar una y
  otra vez.

### Nota

- Cuando un tablero tiene más divisas de las que caben en la pantalla, se
  reparte en páginas y **cada página dura lo que hayas puesto en el contenido**.
  Un tablero de dos páginas a 10 segundos ocupa 20. Es a propósito, para que dé
  tiempo a leer, pero conviene saberlo al cuadrar los tiempos.

---

## 1.0.14 — 2026-08-11

### Corregido

- **La regla del cortafuegos se crea aunque no marques el arranque
  automático.** En la 1.0.13 iba dentro del mismo paso que registra el
  arranque con Windows, así que quien desmarcara esa casilla se quedaba sin
  regla y sin saberlo: el panel funcionaba y las pantallas no entraban. Son
  dos cosas distintas y ahora van por separado.

---

## 1.0.13 — 2026-08-11

### Corregido

- **El instalador abre solo el puerto en el cortafuegos de Windows.** Hasta
  ahora había que hacerlo a mano, y sin ese paso pasaba lo peor que puede
  pasar: el panel funcionaba perfectamente en el propio ordenador y **ningún
  televisor ni tablet llegaba al servidor**, quedándose cargando para siempre
  sin dar ni un error. Instalado en una tienda, eso son horas buscando el
  fallo donde no está.
- **La instrucción que había en el manual para hacerlo a mano no servía en la
  mayoría de las redes.** Creaba la regla solo para «redes privadas», y
  Windows marca como pública cualquier wifi que nadie haya cambiado a mano: se
  seguía el manual al pie de la letra y el televisor seguía sin entrar. Ahora
  la regla vale para cualquier red, y también aguanta que Windows reclasifique
  la wifi más adelante.

---

## 1.0.12 — 2026-08-11

### Corregido

- **Los datos se guardaban dentro de la carpeta del programa.** Deberían haber
  ido siempre a `C:\ProgramData\InTeks Display\`, y así lo dice el manual, pero
  acababan en `C:\Program Files\InTeks Display\` junto al propio programa. Al
  actualizar se arreglan solos: la primera vez que arranca la versión nueva se
  traen las pantallas, el contenido, los archivos subidos, la contraseña y la
  configuración —incluido el token de avisos— a su sitio. No hay que hacer
  nada, y la copia vieja se queda donde estaba por si acaso.
- **`restablecer-contrasena.bat` no encontraba la instalación.** Buscaba en
  `ProgramData`, que es donde se supone que están los datos; como en realidad
  estaban en la carpeta del programa, decía que no había ninguna instalación y
  no había forma de recuperar el acceso al panel. Con los datos en su sitio,
  vuelve a funcionar.

---

## 1.0.11 — 2026-08-11

### Nuevo

- **La ventanilla del agente de pago (Ria y similares) ya se ve en la
  pantalla.** Cuando una moneda se cobra por varios agentes (Davivienda,
  4-72...), la extensión de Chrome ya elegía uno para calcular la tasa, pero
  esa elección se quedaba solo en el ordenador que la mandaba. Ahora aparece
  también en el cartel, bajo el país, para que el cliente sepa a qué
  ventanilla dirigirse. El campo también se puede escribir a mano en el
  admin, para tableros hechos pegando texto o leyendo una imagen.

### Corregido

- **Crear una pantalla, asignarle una playlist o configurar un videowall
  desde dos paneles todavía se pisaba.** El arreglo de la 1.0.10 cubrió el
  guardado general y las tasas de cambio, pero se dejó fuera esta otra vía:
  no avisaba a otros paneles abiertos ni comprobaba si alguien había
  guardado algo mientras tanto, así que un panel con datos viejos podía
  borrar en silencio lo que acababa de configurar otro equipo. Ahora se
  comporta igual que el resto: avisa y rechaza el guardado caducado en vez
  de sobrescribir a ciegas.

---

## 1.0.10 — 2026-08-10

### Corregido

- **Dos ordenadores usando el panel ya no se pisan.** Si actualizabas las tasas
  con la extensión desde un PC y en otro tenías el panel abierto, ese panel no
  se enteraba: al tocar cualquier cosa subía su copia vieja y **las tasas recién
  puestas desaparecían sin aviso ni error**. Ahora el panel recibe el aviso y se
  refresca solo.

- **Se perdían cambios al guardar dos cosas a la vez.** El servidor leía el
  archivo, lo modificaba y lo volvía a escribir, y en el hueco entre leer y
  escribir cabía otra petición. Medido con veinte subidas simultáneas:
  **sobrevivían seis**. Afectaba a subir archivos, borrarlos, actualizar tasas y
  enlazar pantallas. Ahora ninguna escritura puede colarse en medio de otra.

### Por dentro

- `content.json` lleva un número de revisión que sube en cada escritura. Si el
  panel intenta guardar con una foto que ya no es la actual, el servidor lo
  rechaza y el panel avisa —«otro equipo cambió algo, repite lo último que
  hiciste»— en vez de destruir en silencio el trabajo del otro equipo. Se pierde
  la última acción propia, que es el mal menor.
- Las instalaciones que vienen de una versión anterior se migran solas al
  arrancar.
- Restaurar una copia deja el contador por encima del que traía, para que ningún
  panel abierto de antes pueda escribir encima de lo recién restaurado.

---

## 1.0.9 — 2026-08-10

### Nuevo

- **La extensión de Chrome elige el agente de pago de Ria.** Cuando una
  moneda trae varios agentes (Bancolombia, Davivienda, 4-72...), el panel
  lateral ofrece un desplegable con todos y su tasa: se elige el preferido
  con un clic, sin escribirlo a mano. Se guarda solo y avisa cuando otro
  agente paga notablemente más, sin cambiar la elección.

### Corregido

- La extensión **confundía dígitos del nombre de un agente con la tasa** (p.
  ej. "4-72 Servici" en Ria publicaba "4" en vez de la tasa real).

---

## 1.0.8 — 2026-08-10

### Corregido

- **Fuga de conexión en el reproductor**: cada corte de la conexión en tiempo
  real (SSE) abría una conexión nueva sin cerrar la anterior. En el WiFi de
  un televisor, mucho menos estable que el de un PC, esto podía acumular
  conexiones abiertas con las horas.

### Por dentro

- El reproductor se recarga solo cada 4 horas como medida de seguridad,
  pensada para navegadores de TV con poca memoria (el de LG webOS es un caso
  documentado por el propio soporte de LG). Es seguro: si el servidor
  estuviera caído justo en ese instante, la pantalla recupera lo último
  reproducido igual que al encenderla, no se queda en negro.

---

## 1.0.7 — 2026-08-10

### Nuevo

- **La extensión de Chrome elige el agente de pago correcto en Ria.** Cuando
  una moneda trae varios agentes (Bancolombia, Davivienda, 4-72...), antes se
  quedaba con el primero que encontraba en la página. Ahora se configura una
  lista de preferencia por moneda desde el panel lateral de la extensión
  («Agente preferido»), y si otro agente paga notablemente más sin estar en
  la lista, avisa sin cambiar la elección.

### Corregido

- La extensión **confundía dígitos del nombre de un agente con la tasa**: en
  Ria, "4-72 Servici" hacía que se publicara "4" en vez de la tasa real. Pasa
  con cualquier página cuyo nombre de agente lleve números.

---

## 1.0.6 — 2026-08-09

### Nuevo

- **El aviso de tasas viejas ahora es un recordatorio**, no una notificación
  suelta. Se configura desde qué hora, hasta qué hora y cada cuánto insistir
  (por defecto: de 9:00 a 22:00, cada hora). Con «repetir cada 0 horas» se
  queda en un único aviso al día.
- Pasada la hora de fin **se calla**, aunque las tasas sigan viejas.

### Corregido

- Un reinicio del servidor de madrugada podía disparar el aviso de tasas en ese
  momento: el estado vivía en memoria. Ahora se guarda en disco.

---

## 1.0.5 — 2026-08-09

### Nuevo

- **Orden aleatorio** por pantalla, en Playlist junto a la transición. Cada
  vuelta se baraja de nuevo, y nunca repite el último de la vuelta anterior.

### Corregido

- **Los accesos directos no tenían icono.** Apuntan a un `.bat`, y sin indicar
  el icono Windows ponía el genérico de archivo por lotes. Ahora usan
  `assets\icon.ico`, también en «Programas instalados».

---

## 1.0.4 — 2026-08-09

### Corregido

- La insignia **«auto»** de los vídeos salía recortada: usaba el ancho fijo de
  46 px pensado para un número de tres cifras.
- El nombre del contenido podía aplastarse hasta desaparecer cuando la columna
  de la playlist iba estrecha. Ahora los controles bajan de línea antes que
  comerse el nombre.

---

## 1.0.3 — 2026-08-09

### Corregido

- **Los archivos con espacios o acentos en el nombre daban 404.** Un vídeo
  llamado «Tarifas sujetas a cambios…» no se reproducía y su miniatura salía
  negra, sin ningún mensaje. El servidor no deshacía el codificado de la URL,
  así que buscaba en disco un archivo con `%20` en el nombre. Las imágenes
  funcionaban de casualidad, por llamarse `0000_1.png`.
- La fila de la playlist se descuadraba con los campos de fecha: aplastaban el
  nombre del contenido hasta hacerlo desaparecer. Ahora van en su propia línea
  y con etiquetas.

---

## 1.0.2 — 2026-08-09

### Nuevo

- **Avisos al móvil por Telegram**: pantalla caída dentro de su horario,
  pantalla que vuelve, y tablero de divisas sin actualizar. Se configura en
  Ajustes y hay un botón para mandarse un mensaje de prueba. Cada aviso se
  manda una sola vez.
- **Vigencia por fechas**: cada contenido de una playlist puede tener fecha de
  inicio y de fin, y entra y sale solo. Si todo caduca, se sigue mostrando lo
  último antes que dejar el escaparate en negro.
- **Duplicar una pantalla** con toda su configuración, para montar la segunda
  caja sin rehacer nada.
- **Aviso de disco casi lleno** en Ajustes.

### Corregido

- Guardar los ajustes **borraba el resto de `config.json`**: el nombre mDNS, la
  dirección de actualizaciones y, a partir de ahora, el token de avisos. Y
  enviar algo que no fuera un objeto escribía basura en el archivo y se llevaba
  la configuración entera.

---

## 1.0.1 — 2026-08-09

Primera versión con el intérprete de Python incluido. **El equipo de destino ya
no necesita tener Python instalado.**

### Nuevo

- **Copia de seguridad y restauración** (Ajustes). Se lleva pantallas,
  playlists, paquetes y archivos subidos. No incluye la contraseña ni el token
  de la extensión, así que el archivo se puede guardar en un pendrive sin riesgo.
- **Transiciones entre pases**: fundido, deslizar, zoom o corte seco, una por
  pantalla, con duración ajustable. En Playlist de cada pantalla.
- **Modo festivos**: fechas concretas que mandan sobre el horario del día de la
  semana, para cerrar en Navidad o abrir un domingo de rebajas.
- **Recuperar la contraseña** del panel con `restablecer-contrasena.bat`, desde
  el propio ordenador. No hay recuperación por la red a propósito.
- **Las pantallas guardan sus imágenes y vídeos** en el propio televisor, así
  que un arranque con el servidor apagado ya no deja el escaparate vacío.
- **Desenlazar una pantalla** desde el panel, y **copiar su enlace directo**.
- La **versión instalada** se ve en Ajustes.

### Corregido

- El tablero de divisas mostraba **la fecha de hoy** aunque las tasas fueran de
  hace tres días. Ahora muestra la fecha de las tasas y avisa cuando caducan.
- Al **editar un paquete**, las pantallas que lo usaban no se enteraban. Ahora
  se actualizan solas.
- Una pantalla que se apagaba y encendía podía **perder su enlace** sin forma de
  devolvérselo. Ahora se reenlaza desde el panel conservando su configuración.
- El **panel aparecía en su propia lista** como una pantalla llamada «admin».
- Un día del horario con «abierto» y sin horas dejaba la pantalla **apagada las
  24 horas**.
- El **instalador se pisaba a sí mismo** al actualizar: copiaba archivos con el
  servidor todavía en marcha.
- `server.log` crecía sin límite.
- El cuerpo de las peticiones se leía entero en memoria sin ningún techo.

### Por dentro

- Se abandona la vía Electron: fuera el build de 354 MB, las fuentes y las
  dependencias de npm. El proyecto ya no tiene ninguna.
- 152 pruebas de lógica y 8 suites de servidor.

---

## 1.0.0

Primera versión: pantallas, playlists, paquetes, módulo de divisas con la
extensión de Chrome, horarios, videowall y emparejamiento por código.
