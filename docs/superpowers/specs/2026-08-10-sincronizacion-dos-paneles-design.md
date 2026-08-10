# Dos paneles, un servidor: que ninguno pise al otro

> Diseño validado el 10 de agosto de 2026. Versión de partida: 1.0.9.

## El problema

Dos ordenadores en la misma red local. Uno hace de servidor y es el que se usa
normalmente; en el otro se consultan y actualizan los tipos de cambio con la
extensión de Chrome.

La sincronización **ya existe** y no hay que construirla: el panel no es un
programa instalado, es una página que sirve `server.py`. Se abre
`http://signage.local/admin.html` desde cualquier equipo de la red, se entra con
la misma contraseña, y los paneles se refrescan solos por SSE. Las sesiones son
tokens HMAC sin estado (`server.py:358-366`), así que dos equipos pueden estar
dentro a la vez indefinidamente sin echarse el uno al otro.

Lo que falta es evitar que un panel con datos rancios pise lo que hizo el otro.

### El fallo concreto que se arregla

`POST /api/fx-update` (`server.py:1737-1795`) avisa a las pantallas una a una:

```python
for sid in updated_screens: notify_screen(sid)
```

`updated_screens` solo contiene IDs de televisores reales. El panel escucha en
`sse_clients["admin"]`, y `admin` nunca está en esa lista porque está
deliberadamente excluido del registro de pantallas (`server.py:1315-1318`).

Consecuencia, paso a paso:

1. El panel está abierto en el PC1.
2. Se actualizan las tasas desde el PC2 con la extensión. Las teles se enteran;
   el panel del PC1 no.
3. Se toca cualquier cosa en ese panel. `saveContentLocal()`
   (`admin.html:3072`) envía su copia entera y caducada de `content`.
4. `server.py:1648-1650` la escribe encima. Las tasas recién subidas desaparecen,
   sin error y sin aviso.

Es el mismo fallo que el comentario de `server.py:1783-1785` intentaba evitar,
pero aquella corrección solo cubrió la divergencia *dentro* de una misma
petición. No cubre un panel abierto con datos viejos.

### El fallo de fondo, que afecta a más sitios

`load_json` y `save_json` (`server.py:914-931`) cierran cada uno su propio
`file_lock`, pero el hueco entre ambos no está protegido:

```python
content = load_json(CONTENT_FILE)   # toma el lock… y lo suelta
content.setdefault("items", []).append(item)
save_json(CONTENT_FILE, content)    # vuelve a tomar el lock
```

Con `ThreadingHTTPServer`, dos peticiones simultáneas leen la misma foto y la
segunda escribe encima de la primera. Mismo patrón en `/api/upload`,
`/api/delete` y `/api/fx-update`.

## Alcance

**Dentro:** que las escrituras de `content.json` no se pisen, y que el panel se
entere de las actualizaciones de tasas.

**Fuera, y por qué:**

- *Guardado granular por entidad* (`/api/items/<id>`, etc.). Correcto de raíz y
  permitiría a dos personas editar en paralelo de verdad, pero es un refactor
  profundo de un `admin.html` de 214 KB con `saveContentLocal()` llamado desde
  doce sitios. Desproporcionado para una persona con dos equipos.
- *Preservar ediciones a medias durante un repintado.* `admin.html:1072` hace
  `es.onmessage=()=>loadAll()`, que reconstruye la interfaz ante cualquier
  aviso y se lleva por delante lo que hubiera a medio escribir. Es un
  comportamiento previo, no introducido aquí. Para que muerda haría falta estar
  tecleando en el PC1 en el mismo instante en que se pulsa la extensión en el
  PC2, y una sola persona no tiene dos pares de manos. Se anota en «Pendiente»
  de `CLAUDE_CODE_PROMPT.md` por si algún día hay dos empleados editando a la
  vez.

## Diseño

Cuatro piezas. Las tres primeras en `server.py`, la cuarta en `admin.html`.

### ① Número de revisión

`content.json` gana una clave de primer nivel, `rev`, un entero que sube en cada
escritura. Es el testigo que permite saber si el panel que guarda tenía la foto
actual o una vieja.

Se elige un contador explícito dentro del propio archivo, y no el `mtime` del
fichero, porque es visible al depurar, viaja en las copias de seguridad y se
puede afirmar en una prueba sin depender de la resolución del reloj del sistema
de archivos.

### ② Un solo punto de escritura

Los ocho `save_json(CONTENT_FILE, …)` repartidos por los manejadores (líneas
1616, 1638, 1651, 1663, 1684, 1793, 1814 y 1890) se sustituyen por un guardián
único:

```python
@contextlib.contextmanager
def contenido_en_edicion():
    """Lee, deja modificar y guarda content.json sin soltar el lock en medio.

    El hueco entre load_json y save_json era la carrera: dos peticiones
    simultáneas (una subida y las tasas de la extensión, por ejemplo) leían la
    misma foto y la segunda escribía encima de la primera.
    """
    with file_lock:
        content = load_json(CONTENT_FILE)
        yield content
        content["rev"] = int(content.get("rev", 0)) + 1
        save_json(CONTENT_FILE, content)
```

Los manejadores quedan sin hueco que aprovechar:

```python
with contenido_en_edicion() as content:
    content.setdefault("items", []).append(item)
```

Esto funciona sin tocar `load_json` ni `save_json` porque `file_lock` ya es un
`threading.RLock()` (`server.py:413`), reentrante: las adquisiciones internas se
vuelven anidamientos inofensivos dentro del mismo hilo. Con un `Lock()` normal
se habría bloqueado a sí mismo y habría hecho falta refactorizar ambas
funciones.

Centralizar el guardado tiene un segundo efecto deseado: ningún camino futuro
puede olvidarse de subir `rev`, porque no hay otra forma de escribir el archivo.

### ③ Comprobación optimista en `POST /api/content`

El panel manda el `rev` con el que cargó. El servidor compara:

| Situación | Respuesta |
|---|---|
| `rev` coincide | `200`, se escribe, `rev` sube |
| `rev` distinto | `409 {"ok":false,"error":"rev_conflict","rev":N}` — no se escribe nada |
| `rev` ausente | `409 {"ok":false,"error":"rev_stale_client"}` |

El tercer caso es deliberado: una pestaña con `admin.html` cacheado de antes de
la actualización no puede colarse por la puerta de atrás saltándose la
comprobación. Al recibir ese 409 el panel hace `location.reload()` y se cura
solo.

El conflicto no es una avería, así que sale por `jresp(409, …)` y no por `err()`
(que devuelve 500). Es el mismo camino que ya usa `/api/login` en
`server.py:1490` para «todavía no hay contraseña». Se registra en el log, porque
un 409 recurrente es la pista de que el SSE del panel no está llegando:

```python
log(f"  [contenido] guardado rechazado: el panel traia rev {enviado}, en disco hay {actual}")
```

### ④ El aviso que falta

En `server.py:1794`, tras el bucle de notificación por pantalla:

```python
notify_screen("admin")
```

Una línea. El resto de endpoints ya avisan bien al panel sin saberlo: usan
`notify_all()`, que recorre `sse_clients.keys()` e incluye `"admin"` cuando hay
un panel conectado. `fx-update` es el único que notifica pantalla por pantalla,
y por eso es el único que deja al panel fuera.

### Manejo del conflicto en el panel

`saveContentLocal()` pasa de ignorar la respuesta a mirarla:

```js
async function saveContentLocal(){
  const r = await fetch("/api/content",{method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(content)});

  if(r.status === 409){
    const d = await r.json().catch(()=>({}));
    // Panel cacheado de una versión anterior: recargar trae el nuevo admin.html
    if(d.error === "rev_stale_client"){ location.reload(); return; }
    toast("Otro equipo cambió algo. Recargado — repite lo último que hiciste.", true);
    await loadAll();
    return;
  }
  if(!r.ok){ toast("No se pudo guardar.", true); return; }
}
```

El cuerpo del POST no cambia: el panel ya envía `content` entero, y `rev` vive
dentro porque `GET /api/content` devuelve el archivo completo. Solo hay que
dejar que viaje y no estorbarlo.

Se reutiliza `toast(msg, isErr)` (`admin.html:3085`), que ya existe. No hace
falta ningún estilo nuevo.

**Qué se pierde en un 409:** la última acción. Si se añadió una imagen justo
cuando el otro equipo escribía, esa imagen no se guarda y hay que volver a
añadirla. Es la contrapartida deliberada — perder la propia última acción y
enterarse, en vez de destruir en silencio el trabajo del otro equipo. Por eso el
mensaje dice «repite lo último que hiciste» y no un «error al guardar» que no
orienta a nadie.

### Restaurar una copia de seguridad

`restaurar_backup` trae el `content.json` de otra instalación con su propio
`rev`. Si por casualidad coincidiera con el que tiene un panel abierto, ese
panel podría escribir encima de lo recién restaurado creyéndose al día.

Se cierra fijando, al restaurar, `rev = max(local, restaurado) + 1`. Garantiza
que el contador solo crece y que ningún panel abierto de antes de la
restauración pueda tener un `rev` válido.

## Flujo resultante

```
PC2: extensión Chrome → POST /api/fx-update
        │
        ├─► content.json: tasas fusionadas, rev 41 → 42
        ├─► notify_screen(tele-1) … ─► las teles repintan     (ya funcionaba)
        └─► notify_screen("admin") ─► PC1 hace loadAll()      (④ nuevo)
                                        └─► su content y su rev quedan al día

PC1: se añade una imagen → POST /api/content {…, rev: 42}  ✅ coincide → 200
```

Si el SSE estaba caído o el aviso se perdió, PC1 mandaría `rev: 41`, el servidor
devolvería 409 y las tasas sobrevivirían. La pieza ④ hace que el caso normal
funcione; la ③ es la red debajo del trapecio, para cuando ④ falla.

## Pruebas

Se sigue el patrón de `tests/test_fx_update.py`: levantar un servidor real en un
directorio temporal y hablarle por HTTP. Estos fallos viven en la concurrencia
de `ThreadingHTTPServer` y un simulacro no los reproduce.

**`tests/test_concurrencia.py`** (nuevo):

| # | Qué comprueba | Por qué importa |
|---|---|---|
| 1 | `rev` sube en `/api/content`, `/api/upload`, `/api/delete`, `/api/fx-update` | Si un camino se olvida de subirlo, la protección tiene un agujero justo por ahí |
| 2 | Guardar con el `rev` correcto → `200` | Que el caso normal no se rompa |
| 3 | Guardar con un `rev` viejo → `409` y `content.json` intacto | El núcleo: es el escenario de las tasas |
| 4 | Guardar sin `rev` → `409 rev_stale_client` | La pestaña cacheada de una versión anterior |
| 5 | `fx-update` emite `update:admin` por SSE | La pieza ④. Se abre `/api/events?screen=admin` en un hilo y se lee el stream |
| 6 | 20 hilos mezclando subidas y `fx-update`: al final están todos los items | La prueba que justifica ②. Hoy falla; con el guardián pasa |

La 6 conviene escribirla **antes** del arreglo y verla fallar: es la única que
demuestra que el hueco entre `load_json` y `save_json` era un fallo real y no
una preocupación teórica.

**Extensión de `tests/test_backup.py`:** restaurar deja un `rev` mayor que el
que había, tanto si la copia traía uno más alto como más bajo.

**`tests/concurrencia-panel.test.js`** (nuevo): el manejo del 409 en
`saveContentLocal`, extrayendo la función de `admin.html` y ejecutándola en un
`vm` con `fetch` falso — el patrón que `CLAUDE_CODE_PROMPT.md` describe para
`schedule.test.js`. Es la prueba más cara del lote en relación a lo que aporta,
porque hay que fingir `fetch`, `toast`, `loadAll` y `location`. Si hubiera que
recortar, es la primera que se quita: el resto cubre el servidor, que es donde
vive el riesgo de perder datos.

**Verificación manual**, que ninguna prueba automática cubre: con el panel
abierto en el PC1 y las tasas actualizadas desde el PC2, comprobar que el PC1 se
refresca solo. Repetirlo después con el cable de red del PC1 desenchufado unos
segundos, para forzar el camino del 409.

`npm test` solo ejecuta los `.test.js`. Las pruebas de Python se lanzan sueltas
(`python tests/test_concurrencia.py`), como el resto de las suites de servidor.

## Documentación

- **`MANUAL.md`** — apartado nuevo, «Usar el panel desde otro ordenador»: la
  regla de firewall (que el instalador no crea, ya anotado como *gotcha*
  conocido), la URL `http://signage.local/admin.html`, y el campo *Servidor* de
  la extensión.
- **`CHANGELOG.md`** — entrada 1.0.10, en el registro «en cristiano» del resto.
- **`CLAUDE_CODE_PROMPT.md`** — `rev` en la tabla de datos en disco, y el punto
  aplazado (preservar ediciones a medias durante un repintado) en «Pendiente».

## Restricciones respetadas

Sin dependencias nuevas (`contextlib` es librería estándar), sin frameworks JS,
sin paso de build, y sigue funcionando sin internet.
