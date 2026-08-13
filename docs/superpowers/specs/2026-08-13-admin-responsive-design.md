# Panel de administración usable desde el móvil — diseño

> Estado: **diseñado, sin implementar** (2026-08-13). Hace que `admin.html`
> funcione en un móvil sin perder ninguna funcionalidad y sin reestructurar el
> monolito.

## El problema

El panel es de escritorio puro. En 216 KB de `admin.html` hay **una sola
`@media`** (línea 81, para `.pl-editor`). Abrirlo en un móvil hoy da esto:

| Elemento | Cómo está | Qué pasa en 375 px |
|---|---|---|
| `.app` | rejilla `220px minmax(0,1fr)` | La barra lateral se come el **59 %** del ancho |
| `.fx-row-edit` | 8 columnas (`18px 40px 1fr 1fr 80px 80px .9fr 32px`) | Necesita ~450 px: no entra |
| `.stats-row` | `repeat(4,1fr)` | Cuatro tarjetas de 80 px |
| `.form-row` | `1fr 1fr` | Campos de 170 px |
| `.modal` | 700 px centrado | Ocupa casi todo, con márgenes desperdiciados |
| Reordenar | `dragstart`/`dragover`/`drop` de HTML5 | **No funciona con el dedo** |

Las rejillas de pantallas (`auto-fill minmax(260px,1fr)`) y librería
(`minmax(110px,1fr)`) sí se adaptan solas.

**El problema serio no es el CSS.** El arrastrar y soltar de HTML5 no existe en
táctil: no es que se vea mal, es que **no hay forma de reordenar una playlist ni
las filas de un tablero con el dedo**. Eso hay que sustituirlo, no adaptarlo.

## Decidido con el usuario

| Decisión | Elegido | Por qué |
|---|---|---|
| Alcance | **Todo se adapta; se pulen las tareas del día a día** | Nadie va a montar un videowall desde el móvil, pero sí mirar si las pantallas viven o actualizar tasas |
| Reordenar | **Botones subir/bajar**, en móvil **y en escritorio** | Sin librerías, funciona con dedo, ratón y mando. El arrastre actual se queda para el ratón |
| Editor de divisas en móvil | **Solo la tasa; el resto plegado** | De los ocho campos de una fila, el único que cambia a diario es la tasa |
| Dónde vive el código | **En `admin.html`, en un bloque `@media` propio** | Un segundo panel se desincroniza; ver abajo |

### Por qué no las otras vías

**Un `movil.html` aparte.** Rápido de hacer y deja el panel de escritorio
intacto, pero son dos interfaces que mantener: cada función nueva habría que
hacerla dos veces, y en la práctica el móvil se queda atrás hasta que deja de
servir. Descartado.

**Reescribir el arrastre con eventos de puntero** (un solo mecanismo para dedo
y ratón). Es más elegante y arrastrar sigue siendo lo natural en listas largas,
pero obliga a resolver el desplazamiento automático al llegar al borde y a
impedir que la página se mueva mientras arrastras. Mucho más código y más
riesgo para un problema que dos botones resuelven. Descartado por ahora.

**Paridad total pulida en las 14 secciones.** Más superficie que probar en cada
cambio futuro, a cambio de pulir pantallas que nadie va a usar desde un móvil.

## Forma de la solución

**Una capa encima, sin reestructurar nada.** `admin.html` lleva quince
versiones funcionando; el CSS de escritorio no se toca.

```
admin.html
├── CSS de escritorio actual        ← intacto
├── NUEVO: bloque responsive        ← todo lo nuevo vive aquí
│     @media (max-width: 860px)     tableta y móvil apaisado
│     @media (max-width: 560px)     móvil
└── JS actual                       ← intacto
      + menú lateral (abrir/cerrar)
      + botones subir/bajar
      + plegar/desplegar fila de divisas
```

**Regla:** si se puede resolver con CSS, no se toca el JS. Así el riesgo sobre
lo que hoy funciona se queda casi en cero y lo nuevo está agrupado en un sitio
identificable.

### Los cambios de layout, y en qué punto de corte entra cada uno

| Elemento | ≥ 861 px (hoy) | ≤ 860 px | ≤ 560 px |
|---|---|---|---|
| `.app` | `220px + resto` | Una columna; lateral en cajón | igual |
| `.stats-row` | `repeat(4,1fr)` | `repeat(2,1fr)` | `repeat(2,1fr)` |
| `.form-row` | `1fr 1fr` | `1fr 1fr` | 1 columna |
| `.pl-editor` | `1fr 260px` | 1 columna | 1 columna |
| `.modal` | 700 px centrado | 700 px centrado | Pantalla completa |
| `.fx-row-edit` | 8 columnas | 8 columnas | Solo la tasa; resto plegado |
| Campos de texto | 12-13 px | 12-13 px | **16 px** (zoom de iOS) |
| Botones de acción | como están | 44 px de alto | 44 px de alto |

La regla detrás del reparto: **a 860 px lo que sobra es ancho de layout**
(la barra lateral, las columnas), y **a 560 px lo que falta es sitio para el
dedo** (campos, objetivos táctiles, el modal).

**La `@media (max-width:700px)` que ya existe** para `.pl-editor` (línea 81) se
absorbe en el bloque de 860 y se borra de donde está. Tres puntos de corte
sueltos en un archivo de 216 KB es exactamente como se llega a un CSS que nadie
entiende.

### La navegación

La barra lateral pasa a **cajón deslizante**, con botón de menú en la barra
superior (visible solo por debajo de 860 px). Se cierra al elegir sección y al
tocar fuera. Las 14 entradas ya llevan icono, así que el cajón se lee tal cual.

### Las cuatro tareas que se pulen

**Pantallas.** Sale casi gratis: la rejilla ya cae a una columna. Solo hay que
subir los botones de la tarjeta a 44 px de alto.

**Divisas.** El cambio de verdad. La fila queda en país + código como texto y
un campo grande para la tasa, con *editar* para desplegar bandera, moneda y
ventanilla:

```
  🇨🇴 Colombia · COP        [ 3606  ]
  [↑] [↓]                    editar
```

La previa del tablero —hoy un iframe dimensionado a la resolución de la
pantalla— se pliega en móvil detrás de un botón **«ver previa»**: ocupa
demasiado justo cuando lo que quieres es teclear ocho números.

**Playlist.** Se edita en un modal, que en móvil pasa a pantalla completa. Cada
contenido gana sus botones subir/bajar.

**Ajustes y avisos.** `.form-row` de dos columnas a una. Prácticamente gratis.

### Reordenar sin rutas de escritura nuevas

Los módulos de divisas viven **duplicados**: una copia en la librería y otra
dentro de la playlist de cada pantalla que los use. `saveFxModule()` escribe la
librería *y propaga* a las playlists.

Si los botones tocaran el array y guardaran por su cuenta, reordenarían una
copia y dejarían la otra como estaba, y **el siguiente guardado del admin
desharía el cambio en silencio** — un fallo que no se ve en el paso que lo
causa, sino uno después.

**Por eso los botones no escriben nada.** Reordenan el array en memoria y
llaman a la misma función de guardado que ya usa el arrastre. Cero rutas de
escritura nuevas.

**Dónde aparecen los botones**, para que no quede a interpretación: en los
elementos de la playlist (el modal de una pantalla) y en las filas del editor
de divisas. En los dos sitios van **siempre visibles, también en escritorio**,
y no sustituyen al arrastre: conviven. El botón de subir del primer elemento y
el de bajar del último quedan deshabilitados, no ocultos, para que la fila no
cambie de tamaño según su posición.

**El desplegar de la fila de divisas** es estado por fila y transitorio: no se
guarda en ningún sitio y todas las filas vuelven a plegarse al recargar. Es una
comodidad de edición, no una preferencia del usuario.

### Ergonomía táctil

- **Campos a 16 px en móvil.** Están a 12-13 px, y iOS **hace zoom automático
  al enfocar un campo con letra menor de 16 px**: cada toque daría un salto de
  zoom que hay que deshacer a mano. Es de las cosas que hacen que una web
  responsive se sienta rota aunque el layout esté perfecto.
- **Objetivos táctiles de 44 px** en botones de acción.
- **`100dvh` con `100vh` de reserva** en `.app`: con `100vh` a secas, la barra
  de direcciones del móvil recorta el contenido por abajo.

## Cómo se prueba

**La lógica, con tests.** Reordenar es una función pura —mover un elemento de
una posición a otra— y entra en el arnés que ya existe: se extrae el bloque de
`admin.html` y se ejecuta en un `vm` de Node, como hace `schedule.test.js` con
el player. Casos: mover el primero hacia arriba y el último hacia abajo (no
deben hacer nada), y que la lista no pierda ni duplique elementos.

**El aspecto, renderizando**, que es la regla de la casa. Chrome headless a
390×844 (móvil) y 820×1180 (tableta), con capturas de cada sección tocada.

`admin.html` exige sesión, así que una captura a pelo cae en el login. Se
resuelve con el mismo truco ya usado para el tablero de divisas: una página
auxiliar servida por el propio servidor de pruebas que hace `login` y redirige,
todo en el mismo origen.

**Qué se mide en las capturas**, para no fiarse del ojo: que ningún elemento
desborde el ancho del viewport, y que los botones de acción midan 44 px o más.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Romper el escritorio | Todo lo nuevo dentro de `@media`; el CSS actual no se toca |
| Deshacer un reordenado de divisas | Los botones no escriben: llaman a la función de guardado existente |
| 409 entre dos paneles al reordenar | Comportamiento normal ya existente: guardar sube `rev` y el otro panel se entera |

## Lo que no se puede verificar aquí

Cómo se siente en el móvil de verdad. Se pueden medir anchos, capturar y
comprobar que nada se sale, pero el tamaño real de los botones bajo el pulgar y
si el cajón se abre con soltura lo tiene que decir quien tenga el teléfono en
la mano.

## Fuera de alcance, a propósito

- **Reescribir el arrastre con eventos de puntero.** Anotado arriba.
- **Pulir las diez secciones que no son del día a día.** Se adaptan y se usan,
  pero no se les dedica diseño específico.
- **Convertir el panel en PWA instalable.** `sw.js` existe y solo se activa
  bajo HTTPS o localhost; nada que ver con esto.
- **Modo claro.** El panel es azul marino con acento naranja y así se queda.
