# Mandar a pantallas desde la Librería — diseño

Fecha: 2026-10-30. Pieza 3 de 4. Todo por IP local. Decisiones tomadas sin
preguntar (Axel pidió «ve haciendo todo»); se corrigen si no le gustan.

## Problema
Para poner un archivo en una pantalla hay que entrar en el editor de playlist de
cada pantalla y añadirlo a mano. Con varias tiendas y varias pantallas es
lento, y no se puede mandar un mismo archivo a muchas a la vez.

## Diseño

### Dónde
- **Ficha del archivo:** botón «Mandar a pantallas».
- **Cuadrícula:** casilla de selección en cada miniatura; al marcar una o más
  aparece una barra «N seleccionados · Mandar a pantallas · Quitar selección».

### Diálogo «Mandar a pantallas»
- Lista de pantallas registradas, con casilla y nombre (todas desmarcadas al
  abrir; enlace «Marcar todas»).
- Duración por imagen en segundos (por defecto 8; los vídeos usan su duración).
- Botón «Mandar». Pantalla ya con ese archivo: se salta (sin duplicar).
- Resultado: «Añadido a 3 pantallas · 1 ya lo tenía».
- Se añade al final de la playlist.

### Servidor
`POST /api/send-to-screens` `{ids: [itemId…], screens: [screenId…], duration?: n}`
- Exige auth (ruta no pública). `ids` y `screens` listas no vacías de cadenas,
  máx. 200 ids y 100 pantallas; `duration` número 1–3600 (por defecto 8).
- Una sola operación bajo `contenido_en_edicion()`. Id que no existe en la
  Librería → 404 sin guardar nada. Pantalla que no está en el registro
  (`screens.json`) → 404 sin guardar nada.
- Por cada pantalla y cada id: si ya hay una entrada directa con ese `id` en
  su playlist, se cuenta como «ya estaba»; si no, se añade `{...item, duration}`
  (copia del item, igual que hace el editor de playlist).
- Pantalla sin entrada en `content["screens"]` → se crea
  `{"mode": "independent", "playlist": []}`.
- Respuesta `{"ok": true, "added": N, "skipped": M}` (N, M = pares
  pantalla×archivo). Llama a `notify_all()`.

## Fuera de alcance
Programar horarios al mandar (ya existe `desde`/`hasta` en el editor), mandar
paquetes, quitar de pantallas desde la Librería, orden concreto en la playlist.

## Pruebas
- `tests/test_mandar_pantallas.py` (servidor real, puerto 8124): añade a 2
  pantallas; segundo envío cuenta `skipped`; vídeo/imagen con `duration`;
  pantalla inexistente → 404 sin cambios ni `rev`; id inexistente → 404;
  listas vacías → 400; sin token → 401; pantalla sin entrada en content se crea.
- `tests/mandar-pantallas.test.js`: función pura `mensajeEnvio(r)` y
  `parseSeleccion`.
