# Librería más útil — diseño

Fecha: 2026-10-30. Pieza 2 de 4 (la 1, subida robusta, está en 1.0.48).
Todo por IP local: sin nube ni web.

## Problema

La Librería es una cuadrícula de miniaturas: al pulsar una no pasa nada, solo
se puede borrar con la X (sin aviso aunque esté en uso) y no hay búsqueda,
filtros, orden ni datos del archivo.

## Diseño

### Barra superior
- Buscador por nombre.
- Filtro por tipo: Todos, Imágenes, Vídeos, Otros.
- Orden: más nuevos, nombre, tamaño, más usados.
- Contador «N de M» cuando hay filtro activo.

### Miniaturas
- Debajo del nombre: tamaño y tipo (`48 MB · MP4`).
- Insignia «en uso · N» si está en alguna pantalla o paquete.
- Vídeos: duración en una esquina (la lee el navegador de los metadatos).

### Ficha del archivo (panel lateral al pulsar una miniatura)
- Vista previa grande (el vídeo se puede reproducir).
- Datos: nombre, tamaño, resolución, duración, fecha de subida.
- «Dónde se usa»: pantallas y paquetes por nombre.
- **Renombrar**: cambia solo el nombre visible (`name`), no el archivo en disco.
- **Borrar**.

### Borrar con aviso
- En uso: «Está en 2 pantallas y 1 paquete: Tienda Centro, Escaparate… ¿Borrar
  igualmente?». Si confirma, se borra del disco y se quita de esas listas.
- Sin uso: confirmación simple.

### Servidor
- `GET /api/library-info` → por id: `size` (bytes en disco), `created` (fecha de
  modificación del archivo; los antiguos no guardan fecha), `uses`
  (lista `{kind: "screen"|"package", id, name}`). Calcula con
  `expandir_paquetes` lógica de referencias: una entrada de playlist usa el
  item por `id`; un paquete, por `itemIds`.
- `POST /api/rename` `{id, name}` → valida (no vacío, máx. 120 caracteres),
  usa `contenido_en_edicion()`.
- `/api/delete` además quita el id de las playlists de las pantallas y de los
  `itemIds` de los paquetes, bajo el mismo bloqueo.
- Ambas rutas exigen sesión o token, como el resto.

### Panel
Función pura `filtrarOrdenar(items, info, {texto, tipo, orden})` (testable en
Node con el mismo método de marcadores que la subida). El panel pide
`/api/library-info` al abrir la Librería y tras cada cambio.

## Fuera de alcance
Mandar a pantallas desde la ficha (pieza 3), carpetas y etiquetas (pieza 4),
miniaturas generadas en el servidor.

## Pruebas
- `tests/test_libreria_info.py` (servidor real, puerto propio): info con
  tamaño y usos, renombrar (válido y vacío → 400), borrar en uso limpia
  playlists y paquetes, borrar sin uso, sin sesión → 401.
- `tests/libreria-filtro.test.js`: texto, tipo, cada orden.
