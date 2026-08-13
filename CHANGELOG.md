# Cambios de InTeks Display

Qué cambió en cada versión, en cristiano. Sirve para dos cosas: saber qué tiene
instalada cada tienda cuando algo falla, y tener el texto listo si algún día se
enciende el aviso de versión nueva (`update_url` en `config.json`).

Para subir de versión: `powershell -File tools\subir-version.ps1 1.0.2`

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
