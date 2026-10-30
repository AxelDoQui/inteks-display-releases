# APK: diagnóstico en la caja y versión visible en el panel — diseño

Fecha: 2026-10-30. Decisiones tomadas sin preguntar (Axel pidió «ve haciendo
todo»). **No incluye la actualización automática del APK**: instalar un APK
nuevo en una caja sin pantalla táctil ni forma de probarlo aquí podría dejar la
caja inservible en una tienda; queda como propuesta para hacerla con una caja de
pruebas delante.

## Problema
Si una pantalla va mal no hay forma de saber desde el PC qué versión de APK
tiene la caja, ni desde la caja a qué servidor intenta hablar o desde cuándo.

## Diseño

### Caja (Android)
- `KioskActivity` expone al reproductor una interfaz JS **solo de lectura**
  `InTeksApp.version()` → `versionName` del APK. Nada más.
- `SettingsStore.ultimaConexionOk` (epoch ms): se anota cuando el marco
  principal termina de cargar sin error (`onPageFinished` con
  `errorEnEstaCarga == false`).
- La pantalla de mantenimiento (`SetupActivity`, se abre con 5 pulsaciones de
  Atrás o con OK en la búsqueda) muestra una línea de diagnóstico: versión del
  APK, servidor guardado, nombre de pantalla y «última conexión buena: hace N
  min / nunca». Función pura `textoDiagnostico(version, base, pantalla, ultimaOk,
  ahora)` con test unitario.

### Reproductor y servidor
- `player.html`: `reportarAhora` añade `apk: window.InTeksApp.version()` si la
  interfaz existe (en navegadores normales no se manda).
- `server.py` `/api/screen-now`: guarda `apk` (cadena, máx. 20 car.) en
  `ahora_pantalla[sid]`; `GET /api/screens` ya lo devuelve dentro de `now`.

### Panel
- En la tarjeta de cada pantalla, junto a «Ahora», una etiqueta «APK 1.0.49».
  Si difiere de la versión del servidor (`/api/info`), sale en ámbar con el
  texto «APK antiguo: 1.0.40 (servidor 1.0.49)». Sin dato (navegador o APK
  anterior a esta versión): nada.

## Fuera de alcance
Actualización automática del APK, avisos por Telegram, historial de conexiones.

## Pruebas
- `tests/test_pantalla_ahora.py` ampliado: `apk` se guarda, se trunca a 20 y
  aparece en `/api/screens`; un envío sin `apk` no rompe nada.
- `tests/apk-version.test.js`: función pura `estadoApk(apk, servidor)` →
  `{texto, aviso}`.
- Android: `./gradlew testDebugUnitTest` con `DiagnosticoTest.kt`.
