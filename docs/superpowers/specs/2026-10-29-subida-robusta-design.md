# Subida robusta de archivos — diseño

Fecha: 2026-10-29. Pieza 1 de 4 de la mejora de Librería y puesta en pantalla.
Todo por IP local: sin nube ni web.

## Piezas del proyecto (orden)

1. **Subida robusta** (este documento).
2. Librería más útil: buscador, filtros, datos de cada archivo, dónde se usa,
   renombrar, vista previa y borrar con aviso.
3. Mandar a pantallas desde la Librería (una o varias).
4. Carpetas y etiquetas.

Cada pieza tiene su diseño, su plan y su versión.

## Problema

`/api/upload` recibe el archivo como base64 dentro de un JSON:

- Un vídeo de 300 MB ocupa ~400 MB en el navegador y otro tanto en el servidor
  (`MAX_BODY_BYTES` carga el cuerpo entero en RAM). En un mini PC puede tumbarlo.
- La barra solo avanza archivo a archivo; un vídeo grande parece colgado.
- `handleUpload` ignora la respuesta: si falla, el panel dice «subido ✓».
- El servidor se fía del `type` que manda el navegador.

## Diseño

### Envío en bruto

`POST /api/upload-raw?name=<nombre>` con el archivo como cuerpo
(`Content-Type: application/octet-stream`, `Content-Length` obligatorio).
Exige sesión de administrador o token API, como el resto de rutas no públicas.

El servidor lee el cuerpo por trozos (1 MB) y lo escribe a
`uploads/<n>_<nombre>.part`; al terminar y validar, lo renombra a su nombre
final. La memoria usada no depende del tamaño del archivo.

Un archivo cortado a mitad (cliente que se desconecta, `Content-Length` no
cumplido) borra su `.part`. Al arrancar se limpian los `.part` huérfanos.

### Comprobaciones (servidor)

- **Tipo por contenido** (primeros bytes): JPG, PNG, GIF, WEBP, MP4/MOV
  (`ftyp`), WEBM (EBML). Cualquier otra cosa se rechaza. El `type` del
  elemento (`image`/`video`) sale de aquí, no del cliente.
- **Tope por archivo:** ajuste `upload_max_mb` en `config.json` (por defecto
  2048), editable en Ajustes.
- **Espacio en disco:** debe quedar libre al menos el tamaño + 500 MB.
- **Nombre:** `os.path.basename`, primer número libre (igual que hoy).
- Rechazo = respuesta con código y mensaje en español que dice el motivo
  («No es una imagen ni un vídeo», «Pasa del máximo de 2048 MB», «No cabe: quedan 3 GB»).
- El elemento se añade al contenido con `contenido_en_edicion()`, como hoy.

El techo de cuerpo `MAX_BODY_BYTES` no se aplica a esta ruta (se lee en
streaming); manda `upload_max_mb`. `/api/upload` (base64) queda igual para
pestañas con un panel antiguo.

### Panel

Función única `subirArchivos(files, {alTerminar})` que usan Librería y
Paquetes. Usa `XMLHttpRequest` (`upload.onprogress`):

- Una fila por archivo con nombre, barra y porcentaje; botón cancelar.
- Se sube de uno en uno. Si uno falla, el resto continúa.
- Al final, resumen: «4 subidos, 1 falló: <motivo>». Solo se dice «subido»
  de lo que el servidor confirmó.
- Cancelar aborta la petición; el servidor limpia el `.part`.

## Fuera de alcance

Subida en trozos reanudable, miniaturas generadas en el servidor, conversión de
formatos, aviso de formatos que la TV no reproduzca (pieza 2 o posterior).

## Pruebas

`tests/test_subida_raw.py`, con servidor real en puerto propio:

1. Subida correcta de PNG y MP4 pequeños → elemento en contenido, tipo correcto.
2. Archivo con extensión `.png` que no es imagen → rechazado, sin archivo.
3. Cuerpo cortado a mitad → sin `.part` ni elemento.
4. Más grande que `upload_max_mb` → rechazado antes de escribir.
5. Sin sesión → 401 sin leer el cuerpo.
6. Archivo de ~200 MB: la memoria del servidor no crece de forma proporcional.
7. `/api/upload` antiguo sigue funcionando.

Prueba de Node para `subirArchivos` (resumen con un fallo, cancelar).
