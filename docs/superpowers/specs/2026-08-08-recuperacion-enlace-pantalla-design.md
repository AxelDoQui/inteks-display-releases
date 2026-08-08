# Recuperación del enlace de una pantalla

**Fecha:** 2026-08-08
**Estado:** aprobado, pendiente de plan de implementación

## El problema

Una pantalla enlazada puede perder el camino de vuelta a su contenido, y hoy el
sistema no tiene forma de devolvérselo sin destruir su configuración.

Tres decisiones razonables por separado forman, juntas, un callejón sin salida:

1. `index.html:35` — al arrancar, si hay identidad en `localStorage` va al
   player; si no, a `/pair`.
2. `pair.html:124` — `pedirCodigo()` se llama incondicionalmente. `/pair` nunca
   comprueba si el dispositivo ya estaba enlazado: pide un código nuevo siempre.
3. `server.py:923-924` — `pair-claim` rechaza cualquier nombre que ya exista:
   *«Ya existe una pantalla llamada 'X'»*.

Resultado: abres `/pair` en un televisor ya enlazado, sale un código, escribes en
el panel el nombre real de esa pantalla y **el servidor te lo rechaza**. Las
únicas salidas son inventarse «Escaparate-2», que nace con la playlist vacía, o
borrar la pantalla original y perder su configuración.

La comprobación del punto 3 existe para protegerte de pisar una pantalla por
error. El fallo es que no distingue *crear* de *reenlazar*, así que bloquea justo
el caso que hay que arreglar.

### Las dos puertas por las que se entra al callejón

- **La URL de arranque es `/pair`.** Ocurre porque nadie recuerda la URL exacta
  del player y el emparejamiento es lo que se tiene a mano.
- **El navegador del televisor borra `localStorage` al apagarse.** Modo kiosco,
  incógnito, o limpieza de memoria en Android TV. La pantalla pierde su identidad
  y tampoco se le puede devolver.

### Lo que ya funciona y no se toca

El player reintenta el SSE cada 4 s indefinidamente (`player.html:303`) y guarda
en caché lo último reproducido. Un televisor que se enciende antes que el PC del
servidor se recupera solo. Ese camino queda como está.

## Decisiones

| Decisión | Elegida |
|---|---|
| Qué se puede hacer con un código en espera | Crear una pantalla nueva **o** reenlazar a una existente |
| `/pair` en un dispositivo ya enlazado | Aviso breve con cuenta atrás + botón de desenlazar |
| Resistencia a perder la identidad | Dos almacenes + enlace directo copiable desde el panel |

### Cómo se verifica que la pantalla sigue existiendo — enfoque A

Cuando `/pair` encuentra una identidad guardada tiene que saber si esa pantalla
sigue existiendo en el servidor. Se evaluaron tres formas:

- **A. Delegarlo en el player.** `/pair` redirige sin preguntar. Si la pantalla
  fue borrada, el SSE responde `deleted:` (`server.py:667`), el player olvida la
  identidad y vuelve a `/pair`.
- **B. Endpoint público `POST /api/screen-check`.** Sin rebote, pero es un
  endpoint *antes* de la puerta de autenticación que confirma nombres de
  pantalla: un oráculo de enumeración.
- **C. Que `pair-request` decida.** Mismo oráculo que B y además enreda el
  endpoint, que necesitaría un modo «dame código igualmente».

**Se elige A.** Cuesta un rebote de aproximadamente un segundo en un caso raro
(pantalla borrada desde el panel mientras el dispositivo la recordaba), pero no
añade ninguna superficie pública nueva y reutiliza un camino ya probado. Tiene
además una ventaja no buscada: con el servidor caído, el televisor termina en el
player mostrando su caché en lugar de en un código inútil.

De C se conserva una idea: `pair-request` puede llevar `known_as`, para que el
panel indique de qué pantalla venía ese código.

## Diseño

### 1 · La identidad vive en dos almacenes

Tres funciones sobre `localStorage` y una cookie de un año:

```js
leerIdentidad()        // localStorage, y si no hay, la cookie
guardarIdentidad(sid)  // escribe en los dos
olvidarIdentidad()     // borra los dos
```

Cookie: `signalos_screen=<sid>; Path=/; Max-Age=31536000; SameSite=Lax`.

El nombre de la cookie usa el prefijo `signalos_` igual que
`signalos_screen_id`: los identificadores internos conservan el nombre antiguo a
propósito, porque renombrarlos desenlazaría las pantallas ya instaladas.

**Regla crítica:** `olvidarIdentidad()` limpia los dos almacenes. Hoy
`player.html:293` solo borra `localStorage`. Si se añade la cookie sin corregir
eso, una pantalla borrada entra en bucle infinito:

```
/pair lee la cookie → player → SSE «deleted» → borra solo localStorage
   → /pair → la cookie sigue ahí → player → …
```

Dos almacenes solo son más robustos si se olvidan a la vez.

**Las tres funciones van repetidas literalmente** en `index.html`, `pair.html` y
`player.html`, no en un `identidad.js` compartido. Un `<script src>` obliga a
hablar con el servidor antes de poder decidir a dónde ir, y con el servidor caído
el televisor se quedaría en blanco. Cada página tiene que poder decidir sola.

La duplicación se defiende con un test que exige que las tres copias sean
idénticas carácter a carácter, igual que hace `currency-db-sync` con la base de
divisas.

### 2 · `/pair` deja de pedir código a ciegas

| Situación | Comportamiento |
|---|---|
| Hay identidad guardada | «Ya enlazada como «Escaparate» · abriendo en 6 s», más un botón grande **Enlazar de nuevo**. Al agotarse la cuenta, va a `/player.html?screen=<sid>` |
| No hay identidad | Pide código, como hasta ahora |
| `/pair?nuevo=1` | Pide código aunque haya identidad |

Cualquier tecla o clic **cancela la cuenta atrás** y deja el botón esperando, sin
depender de que el foco haya caído donde toca. Los mandos de televisor navegan
con flechas y acertar con el foco no siempre es fácil.

El botón **Enlazar de nuevo** navega a `/pair?nuevo=1&era=<nombre>` y *después*
llama a `olvidarIdentidad()`. El orden importa: el nombre recordado tiene que
viajar en la URL antes de borrarse de los almacenes, o se pierde y el panel ya no
puede sugerir el reenlace. La página, al cargar con `?nuevo=1`, envía el valor de
`era` como `known_as`.

### 3 · `pair-claim` distingue crear de reenlazar

`POST /api/pair-claim` acepta `{code, screen_name, modo}` con `modo` en
`"nueva"` o `"reenlazar"`:

- **`"nueva"`** (valor por omisión) — error si el nombre ya existe. Idéntico al
  comportamiento actual, así que los tests que ya existen siguen siendo válidos
  sin modificarlos.
- **`"reenlazar"`** — error si el nombre **no** existe. No toca `content.json`:
  la playlist, el horario y la rotación de esa pantalla siguen intactos.

Reenlazar a una pantalla que está conectada en ese momento **se permite**: dos
televisores mostrando el mismo tablero es un uso legítimo. El panel avisa antes
de hacerlo.

### 4 · `pair-request` acepta `known_as`

`POST /api/pair-request` acepta un cuerpo opcional `{known_as: "Escaparate"}`. El
valor se guarda junto al código pendiente y se devuelve en `pair-pending`, para
que el panel muestre *«dice que era «Escaparate»»* y ofrezca el reenlace en un
clic.

`known_as` es un dato sin autoridad: lo envía un dispositivo no autenticado y
solo sirve como sugerencia visual. El reenlace real lo decide el administrador
desde el panel, y `pair-claim` valida el nombre contra `screens.json` como
siempre.

### 5 · Desenlazar desde el panel

`POST /api/screen-unlink {screen}` — detrás de la puerta de autenticación.

Añade `notify_unlink(screen_id)` junto a `notify_deleted()` (`server.py:381`),
emitiendo `data: unlink:<sid>`. El player lo trata como el mensaje `deleted:`
pero con una diferencia esencial: **el servidor no borra nada**. La pantalla
sigue en `screens.json` y su configuración sigue en `content.json`; solo el
dispositivo olvida quién era.

Al recibirlo, el player navega a `/pair?nuevo=1&era=<sid>` y luego olvida su
identidad, en ese orden y por el mismo motivo que el botón de la sección 2. El
`?nuevo=1` es imprescindible: sin él, `/pair` podría leer una identidad que
todavía no se ha terminado de borrar y devolver el televisor al player.

Es la forma de reenlazar a propósito sin levantarse a tocar el televisor.

Con una pantalla que no existe, responde 400.

### 6 · Enlace directo copiable

Cada pantalla del panel lleva un botón que copia
`http://<host>/player.html?screen=<nombre>`. Es la solución para los televisores
que borran todo al apagarse: se pega como página de inicio y la identidad viaja
en la URL, donde ningún borrado la alcanza.

## Flujo de datos

**Arranque normal:**

```
TV enciende → / → leerIdentidad() → hay → /player.html?screen=X
                                  → SSE conecta → contenido
```

**Arranque por /pair estando enlazada:**

```
TV enciende → /pair → leerIdentidad() → hay
   → «Ya enlazada como X · 6 s» → /player.html?screen=X
```

**Identidad perdida:**

```
TV → /pair → no hay → pair-request → código 4821 en pantalla
Panel → «4821» → desplegable «reenlazar a: Escaparate»
   → pair-claim {modo:"reenlazar"} → pair-status devuelve «Escaparate»
   → guardarIdentidad("Escaparate") → player con SU playlist de siempre
```

**Reenlace deliberado:**

```
Panel → Desenlazar «Escaparate» → notify_unlink
   → el TV va a /pair?nuevo=1&era=Escaparate y olvida su identidad
   → pair-request {known_as:"Escaparate"} → código 4821
Panel → «4821 — dice que era Escaparate» → un clic → reenlazada
```

**Pantalla borrada mientras el dispositivo la recordaba:**

```
TV → /pair → hay identidad → player → SSE «deleted:X»
   → olvidarIdentidad() (los dos almacenes) → /pair → pide código
```

## Manejo de errores

| Situación | Respuesta |
|---|---|
| `pair-claim` modo `nueva` con nombre existente | 400, mensaje actual |
| `pair-claim` modo `reenlazar` con nombre inexistente | 400, «Esa pantalla ya no existe» |
| `pair-claim` con código caducado o ya reclamado | 400, mensaje actual |
| `screen-unlink` con pantalla inexistente | 400 |
| Servidor caído durante la cuenta atrás de `/pair` | Redirige igual; el player tira de caché |
| `localStorage` y cookies bloqueados en el televisor | La identidad no persiste; el enlace directo en la URL es el remedio |

## Pruebas

**Python** (`tests/test_emparejamiento.py`):

- reenlazar conserva la playlist, el horario y la rotación de la pantalla
- reenlazar a una pantalla inexistente devuelve 400
- crear con un nombre que ya existe sigue devolviendo 400
- `pair-claim` sin `modo` se comporta como `"nueva"` (retrocompatibilidad)
- `known_as` enviado en `pair-request` aparece en `pair-pending`
- `screen-unlink` no borra la pantalla ni su configuración
- `screen-unlink` sobre una pantalla inexistente devuelve 400
- `screen-unlink` sin autenticación devuelve 401

**Node** (`tests/`):

- las tres copias de las funciones de identidad son idénticas
- `olvidarIdentidad()` limpia `localStorage` **y** la cookie
- `leerIdentidad()` recupera de la cookie cuando `localStorage` está vacío
- con identidad guardada, la lógica de `/pair` no pide código
- con `?nuevo=1`, pide código aunque haya identidad
- con `?nuevo=1&era=X`, el `known_as` enviado es `X`

## Fuera de alcance

- Persistir los códigos pendientes entre reinicios del servidor. Siguen en
  memoria: el emparejamiento dura segundos y se cura solo.
- Autenticar el dispositivo. `known_as` es una sugerencia, no una credencial.
- Descubrimiento automático de pantallas por IP o huella del navegador.
