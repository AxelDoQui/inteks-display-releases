# Visor de cliente — qué falta probar con aparatos reales

Probado SIN aparatos (simulación): el buzón del servidor (`tests/test_visor_cliente.py`), la capa de
`player.html` (`tests/visor-cliente-player.test.js`) y, en el navegador integrado, un recorrido completo
real de WebRTC entre `player.html` y el código del emisor de la extensión con una captura simulada:
conecta, enseña SOLO el recuadro recortado, lo oculta con «0», reconecta sola tras recargar la tablet,
y vuelve a la publicidad al parar.

NO probado: Chrome real con la extensión, tabCapture, ni la tablet.

## Preparación
1. Servidor de InTeks Display con esta versión (hay que actualizarlo/reiniciarlo: la tablet carga
   `player.html` del servidor, así que no hace falta tocar la app Android).
2. En el PC del mostrador: `chrome://extensions` → modo desarrollador → «Cargar descomprimida» →
   carpeta `visor-cliente\extension`. (Si ya estaba la versión 2.0, quítala o pulsa «Recargar» y
   **recarga también las pestañas abiertas**: los scripts antiguos quedan huérfanos.)
3. Icono de la extensión → «Conexión con InTeks Display»: dirección del servidor (p. ej. `http://192.168.1.20:8080`)
   y el token de API (panel → Ajustes → Seguridad). «Guardar y comprobar» debe decir «Conectado ✔» y
   llenar la lista de pantallas.
4. La tablet: la app de `android/` ya emparejada como pantalla (la actual de la caja vale).

## Pruebas, en orden
1. **Recuadro**: en la web del mostrador, «1. Añadir un recuadro» y elegir el Resumen. Debe guardarse con su nombre.
2. **Mostrar**: elegir la tablet por su nombre → «2. Mostrar en la pantalla». En ~5-10 s la barra de la web
   debe decir «Pantalla conectada» y la tablet enseñar el recuadro encima de la publicidad.
   - Mirar que en la tablet NO se vea nada más de la pantalla del PC (ni bordes, ni la barra).
   - Probar con zoom del navegador distinto de 100 %: el recorte debe seguir cuadrando.
3. **Ocultar/mostrar** desde la barra de la web: al ocultar, la tablet vuelve a la publicidad
   inmediatamente; al mostrar, vuelve el recuadro. Probar a cambiar de recuadro.
4. **Cortes**: (a) apagar y encender la wifi de la tablet; (b) reiniciar la app de la tablet;
   (c) recargar la pestaña del mostrador. En todos, la tablet debe volver sola a la publicidad y,
   tras unos segundos (hasta ~30 s en el caso (a)), recuperar el recuadro sin tocar nada.
5. **Cerrar el navegador del PC con el visor activo**: en ~15 s la tablet debe dejar de enseñar la imagen.
6. **Dejar de mostrar**: la tablet vuelve a la publicidad al instante.
7. **Fluidez**: 10 imágenes/s, hasta 1280 px de ancho. Ver si se lee bien un número de cuenta y si la tablet
   (y el PC) van bien. Si falta nitidez o fluidez, se ajusta `FPS` y `MAX_ANCHO` en `emisor.js`.

## Riesgos conocidos (lo que más puede fallar)
- **Red**: PC y tablet deben verse por la red local. Se han quitado los servidores STUN de Google, así que
  NO funcionaría si están en redes separadas sin ruta entre ellas (la caja Android estaba en otra subred).
  Si no conecta y todo lo demás está bien, es lo primero que mirar (se puede volver a añadir un STUN o abrir la ruta).
- **Nombres `.local` (mDNS)**: Android oculta su IP detrás de un nombre «xxxx.local» y el PC tiene que resolverlo.
  Suele funcionar en Windows 10/11; si el PC se queda en «Esperando a la pantalla…» con la tablet bien,
  sospechar de esto o de un cortafuegos/aislamiento de clientes en el router (AP isolation).
- **Sonido**: si la publicidad lleva vídeo con sonido, seguirá sonando detrás mientras se ve el recuadro.
- **Seguridad**: igual que el resto de pantallas, la tablet se identifica solo por el nombre de pantalla (público en la red
  local). El saludo solo admite UNA respuesta por oferta y la oferta se renueva sola, pero un equipo malicioso de la misma
  red que adivine el nombre de la pantalla y conteste antes que la tablet podría recibir el vídeo. Para un local normal es
  asumible; si preocupa, se añade un secreto por pantalla.
- La pantalla oculta la imagen ante la duda: si el PC deja de avisar 15 s, o con cualquier corte.

## Antes de dar por cerrado
- Subir versión (`tools\subir-version.ps1`) y anotar en `CHANGELOG.md`; no se ha hecho ni commit.
- Si va bien: borrar `extension/script_google/` y `android-tablet/` (y el script publicado en Google).
