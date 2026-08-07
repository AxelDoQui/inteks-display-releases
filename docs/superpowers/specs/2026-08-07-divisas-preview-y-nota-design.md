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
