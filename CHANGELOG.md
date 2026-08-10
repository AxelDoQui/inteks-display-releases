# Cambios de InTeks Display

Qué cambió en cada versión, en cristiano. Sirve para dos cosas: saber qué tiene
instalada cada tienda cuando algo falla, y tener el texto listo si algún día se
enciende el aviso de versión nueva (`update_url` en `config.json`).

Para subir de versión: `powershell -File tools\subir-version.ps1 1.0.2`

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
