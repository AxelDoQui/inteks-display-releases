# Cambios de InTeks Display

Qué cambió en cada versión, en cristiano. Sirve para dos cosas: saber qué tiene
instalada cada tienda cuando algo falla, y tener el texto listo si algún día se
enciende el aviso de versión nueva (`update_url` en `config.json`).

Para subir de versión: `powershell -File tools\subir-version.ps1 1.0.2`

---

## 1.0.2 — 2026-08-09

### Nuevo

- **Avisos al móvil por Telegram**: pantalla caída dentro de su horario,
  pantalla que vuelve, y tablero de divisas sin actualizar. Se configura en
  Ajustes y hay un botón para mandarse un mensaje de prueba. Cada aviso se
  manda una sola vez.
- **Vigencia por fechas**: cada contenido de una playlist puede tener fecha de
  inicio y de fin, y entra y sale solo. Si todo caduca, se sigue mostrando lo
  último antes que dejar el escaparate en negro.
- **Duplicar una pantalla** con toda su configuración, para montar la segunda
  caja sin rehacer nada.
- **Aviso de disco casi lleno** en Ajustes.

### Corregido

- Guardar los ajustes **borraba el resto de `config.json`**: el nombre mDNS, la
  dirección de actualizaciones y, a partir de ahora, el token de avisos. Y
  enviar algo que no fuera un objeto escribía basura en el archivo y se llevaba
  la configuración entera.

---

## 1.0.1 — 2026-08-09

Primera versión con el intérprete de Python incluido. **El equipo de destino ya
no necesita tener Python instalado.**

### Nuevo

- **Copia de seguridad y restauración** (Ajustes). Se lleva pantallas,
  playlists, paquetes y archivos subidos. No incluye la contraseña ni el token
  de la extensión, así que el archivo se puede guardar en un pendrive sin riesgo.
- **Transiciones entre pases**: fundido, deslizar, zoom o corte seco, una por
  pantalla, con duración ajustable. En Playlist de cada pantalla.
- **Modo festivos**: fechas concretas que mandan sobre el horario del día de la
  semana, para cerrar en Navidad o abrir un domingo de rebajas.
- **Recuperar la contraseña** del panel con `restablecer-contrasena.bat`, desde
  el propio ordenador. No hay recuperación por la red a propósito.
- **Las pantallas guardan sus imágenes y vídeos** en el propio televisor, así
  que un arranque con el servidor apagado ya no deja el escaparate vacío.
- **Desenlazar una pantalla** desde el panel, y **copiar su enlace directo**.
- La **versión instalada** se ve en Ajustes.

### Corregido

- El tablero de divisas mostraba **la fecha de hoy** aunque las tasas fueran de
  hace tres días. Ahora muestra la fecha de las tasas y avisa cuando caducan.
- Al **editar un paquete**, las pantallas que lo usaban no se enteraban. Ahora
  se actualizan solas.
- Una pantalla que se apagaba y encendía podía **perder su enlace** sin forma de
  devolvérselo. Ahora se reenlaza desde el panel conservando su configuración.
- El **panel aparecía en su propia lista** como una pantalla llamada «admin».
- Un día del horario con «abierto» y sin horas dejaba la pantalla **apagada las
  24 horas**.
- El **instalador se pisaba a sí mismo** al actualizar: copiaba archivos con el
  servidor todavía en marcha.
- `server.log` crecía sin límite.
- El cuerpo de las peticiones se leía entero en memoria sin ningún techo.

### Por dentro

- Se abandona la vía Electron: fuera el build de 354 MB, las fuentes y las
  dependencias de npm. El proyecto ya no tiene ninguna.
- 152 pruebas de lógica y 8 suites de servidor.

---

## 1.0.0

Primera versión: pantallas, playlists, paquetes, módulo de divisas con la
extensión de Chrome, horarios, videowall y emparejamiento por código.
