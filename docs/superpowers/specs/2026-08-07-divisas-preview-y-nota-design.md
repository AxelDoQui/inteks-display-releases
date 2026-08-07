# Divisas: vista previa por pantalla y mensaje al pie

**Fecha:** 7 de agosto de 2026
**Estado:** aprobado, pendiente de plan de implementación

## Problema

Al montar un módulo de divisas en el admin no hay forma de saber cuántas filas
van a caber en cada pantalla. Se edita a ciegas y hay que ir físicamente a mirar
el televisor. Además no existe manera de poner un aviso debajo de las
cotizaciones para las jornadas en que los tipos se mueven mucho.

## Lo que ya funciona (no rehacer)

`setupFxPagination()` (`player.html:495`) **ya pagina correctamente en tiempo
real**: mide la altura disponible del contenedor y la altura real de cada fila
en el DOM, las agrupa en páginas, muestra el indicador `1 / 3` y avanza el slide
solo tras la última página.

Esto es más fiable que estimar por resolución, porque los tamaños usan `clamp()`
con unidades `vw`/`vh` y además hay rotación y modo vertical. **La paginación no
se toca.** El problema es exclusivamente de autoría: el admin no informa.

## Requisitos

1. Debe funcionar con **cualquier tipo y tamaño de pantalla**, sin valores fijos.
2. El mensaje al pie lo **escribe el usuario a mano**. Sin histórico de
   cotizaciones ni detección automática de volatilidad.
3. El mensaje es un **pie fijo, visible en todas las páginas**. Un descargo que
   solo aparece a veces no cumple su función.

## Diseño

### 1. La resolución la escribe el usuario

**Revisado el 2026-08-07, tras implementar la autodetección y descartarla.**

La primera versión detectaba la resolución automáticamente: el player la
reportaba a `POST /api/screen-info` y se guardaba en `screens.json`. Se ha
retirado por completo en favor de que el usuario la escriba.

Motivos:

- La autodetección solo sabe de pantallas **ya conectadas**. Escribiéndola se
  puede preparar el contenido de un cliente antes de instalar nada, que es el
  caso real de uso al vender el producto.
- El endpoint tenía que ser público, porque las pantallas no tienen sesión
  (`server.py:690` es una puerta de control). Eso obligaba a defenderlo de
  escrituras de cualquiera en la red. Al quitarlo desaparece esa superficie.
- Elimina el caso "pantalla sin datos todavía" y toda la lógica de rotación:
  el usuario escribe `1080×1920` para una pantalla vertical y ya está.

En el admin: un desplegable de resoluciones habituales (Full HD horizontal,
4K, 1366×768, HD, Full HD vertical, tablet vertical) más dos campos de ancho y
alto para cualquier otra. La elección se guarda en `localStorage`, no en el
contenido: es una preferencia de quien edita, no un dato del módulo.

**La previa es opcional y viene apagada.** Una casilla la muestra u oculta, y
el estado también se recuerda en `localStorage`. Al apagarla se **destruye el
iframe**, no se limita a ocultarlo: mantener un player entero cargado en
memoria cuando nadie lo mira no tiene sentido, y así el panel de divisas pesa
lo mismo que antes para quien no use la previa.

Se muestra pequeña: el contenedor se limita a 440 px de ancho, y el factor de
escala sale de ahí. Es una miniatura de comprobación, no una segunda pantalla.

### 2. Modo preview del player — `player.html?preview=1`

Sin parámetro `screen`. En este modo el player **no**:

- abre la conexión SSE,
- se registra en el registro de pantallas,
- aplica la comprobación de horario ni muestra el standby.

Sin estas exclusiones, abrir el player dentro del admin marcaría una pantalla
como conectada y ensuciaría `screens.json`.

### 3. Contrato de previsualización (postMessage)

El iframe no lee la playlist guardada: renderiza lo que el admin le inyecta, de
modo que los cambios se ven **antes de guardar**.

```
admin  → iframe   { type: "preview-item",  item: {…módulo fx en edición…} }
iframe → admin    { type: "preview-pages", pages: 2, rowsFirstPage: 5 }
```

Interfaz deliberadamente estrecha: el iframe es un servicio de "renderiza este
item a este tamaño y dime cuántas páginas salen". No necesita saber qué pantalla
representa.

### 4. Fidelidad del iframe

El iframe se crea con las **dimensiones reales en píxeles** de la pantalla
seleccionada y se reduce visualmente con `transform: scale(f)`, con
`transform-origin: top left` y un contenedor de alto `h*f`.

El factor es `f = anchoDisponibleDelPanel / w`, limitado a un máximo de 1 para
no ampliar pantallas pequeñas. El contenedor se recalcula en el `resize` de la
ventana del admin.

Es el punto crítico del diseño: los `clamp()`, `vw` y `vh` se resuelven contra
el viewport real del iframe. Si en su lugar se creara un iframe pequeño, las
fuentes se calcularían con otros valores y la previsualización mentiría
justo en lo que se quiere comprobar.

### 5. Mensaje al pie

Campo nuevo `footer_note` (string, por defecto `""`) en los items de tipo `fx`.
En el player, un `<div class="mod-fx-note">` hermano de `.mod-fx-rows` dentro de
`.mod-fx`, con `flex-shrink:0`.

**No requiere cambios en la paginación.** `.mod-fx-rows` es `flex:1;
min-height:0`, así que el hermano le resta alto automáticamente, y
`setupFxPagination()` mide `container.clientHeight` del DOM ya renderizado. El
recálculo es automático.

Si `footer_note` está vacío, el `div` no se renderiza y no ocupa alto.

### 5b. Reparto del alto y escalado tipográfico

**Añadido el 2026-08-07, a raíz de lo que destapó la propia vista previa.**

En una pantalla 4K vertical (2160×3840) seis divisas ocupaban el 14% del alto y
quedaban diminutas en el centro. Dos causas:

- `.mod-fx-rows` llevaba `justify-content:center`, que agrupa las filas y
  reparte el sobrante arriba y abajo.
- **Todos los techos de los `clamp()` estaban saturados.** Se calibraron para
  Full HD: a 2160 px de ancho, `2vw` son 43 px pero el tope era 28 px. El
  contenido dejaba de crecer justo donde más falta hacía.

Solución: las filas pasan a `flex:1 1 0` para repartirse el alto, y la
tipografía cuelga de una variable `--fx-row-h` que el JS fija a
`alto disponible / filas de la página`. Cada tamaño se expresa como
`min(calc(var(--fx-row-h) * k), N vw)`; el término en `vw` impide que en una
pantalla muy alta el texto crezca hasta salirse por los lados.

**Dos pases, y el orden importa.** `setupFxPagination()` necesita el alto
*natural* de cada fila para decidir las páginas: si midiera con las filas ya
repartidas, la suma sería siempre igual al alto disponible y nunca paginaría
nada. Por eso añade la clase `.fx-measuring`, que restaura temporalmente la
tipografía y el `padding` anteriores, mide, y la quita. Leer `offsetHeight`
fuerza un reflujo síncrono, así que la medición es fiable dentro del mismo
tick. Con esto, **cuántas filas caben por página se sigue decidiendo igual que
antes**; lo único que cambia es cómo se reparte el espacio una vez decidido.

Efecto medido: en 1920×1080 los tamaños apenas se mueven (33 px frente a 28 px
en el nombre del país); en 2160×3840 pasan de 28 px a 97 px, y de 52 px a
151 px en la cotización.

### 5c. Selector de país y moneda en el admin

**Añadido el 2026-08-07.** Objetivo: que un usuario básico no tenga que saberse
los códigos ISO ni teclear bandera, país y nombre de moneda a mano.

`admin.html` ya tenía `CURRENCY_DB` (36 divisas con país, moneda, código y
bandera), usada solo para el OCR y el pegado de texto. Se expone como
desplegable bajo la lista de filas:

- El desplegable se ordena alfabéticamente por país y etiqueta cada entrada
  como «Argentina — Peso argentino (ARS)».
- «Añadir» inserta la fila ya rellena y pone el foco en la tasa, que es lo
  único que falta. Los campos siguen editables.
- «Fila vacía» es el botón anterior, renombrado, para divisas fuera de la base.
- No se permiten duplicados: si la divisa ya está, avisa y no la añade.

**La bandera se convierte de emoji a código de dos letras.** `CURRENCY_DB`
guarda 🇦🇷 pero el campo tiene `maxlength="2"` y un emoji ocupa 4 unidades
UTF-16: entraría truncado y la bandera saldría rota. `flagCode()` ya hacía esa
conversión, así que `fxRowFromCurrency()` la reutiliza.

Cubierto por `tests/fx-currency-picker.test.js`, que además valida los datos:
comprueba que **toda opción con bandera tiene su SVG en `vendor/flags/`**.
`XAF` (África Central) es la única sin bandera porque no tiene emoji de país, y
el test fija ese hecho para que se note si mañana se añade una divisa nueva sin
su SVG.

#### Países de doble moneda y ampliación de la base

En una casa de cambio o un tablero de remesas hay países donde circulan dos
monedas: Venezuela cotiza bolívar **y** dólar, y son dos filas con tasas
distintas. Además faltaban países del corredor de remesas: Ecuador y Honduras
se estaban tecleando a mano.

**Los pares país+dólar no pueden vivir en `CURRENCY_DB`.** `CODE_MAP` se
construye desde esa base indexando por código de moneda con «el último gana», y
lo consume el OCR y el pegado de texto. Una segunda entrada con código `USD`
haría que el OCR etiquetara como Venezuela cualquier dólar detectado en una web.
Por eso viven en `FX_EXTRA_PAIRS`, una lista que solo consume el selector.

- **Monedas nuevas en `CURRENCY_DB`** (códigos nuevos, sin colisión): `HNL`
  Honduras, `NIO` Nicaragua, `PAB` Panamá, `BZD` Belice, `JMD` Jamaica.
- **Pares en `FX_EXTRA_PAIRS`**: Ecuador, El Salvador y Panamá (dolarizados),
  más Venezuela, Argentina, Cuba, Bolivia, Perú y Paraguay (doble circulación).
- Siete banderas SVG nuevas descargadas de flagcdn, la misma fuente a la que
  ya recurre `flagImg()` como respaldo. `vendor/` pasa de 1,6 a 2,1 MB.

La clave de cada opción es `bandera|código`, no el código solo: varios países
comparten `USD` y cada uno es una fila distinta. El control de duplicados al
añadir compara **país y moneda**, para que un tablero pueda llevar varias filas
en dólares con tasas diferentes. Dentro de un mismo país la moneda local se
ordena antes que el dólar añadido.

### 6. Refactor puntual: extraer el agrupamiento

`setupFxPagination()` mezcla hoy tres cosas: medir el DOM, agrupar filas en
páginas y gestionar los temporizadores. El agrupamiento es lógica pura y hoy no
se puede probar.

Se extrae:

```js
function groupRowsIntoPages(heights, avail)  // → [[0,1,2],[3,4],…] índices
```

`setupFxPagination()` pasa a medir y delegar. Es una mejora acotada al código
que ya se está tocando, no una refactorización oportunista.

## Modelo de datos

| Dónde | Campo | Tipo | Por defecto |
|---|---|---|---|
| item `fx` en `content.json` | `footer_note` | string | `""` |
| `localStorage` del admin | `signalos_fx_preview_size` | `{w,h}` | 1920×1080 |
| `localStorage` del admin | `signalos_fx_preview_on` | `"0"` / `"1"` | apagada |

`footer_note` es aditivo y opcional: el contenido existente sigue funcionando
sin migración. La resolución de la previa no toca el contenido en absoluto — es
una preferencia de quien edita, y por eso vive en `localStorage`.

## Pruebas

Nuevo `tests/fx-pagination.test.js`, con el mismo arnés que
`tests/schedule.test.js`: extrae la función del propio `player.html` y la
ejecuta en un `vm` de Node, para no probar una copia que se desincronice.

Casos sobre `groupRowsIntoPages`:

1. Todas las filas caben → una sola página.
2. Desbordan → reparto correcto entre páginas.
3. Menos alto disponible (simula el pie activo) → menos filas por página.
4. Una sola fila más alta que el espacio disponible → se coloca igualmente en su
   página, sin bucle infinito ni página vacía.
5. Lista vacía → cero páginas, sin excepción.

El resto (iframe, postMessage, panel del admin) se verifica a mano; montar
un DOM completo en Node no compensa para este tamaño de proyecto.

## Casos límite

| Situación | Comportamiento |
|---|---|
| Resolución vacía o disparatada | Se limita a 240–7680 px y cae a 1920×1080 |
| Tamaño escrito que no coincide con ningún preset | El desplegable pasa a "Personalizada" para que no mienta |
| El iframe no carga | Mensaje explícito en lugar de un recuadro en blanco |
| `footer_note` vacío | No se renderiza el `div`; no roba alto |
| Pantalla girada | El usuario escribe la resolución tal y como se ve (1080×1920). No hay lógica de rotación |
| Mensaje muy largo | El pie se limita a `max-height: 18%` del alto del módulo, con `overflow: hidden`, para que no ahogue a las filas |

## Fuera de alcance

- Detección automática de volatilidad e histórico de cotizaciones.
- Previsualización de otros módulos distintos de divisas. La arquitectura queda
  preparada (el contrato de preview es genérico), pero solo se cablea `fx`.
- Cambiar la paginación en tiempo real, que ya funciona.
