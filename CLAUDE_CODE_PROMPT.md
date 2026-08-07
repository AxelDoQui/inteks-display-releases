# SignalOS Pro — Contexto para Claude Code

## Qué es este proyecto

SignalOS Pro es un sistema de digital signage (cartelería digital) para Windows.
Permite gestionar varias pantallas/tablets desde un portátil central por WiFi local.
El objetivo es distribuirlo como producto a empresas (tiendas, restaurantes, casas de cambio, etc).

## Stack actual

- `server.py` — servidor HTTP en Python puro (sin dependencias externas). Gestiona:
  - Playlists por pantalla
  - Subida y almacenamiento de archivos (imágenes, vídeos)
  - SSE (Server-Sent Events) para actualizaciones en tiempo real
  - Configuración de pantallas (modo independiente, videowall, vertical)
  - Endpoints: /api/content, /api/screens, /api/playlist, /api/upload, /api/delete, /api/screens/config, /api/events

- `admin.html` — panel de administración (HTML/CSS/JS puro, sin frameworks). Módulos:
  - Pantallas: gestión de pantallas conectadas, playlists, videowall, modo vertical
  - Librería: subida de imágenes y vídeos
  - Divisas: tabla de tipos de cambio con OCR (Tesseract.js) y pegado de texto
  - Clima: búsqueda de ciudad con Open-Meteo (gratis, sin API key), actualización en tiempo real
  - Noticias/ticker: titulares con animación
  - Texto/precios: diapositivas de texto con colores personalizables
  - URLs web: mostrar páginas web en iframe

- `player.html` — reproductor para tablets/pantallas (HTML/CSS/JS puro). Características:
  - Se identifica con ?screen=NOMBRE en la URL
  - Soporte vertical con ?vertical=1
  - Módulos: imagen, vídeo, texto, URL iframe, divisas, clima (live), noticias ticker
  - Pantalla de espera mostrando el ID de pantalla
  - SSE para actualizaciones en tiempo real sin recargar
  - Barra de progreso, transiciones suaves
  - Actualización automática del clima cada 15 minutos

## Arquitectura de datos

- `playlist.json` / `content.json` — persistencia local en JSON
- `screens.json` — registro de pantallas conectadas
- `uploads/` — carpeta con archivos subidos

## Roadmap completo a implementar

### FASE 1 — Electron + Instalador
1. `main.js` — app Electron que:
   - Arranca `server.py` como proceso hijo embebido
   - Icono en bandeja del sistema (tray) con menú:
     · Abrir admin
     · Abrir player (pantalla1)
     · Reiniciar servidor
     · Salir
   - Ventana principal con el admin cargado
   - Autoarranque con Windows (opcional, configurable)

2. `package.json` con electron y electron-packager

3. `installer/setup.iss` — script Inno Setup para generar el .exe instalable:
   - Nombre: SignalOS Pro
   - Instala en C:\Program Files\SignalOS
   - Crea acceso directo en escritorio y menú inicio
   - Opción de autoarranque con Windows durante la instalación
   - Desinstalador incluido

### FASE 2 — Configuración de puerto
4. `config.json` — archivo de configuración persistente:
   ```json
   {
     "port": 8080,
     "port_fallback": 8081,
     "installation_name": "SignalOS Pro",
     "autostart": false,
     "first_run": true
   }
   ```

5. Pantalla de primer arranque (first_run):
   - Formulario para definir puerto principal y alternativo
   - Nombre de la instalación
   - El sistema prueba el puerto — si está ocupado prueba el alternativo
   - Si ambos ocupados, muestra aviso y pide otro
   - Guarda config.json y arranca

6. Sección "Ajustes" en admin.html:
   - Ver puerto actual en uso
   - Cambiar puerto principal y alternativo
   - Cambiar nombre de instalación
   - Toggle autoarranque con Windows
   - Botón "Reiniciar servidor" aplicando cambios

7. server.py actualizado para:
   - Leer puerto desde config.json
   - Detectar automáticamente puerto libre si el principal está ocupado
   - Aceptar argumento --port como override

### FASE 3 — Módulos nuevos en admin.html + player.html

8. Módulo Comparativa de productos:
   - Dos columnas lado a lado
   - Cada columna: imagen, nombre, precio, lista de características
   - Badge opcional "Mejor precio" / "Más vendido" / "Oferta"
   - Fondo y colores personalizables
   - Vista previa en tiempo real

9. Módulo Cuenta atrás:
   - Temporizador con fecha/hora de fin configurable
   - Mensaje superior e inferior personalizables
   - Cuando llega a cero muestra mensaje de fin
   - Colores y fondo personalizables

10. Módulo QR:
    - Input de URL
    - Genera QR grande usando qrcode.js (sin internet)
    - Texto debajo del QR personalizable
    - Fondo y colores personalizables

11. Módulo Ficha de producto:
    - Imagen grande del producto
    - Nombre, precio, precio anterior tachado opcional
    - Lista de especificaciones técnicas
    - Badge de oferta/nuevo/destacado
    - Fondo y colores personalizables

### FASE 4 — Programación horaria por pantalla

12. En cada tarjeta de pantalla en admin.html:
    - Botón "🕐 Horario"
    - Editor visual por días de la semana
    - Cada día: activar/desactivar + hora inicio + hora fin
    - Imagen de standby cuando la pantalla está fuera de horario (opcional)
    - Modo festivos: fechas concretas con horario diferente

13. player.html actualizado:
    - Comprueba horario cada minuto
    - Dentro de horario: reproduce con normalidad
    - Fuera de horario: pantalla negra o imagen de standby configurada
    - Sin necesidad de recargar la página

## Restricciones importantes

- Sin frameworks JS (no React, no Vue) — HTML/CSS/JS puro en los .html
- Sin dependencias Python externas — solo librería estándar
- Funciona sin internet (excepto clima y noticias que lo requieren explícitamente)
- Compatible con Windows 10 y Windows 11
- Las tablets solo necesitan un navegador (Chrome/Edge/Safari) — sin instalación

## Estilo visual del admin

- Fondo oscuro: #0c0c0e
- Superficie: #141418, #1c1c22
- Bordes: #2e2e3a
- Acento principal: #c8f040 (verde lima)
- Acento 2: #40f0d0 (cian)
- Acento 3: #f07040 (naranja)
- Acento 4: #a07ff0 (morado)
- Fuentes: Space Mono (monospace, títulos), DM Sans (cuerpo)

## Cómo arrancar en desarrollo

```cmd
python server.py
# Admin: http://localhost:8080/admin.html
# Player: http://localhost:8080/player.html?screen=pantalla1
```
