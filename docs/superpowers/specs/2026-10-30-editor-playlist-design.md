# Editor de playlist más fácil — diseño

Fecha: 2026-10-30. Solo panel (`admin.html`): no cambia servidor ni player.
Axel: «no es tan fácil de usar y agregar contenido a la pantalla».

## Problema (visto en el modal «PLAYLIST — pantalla»)
- Cada elemento mide ~190 px (fechas «se ve del/al» siempre visibles, estrella,
  quitar, flechas): con 10 elementos hay que bajar mucho.
- La librería del modal es una columna estrecha de 2 miniaturas, sin buscador ni
  filtros (carpetas/etiquetas/tipo existen ya en la Librería) y sin señal de qué
  está ya en la playlist.
- Se añade de uno en uno, pulsando una miniatura.
- Reordenar: flechas pequeñas y arrastre sin indicador de destino.

## Diseño

### Playlist (columna izquierda)
- Fila compacta (~56 px): asa, miniatura 48×27, nombre (una línea, recortado),
  insignia de tipo, duración (número editable; vídeo = «auto»), estrella y
  botón «⋯».
- «⋯» abre/cierra un **panel dentro de la fila** con lo menos usado: fechas
  «se ve del / al», quitar, subir/bajar. Se abre solo si ya hay fechas puestas
  (para que no queden ocultas) y la fila lo indica con un punto.
- Un paquete conserva su fila especial (también compacta).
- Pie fijo: «N elementos · M min S s por vuelta» (suma de duraciones; los vídeos
  cuentan su duración si se conoce `duration`, si no se dejan fuera y el texto
  añade «+ vídeos»).
- Línea de inserción visible al arrastrar (no solo resaltar la fila destino).

### Selector de contenido (columna derecha)
- Buscador, desplegable de carpeta y chips de etiquetas, filtro de tipo
  (mismos criterios que la Librería: reutilizar `filtrarOrdenar`,
  `listasDeOrganizacion`).
- Miniaturas más grandes (3 por fila en ancho normal, auto-fill 120 px).
- Cada miniatura: casilla de selección; marca «✓ ya está» si su `id` ya está
  en la playlist (sigue pudiendo añadirse otra vez).
- Barra del selector: «Añadir N» (los marcados, al final, en el orden en que
  aparecen en pantalla) y «Quitar marca». Un clic en la miniatura (no en la
  casilla) añade solo esa, como hoy.
- Arrastrar una miniatura a la playlist la inserta en el punto donde se suelta.

### Ajustes de la pantalla (arriba)
- Una fila: Transición (+ ms), Orden aleatorio, y un botón «Más ajustes»
  que despliega prioridad ⭐, margen de seguridad y el texto explicativo.
  Plegado por defecto salvo que prioridad o margen tengan valor distinto del
  predeterminado.

## Fuera de alcance
Cambiar cómo se guarda la playlist, programar por horas, previsualizar la
pantalla, el editor de videowall.

## Pruebas
Lógica pura con test de Node (`tests/editor-playlist.test.js`, bloque entre
`// ── Editor de playlist` y `// ── fin del editor de playlist`):
- `resumenPlaylist(pl, items)` → `{n, segundos, videosSinDuracion, texto}`.
- `idsEnPlaylist(pl)` → `Set` de ids directos.
- `insertarEn(lista, nuevos, posicion)` → lista nueva (posición fuera de rango
  = al final; no muta).
- `ajustesDistintosDeDefecto(cfg)` → boolean.
La parte visual se comprueba a mano en el navegador con servidor temporal.
