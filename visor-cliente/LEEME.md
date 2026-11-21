# Visor de cliente

Enseña en una tablet o minipantalla **solo un recuadro** de una web (por ejemplo, el «Resumen»
de un envío de Western Union), nunca el resto de la pantalla.

- `extension/` — extensión de Chrome (versión 3.0). Se instala en el PC del mostrador («Cargar descomprimida»).
  Desde su icono: se pega UNA vez la dirección del servidor de InTeks Display y el token de API
  (Ajustes → Seguridad del panel), se añaden los recuadros de cada web, se elige la pantalla por su nombre
  y se pulsa «Mostrar en la pantalla». El vídeo va del PC a la tablet por la wifi (WebRTC); el servidor de
  InTeks Display solo guarda el «saludo» inicial (unos 2 KB, en memoria, caduca a la media hora).
  - `extension/script_google/` — el buzón antiguo de Google. YA NO SE USA; se deja como respaldo hasta
    que la tablet real esté probada con el servidor. Se puede borrar después.
- La tablet no lleva nada especial: es una pantalla más de InTeks Display (la app de `android/`), y
  `player.html` ya trae la capa del visor. Enseña el recuadro solo mientras hay imagen y el mostrador lo
  tiene activado; el resto del tiempo, la publicidad.
- `android-tablet/` — app mínima antigua para la tablet. YA NO HACE FALTA (se deja hasta probar).
- `programa-pc/` — versión anterior en Python: copia una zona de la pantalla y la muestra en el
  segundo monitor por cable, o en un navegador de la tablet. Ya no hace falta.

No tiene relación con el proyecto Cierre de Caja.

Qué probar con aparatos reales: ver `PRUEBAS.md`.
