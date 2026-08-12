# InTeks Display — manual de uso

Para el día a día en una tienda. Para instalar por primera vez, ver
[README_INSTALLER.md](README_INSTALLER.md).

---

## Lo básico

**Abrir el panel:** el acceso directo «InTeks Display» del escritorio. Se abre
en su propia ventana, sin barra de direcciones.

**El servidor arranca solo** al encender el equipo, como tarea programada y sin
ventana, para que nadie pueda cerrarlo por error. No hace falta iniciar sesión
en Windows.

Se enciende y se apaga con la casilla **«Iniciar con Windows»** de Ajustes. Al
guardar, el panel toca la tarea programada de verdad, así que lo que ves en la
casilla es lo que va a pasar cuando enciendas el equipo. Como Windows exige
permisos de administrador para eso, **puede fallar al guardar**: si pasa, el
panel te lo dice claramente. No es un aviso decorativo — significa que el
cambio no se aplicó y el arranque sigue como estaba.

**Si algo va mal**, el registro está en
`C:\ProgramData\InTeks Display\server.log`. Que ese archivo exista es la señal
de que la instalación fue bien.

---

## Enlazar un televisor

1. En el televisor, abre `http://signage.local` (o `http://LA-IP-DEL-PC`).
2. La pantalla muestra un **código de cuatro cifras**.
3. En el panel → **Pantallas** → «Esperando para enlazar», escribe el nombre y
   pulsa **Enlazar**.

El nombre se pone desde el ordenador a propósito: teclear con el mando de un
televisor es lento y se equivoca uno.

**Si el televisor ya estaba enlazado** y abres esa misma dirección, te avisa
(«Ya enlazada como…») y vuelve solo a su contenido en seis segundos. Cualquier
tecla del mando para la cuenta atrás si querías reenlazarlo.

**Si perdió su identidad** (algunos televisores borran su memoria al apagarse),
enseñará un código otra vez. En el panel, en lugar de escribir un nombre nuevo,
usa el desplegable **«reenlazar a: …»** y elige la pantalla que era: recupera su
playlist, su horario y su rotación tal cual.

**Para reenlazar a propósito** sin ir al televisor: botón **Desenlazar** en la
tarjeta de la pantalla. No borra nada, solo suelta el aparato.

**Televisores que borran todo al apagarse:** usa el botón de **copiar enlace
directo** y pega esa dirección como página de inicio del televisor. Así la
identidad viaja en la URL y ningún borrado la alcanza.

---

## Con qué reproducir: el televisor o una cajita

Cualquier televisor con navegador vale para empezar, y para una pantalla que se
apaga por la noche suele ir bien. Pero **el navegador de fábrica de un Smart TV
no está pensado para tener una página abierta doce horas seguidas**, y cuando
falla no avisa: cierra la página y deja el escaparate en negro.

Pasó de verdad, en una tienda, con un LG: el navegador se cerraba solo cada dos
minutos. No era el protector de pantalla, ni el ahorro de energía, ni el
HDMI-CEC, ni InTeks Display — se probó con la versión corregida y siguió igual.
Se resolvió **cambiando el aparato, no la página**.

**La recomendación, si la pantalla tiene que estar encendida todo el día:** una
caja Android barata (o un Fire TV Stick, o un mini PC) enchufada al HDMI del
televisor, con la app **Fully Kiosk Browser** (~7 €, pago único). El televisor
pasa a ser solo la pantalla. Es lo que está funcionando hoy en la tienda del
caso de arriba.

### Cómo se deja montada

1. Enlaza la caja como una pantalla normal (ver arriba) y, en su tarjeta del
   panel, pulsa **copiar enlace directo**.
2. Instala Fully Kiosk en la caja y pega ese enlace en **Start URL**. Va con el
   nombre de la pantalla dentro, así que la identidad viaja en la dirección y
   no se pierde aunque la caja se reinicie o se borre su memoria.
3. Activa, en los ajustes de Fully Kiosk:
   - **Keep Screen On** — la pantalla no se apaga sola.
   - **Start on Boot** — al volver la luz, arranca sin que nadie toque nada.
   - **Kiosk Mode** — nadie sale de la aplicación con el mando por error.
   - Y **desactiva el salvapantallas** de la propia app (*Screensaver*), que
     viene puesto y taparía el contenido.

Los nombres son los de la app en inglés y pueden cambiar un poco de una versión
a otra.

**No hace falta configurar nada más.** El reproductor ya se ocupa solo del
resto: se reconecta cuando vuelve la red, guarda las imágenes y los vídeos en
el propio aparato para sobrevivir a un arranque con el servidor apagado, y se
refresca cada cuatro horas por seguridad.

---

## Contenido

### Librería y playlists

Sube imágenes y vídeos a la **Librería**, y arrástralos a la **Playlist** de
cada pantalla. Cada elemento tiene su duración; los vídeos usan la suya propia.

### Paquetes

Un paquete es un grupo de contenidos que se añade de una vez. **Es un grupo
vivo**: si lo editas, todas las pantallas que lo usan cambian al momento, sin
tocarlas. En la playlist aparece como un bloque con borde naranja.

Al borrar un paquete que está en uso, sus contenidos se quedan sueltos en esas
playlists: no se pierde nada, pero dejan de actualizarse juntos.

### Fechas de vigencia

Cada contenido puede tener fecha de inicio y de fin (**se ve del … al …**).
Vacío = sin límite. Una promo entra y sale sola.

Si **todo** el contenido de una pantalla ha caducado, se sigue mostrando lo que
hay y la tarjeta lo avisa. Una promo vieja en el escaparate es malo; un
escaparate apagado es peor y no se distingue de una avería.

### Transiciones y orden

En la **Playlist** de cada pantalla, arriba:

- **Transición**: fundido, deslizar, zoom o corte seco, con su duración.
- **Orden aleatorio**: baraja cada vuelta y nunca repite el último de la
  vuelta anterior.

Un tipo por pantalla, para todos sus pases.

### Que algo salga a menudo: la estrella ⭐

Con el orden aleatorio, un contenido importante puede tener mala suerte y no
salir en un buen rato. Para eso está la **⭐** de cada elemento de la playlist:
lo marcado sale **con una cadencia fija** —cada 4 pases por defecto,
ajustable— en vez de quedar al azar. Lo típico es el tablero de divisas, que
interesa que se vea a menudo aunque haya veinte promociones más.

El resto de la playlist se sigue barajando y sin repetirse dentro de la misma
vuelta. Solo lo marcado con ⭐ puede volver a salir dentro de la misma vuelta,
que es justo lo que hace falta para cumplir su cadencia. Si marcas varios, se
turnan en vez de amontonarse seguidos.

**Solo hace algo con «Orden aleatorio» activado.** Con el orden fijo la
posición ya la decides tú arrastrando.

---

## Tipos de cambio

El módulo de divisas se edita en la sección **Divisas**. Puedes elegir país y
moneda de un buscador, fijar el orden arrastrando, poner logo, colores y un
mensaje al pie.

### La fecha del tablero es la de las tasas

El tablero muestra **cuándo se actualizaron las tasas**, no la fecha de hoy.
Pasado el plazo (24 h por defecto, ajustable, 0 lo desactiva) esa fecha
**parpadea despacio**: lo ve el personal al pasar sin montar un cartel delante
del cliente. En el panel se lee más claro: «actualizado hace 3 días ⚠».

### La extensión de Chrome

Manda tasas a InTeks Display sin teclear el tablero entero cada vez.
Se instala una vez por equipo (menú Inicio → «Instalar extensión de divisas»)
y necesita el **token de la API**, que está en Ajustes.

**Busca el país o la moneda y añádela con un clic**, igual que en el
buscador del panel de administración (sección Divisas). Si un código no está
en la lista, «¿No está en la lista? Añadir código a mano» deja escribirlo
directamente. Elegida una divisa, solo falta escribir la tasa.

**Desde otro ordenador**, se configura igual: campo Servidor + token, ver
*Usar el panel desde otro ordenador* más abajo.

---

## Usar el panel desde otro ordenador

El panel no es un programa instalado: es una página que sirve el equipo donde
corre InTeks Display. Desde cualquier otro ordenador de la misma red se abre en

    http://signage.local/admin.html

con la misma contraseña. Los dos paneles se refrescan solos, así que lo que
hagas en uno aparece en el otro sin recargar nada.

Para la extensión de Chrome en ese segundo equipo, rellena el campo **Servidor**
del panel lateral con esa misma dirección (`http://signage.local`) y pega el
token de la API que está en Ajustes.

**Si el otro ordenador no lo encuentra**, casi siempre es el cortafuegos de
Windows del equipo servidor (ver *Cuando algo falla*, más abajo). Si
`signage.local` tampoco responde, prueba con la IP del equipo servidor. En
**Android** —móviles, tablets y cajas de TV— hay que usar **siempre la IP**: su
navegador no resuelve los nombres acabados en `.local`. Los iPhone y los Mac sí
los entienden, y de ahí la confusión: el mismo enlace funciona en un aparato y
en otro no.

**Qué pasa si dos personas tocan el panel a la vez.** Manda quien guarde
primero. El segundo recibe el aviso «otro equipo cambió algo, repite lo último
que hiciste» y su panel se pone al día solo. Se pierde esa última acción suya
—hay que repetirla— pero nunca se borra en silencio lo que hizo el otro, que es
lo que pasaba antes.

---

## Horarios

En **Horario** de cada pantalla: días de la semana con su franja, o modo 24/7.

**Festivos:** fechas concretas que mandan sobre el día de la semana. Sirven
igual para cerrar en Navidad que para abrir un domingo de rebajas. Deja las
horas vacías para todo el día.

Si configuras **solo festivos** y ningún día, el resto del año la pantalla sigue
encendida.

---

## Avisos al móvil (Telegram)

Avisa cuando una pantalla se cae dentro de su horario, cuando vuelve, y cuando
un tablero de divisas lleva demasiado sin actualizarse.

**Configurarlo:**

1. En Telegram, habla con **@BotFather** → `/newbot` → copia el token.
2. Habla con **@userinfobot** → copia tu `Id`.
3. **Escríbele algo a tu bot.** Telegram no deja que un bot inicie la
   conversación; sin este paso falla con «chat not found».
4. Ajustes → pega los dos → **Guardar avisos** → **Enviar mensaje de prueba**.

**Pantalla caída:** un aviso al caer y otro al volver. Solo dentro del horario
de esa pantalla, para que no suene de madrugada.

**Tasas viejas:** es un recordatorio, no un aviso suelto. Se configura desde qué
hora, hasta qué hora y cada cuánto insistir (9:00 a 22:00 cada hora, por
defecto). Pasada la hora de fin se calla aunque sigan viejas. Con «repetir cada
0 horas» queda un único aviso al día.

### Preguntarle al bot cómo va todo: `/estado`

Los avisos llegan cuando algo pasa. Si lo que quieres es mirar tú —desde casa,
un domingo, sin encender el ordenador de la tienda— escríbele **`/estado`** al
bot y contesta al momento con:

- **Cada pantalla**, en línea o desde cuándo lleva caída.
- **Cada tablero de divisas**, cuánto hace que se actualizó, y marcado si ya
  está vencido.
- **Versión instalada y espacio en disco**, al pie.

No hay nada que configurar: usa el mismo token de los avisos. Si ya recibes
avisos, `/estado` funciona.

**Solo contesta a tu chat.** A cualquier otra persona que le escriba no le
responde nada — ni siquiera un error, para no confirmarle a un desconocido que
el bot existe. Y **solo sabe mirar**: no reinicia el programa ni da el código
de emparejamiento. Es una ventana, no una llave, y así puedes usarlo desde el
móvil sin preocuparte.

> El token se guarda en `config.json`, que **sí** entra en la copia de
> seguridad. Trátala como una contraseña.

---

## Copia de seguridad

En **Ajustes → Copia de seguridad**.

| | Qué lleva |
|---|---|
| **Copia completa** | Configuración + todas las imágenes y vídeos |
| **Solo configuración** | Los cuatro JSON. Cabe en un correo, pero **sin logos ni imágenes** |

**Qué viaja:** pantallas y playlists, librería, paquetes, módulos de divisas con
sus tasas y su sello de fecha, horarios y festivos, rotación, transición, orden
aleatorio, fechas de vigencia, puerto, nombre de instalación y el token de
Telegram.

**Qué NO viaja:** la contraseña del panel, el token de la extensión, el secreto
de sesión y el PIN. Es a propósito: un archivo que va por correo o en un
pendrive no puede llevar dentro la llave de casa.

### Montar otra tienda a partir de una copia

1. Instala en el equipo nuevo y **crea la contraseña**.
2. Restaura la copia (**completa**, o los logos faltarán).
3. **Cambia el «Nombre de instalación»** en Ajustes. Si no, las dos tiendas
   avisarán al mismo chat de Telegram firmando igual y no sabrás cuál es cuál.
4. Borra las pantallas que vengan de la otra tienda y no existan aquí.
5. Empareja los televisores. Si les pones los mismos nombres, heredan playlist
   y horario tal cual.
6. Reconfigura la extensión de Chrome con el token del equipo nuevo.
7. **Actualiza las tasas.** La copia trae las de la otra tienda con su fecha
   original, y el tablero las marcará como viejas desde el primer minuto.

---

## Cuando algo falla

**Olvidaste la contraseña del panel.** En la carpeta del programa (*Archivos de
programa → InTeks Display*), ejecuta **`restablecer-contrasena.bat`**. Borra
solo la contraseña; el token de la extensión no se toca. Vuelve al panel y crea
una nueva **en ese momento**: mientras no haya contraseña, cualquiera que llegue
al servidor desde la red puede crear una.

No hay recuperación por la red a propósito: eso no sería recuperación, sería una
puerta trasera para cualquiera conectado al wifi de la tienda.

**Una pantalla no muestra nada.** Mira si aparece «en línea» en el panel. Si no,
comprueba que el televisor tiene red y que el servidor responde
(`http://LA-IP/admin.html` desde otro equipo).

**El televisor se queda cargando sin llegar a nada, al escribir la IP.** Es el
Firewall de Windows, que por defecto bloquea las conexiones que llegan de otros
aparatos aunque el PC vea el servidor perfectamente por sí mismo. Y no da
error: se queda cargando y ya, porque un paquete bloqueado no contesta nada.

Desde la versión 1.0.14 **el instalador crea la regla solo**. Si vienes de una
instalación anterior, en el PC, PowerShell **como administrador**:
```powershell
New-NetFirewallRule -DisplayName "InTeks Display (HTTP)" -Direction Inbound -Protocol TCP -LocalPort 80,9000 -Action Allow -Profile Any
```
Abre solo ese puerto, no toca el resto del firewall, y surte efecto al momento:
no hay que reiniciar nada.

> `-Profile Any` es importante. Windows clasifica como **red pública**
> cualquier wifi que no se marque a mano como privada, y una regla «para redes
> privadas» **no se aplica en una red pública**: parece que has hecho lo
> correcto y el televisor sigue sin entrar.

**El navegador de un Smart TV se cierra solo pasado un rato.** Algunos
televisores (el navegador integrado de LG webOS es un caso conocido, según su
propio soporte) cierran páginas que llevan mucho abiertas por límites de
memoria del propio televisor, no por InTeks Display. Revisa primero que el
protector de pantalla y el ahorro de energía estén apagados en el TV.

Si sigue pasando, **no pierdas tiempo peleándote con el televisor**: en el caso
real que tuvimos no había nada que ajustar y no se arregló hasta cambiar de
aparato. Ver *Con qué reproducir*, más arriba. La pantalla configurada no se
pierde: cuando la caja nueva enseñe su código, usa el desplegable **«reenlazar
a: …»** y elige la pantalla que era. Hereda su playlist, su horario y su
rotación tal cual.

**El escaparate se queda con contenido viejo.** Las pantallas guardan lo último
reproducido y las imágenes en el propio televisor, así que aguantan sin
servidor. Si el servidor lleva rato caído, aparece un punto tenue en una
esquina.

**El disco se está llenando.** Ajustes lo avisa a partir del 90 %. Cuando se
llena fallan las subidas y puede corromperse la configuración: borra vídeos
antiguos de la librería.

**Actualizar el programa.** Ejecuta el instalador nuevo encima. Para el servidor
antes de copiar nada y conserva pantallas, contenido y contraseña. La versión
instalada se ve en Ajustes.

---

## Dónde está cada cosa

| | |
|---|---|
| Programa | `C:\Program Files\InTeks Display\` |
| Datos, subidas y registro | `C:\ProgramData\InTeks Display\` |
| Registro de errores | `…\InTeks Display\server.log` |
| Extensión de Chrome | `C:\Program Files\InTeks Display\extension\` |

Los datos **no** se borran al desinstalar.
