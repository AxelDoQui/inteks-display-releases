# Carpetas y etiquetas en la Librería — diseño

Fecha: 2026-10-30. Pieza 4 de 4. Todo por IP local. Decisiones tomadas sin
preguntar (Axel pidió «ve haciendo todo»); se corrigen si no le gustan.

## Problema
Con decenas de archivos, la Librería es una lista plana: solo se encuentra
algo por nombre.

## Diseño

### Modelo (sin tablas nuevas)
Cada contenido admite dos campos opcionales dentro de `content["items"][i]`:
- `folder`: texto (1–40 car.) o ausente. **Una** carpeta por archivo.
- `tags`: lista de textos (1–30 car. cada uno, máx. 10 por archivo), sin duplicados
  ignorando mayúsculas y acentos.

Las carpetas y etiquetas existentes se **deducen** de los propios contenidos:
no hay registro aparte, así que una carpeta sin archivos desaparece sola.

### Servidor
`POST /api/organize` `{ids: [..], folder?: str|null, addTags?: [..], removeTags?: [..]}`
- Exige auth. `ids`: lista no vacía (máx. 200). `folder`: cadena → asigna,
  `null` → quita la carpeta, ausente → no toca. `addTags`/`removeTags` listas
  opcionales de cadenas. Al menos una de las tres acciones.
- Un id inexistente → 404 sin guardar. Valida longitudes (400). Una sola
  operación bajo `contenido_en_edicion()`; si no cambia nada, no guarda ni
  sube `rev`. Respuesta `{"ok": true, "changed": N}`; `notify_all()` si N>0.
- Los nombres de carpeta/etiqueta se guardan recortados (`strip`) y con la
  grafía con la que llegan; si ya existe una equivalente (sin mayúsculas ni
  acentos) se usa **la existente**, para no crear «Verano» y «verano».
- `POST /api/rename` y el resto no cambian. `/api/delete` no necesita cambios.

### Panel
- **Filtros nuevos** en la barra: desplegable «Carpeta» (Todas, Sin carpeta,
  + las que haya) y chips de etiquetas pulsables (varias a la vez = deben tenerlas
  todas). `filtrarOrdenar` admite `carpeta` y `etiquetas`.
- **Miniaturas:** etiqueta de carpeta pequeña (📁 nombre) bajo el nombre.
- **Ficha:** secciones «Carpeta» (desplegable con las existentes + «Nueva
  carpeta…» + «Sin carpeta») y «Etiquetas» (chips con ✕ para quitar y campo para
  añadir con Enter).
- **Selección múltiple (de la pieza 3):** la barra gana «Poner en carpeta…» y
  «Añadir etiqueta…».
- Búsqueda por texto también encuentra por carpeta y etiquetas.

## Fuera de alcance
Carpetas anidadas, renombrar/borrar una carpeta o etiqueta en bloque, colores.

## Pruebas
- `tests/test_organizar.py` (puerto 8126): asignar carpeta y etiquetas a varios;
  quitar carpeta con null; equivalencia sin acentos/mayúsculas reutiliza la
  existente; límites; 404 sin tocar rev; no-cambio no sube rev; 401.
- `tests/organizar.test.js`: `filtrarOrdenar` con carpeta/etiquetas/búsqueda por
  carpeta; `normalizarTexto` ya existente.
