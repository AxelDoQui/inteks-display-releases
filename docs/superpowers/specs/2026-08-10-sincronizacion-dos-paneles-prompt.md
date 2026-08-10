# Prompt de implementación: dos paneles, un servidor

> Traspaso para una sesión nueva. El diseño validado está en
> `docs/superpowers/specs/2026-08-10-sincronizacion-dos-paneles-design.md` —
> léelo entero antes de tocar nada. Este documento es el plan de ejecución.
>
> Versión de partida: 1.0.9. Versión de salida: 1.0.10.

---

## Contexto y restricciones no negociables

Esto es InTeks Display (SignalOS): carteleria digital que corre en tiendas, sin
internet garantizado y sin nadie técnico delante.

- **Python de librería estándar pura.** `contextlib` vale porque viene en la
  caja. Nada de `pip install`.
- **Sin frameworks JS, sin paso de build, sin bundler.** `admin.html` es un
  archivo de 214 KB con el JS dentro. Se edita a mano.
- **Tiene que seguir funcionando sin internet.** Ninguna dependencia de CDN.
- **Sin dependencias nuevas de ningún tipo.**

### Aviso sobre los números de línea

Todos los números de línea de este documento se tomaron con el árbol en
`7bf854b`. **Se moverán en cuanto insertes el guardián ②**, que añade ~14 líneas
por encima de casi todos los demás puntos de cambio. Úsalos para orientarte y
localiza el código por su contenido, no por su número. Verifica antes de editar.

### El árbol de trabajo está sucio

Hay 14 archivos modificados y 3 pruebas sin seguir, todo de trabajo a medias de
la 1.0.9 (extensión, player, instalador). **No mezcles estos cambios con
aquello.** Mira `git status` antes de empezar y decide con el usuario si commitear
lo pendiente, guardarlo en `stash` o trabajar en una rama aparte.

---

## El problema

Dos ordenadores en la misma red. Uno hace de servidor y es el que se usa a
diario; desde el otro se actualizan los tipos de cambio con la extensión de
Chrome.

La sincronización **ya existe y no hay que construirla**: el panel es una página
que sirve `server.py`, las sesiones son tokens HMAC sin estado y los paneles se
refrescan por SSE. Lo que falta es evitar que un panel con datos rancios pise lo
que hizo el otro.

Son dos fallos distintos, y hacen falta los dos arreglos.

### Fallo A — el panel nunca se entera de las tasas

`POST /api/fx-update` avisa a las pantallas una a una (`server.py:1794`):

```python
for sid in updated_screens: notify_screen(sid)
```

`updated_screens` solo trae IDs de televisores reales. El panel escucha en
`sse_clients["admin"]`, y `"admin"` **nunca** está en esa lista porque está
deliberadamente excluido del registro de pantallas (`server.py:1315-1318`).

Cadena causal completa:

1. El panel está abierto en el PC1.
2. Se actualizan las tasas desde el PC2. Las teles se enteran; el panel no.
3. Se toca cualquier cosa en ese panel. `saveContentLocal()` (`admin.html:3072`)
   envía su copia **entera y caducada** de `content`.
4. `server.py:1651` la escribe encima. Las tasas recién subidas desaparecen, sin
   error y sin aviso.

Es el mismo fallo que el comentario de `server.py:1783-1785` intentaba evitar,
pero aquella corrección solo cubrió la divergencia *dentro* de una misma
petición.

### Fallo B — el hueco entre leer y escribir

`load_json` (`server.py:914`) y `save_json` (`server.py:920`) cierran cada uno su
propio `file_lock`, pero el hueco entre ambos está desprotegido:

```python
content = load_json(CONTENT_FILE)   # toma el lock… y lo suelta
content.setdefault("items", []).append(item)
save_json(CONTENT_FILE, content)    # vuelve a tomar el lock
```

Con `ThreadingHTTPServer`, dos peticiones simultáneas leen la misma foto y la
segunda escribe encima de la primera. Mismo patrón en `/api/upload`,
`/api/delete` y `/api/fx-update`.

---

## Las seis piezas

Cuatro en `server.py`, una en `admin.html`, una en `restaurar_backup`.

### ① `rev` en `content.json`, con migración obligatoria

`content.json` gana una clave de primer nivel, `rev`: un entero que sube en cada
escritura. Es el testigo que permite saber si el panel que guarda tenía la foto
actual.

Se elige un contador explícito dentro del archivo, y no el `mtime`, porque es
visible al depurar, viaja en las copias de seguridad y se puede afirmar en una
prueba sin depender de la resolución del reloj del sistema de archivos.

**Dos cambios:**

En `server.py:406`, que los archivos nuevos nazcan con el contador:

```python
init_file(CONTENT_FILE, {"items": [], "screens": {}, "rev": 0})
```

Y la migración, junto a `_limpiar_pantalla_fantasma()` (`server.py:933`), que
existe precisamente para esto — arreglar al arrancar los archivos que vienen de
una versión anterior:

```python
def _migrar_rev():
    """Un content.json de 1.0.9 no tiene rev. Sin esto, la comprobación ③ deja
    el panel en bucle: carga sin rev, guarda sin rev, recibe 409
    rev_stale_client, recarga, y vuelve a empezar."""
    with file_lock:
        content = load_json(CONTENT_FILE)
        if "rev" not in content:
            content["rev"] = 0
            save_json(CONTENT_FILE, content)
            log("  [contenido] migrado: se anade rev 0 (venia de una version anterior)")
```

> **Esta pieza no es opcional y no se puede aplazar.** Sin ella, la ③ deja el
> panel inutilizable **en toda instalación que se actualice desde 1.0.9** — que
> son todas. Este fallo no estaba en el primer diseño; salió en la
> auto-revisión. Si vas con prisa y recortas algo, que no sea esto.

### ② Un solo punto de escritura

Los ocho `save_json(CONTENT_FILE, …)` repartidos por los manejadores (líneas
**1616, 1638, 1651, 1663, 1684, 1793, 1814 y 1890**) se sustituyen por un
guardián único. Ponlo cerca de `load_json`/`save_json`:

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

Funciona **sin tocar `load_json` ni `save_json`** porque `file_lock` ya es un
`threading.RLock()` (`server.py:413`), reentrante: las adquisiciones internas se
vuelven anidamientos inofensivos dentro del mismo hilo. Con un `Lock()` normal se
habría bloqueado a sí mismo.

Centralizar tiene un segundo efecto deseado: ningún camino futuro puede olvidarse
de subir `rev`, porque no hay otra forma de escribir el archivo.

> **Cuidado con el sitio número cinco.** Siete de los ocho `save_json` son
> incondicionales, pero el de **`server.py:1684`** (`/api/screens/delete`) está
> dentro de un `if sid in content.get("screens", {})`. Si envuelves ese bloque
> entero con el guardián, `rev` sube también cuando el borrado no borra nada:
> invalidas a todos los paneles abiertos y provocas un 409 espurio en su
> siguiente guardado. Decide conscientemente — entrar al guardián solo cuando
> vayas a mutar de verdad, o aceptar el `rev` de más — pero no lo envuelvas en
> automático junto a los otros siete.
>
> Comprueba además que ningún bloque tenga un `return` temprano dentro del
> `with`: al salir por `return`, el gestor **sí** ejecuta el guardado.

Los `try/except Exception as e: err(e)` que ya envuelven cada manejador siguen
sirviendo: si el cuerpo del `with` lanza, la excepción atraviesa el `yield` y
**no se guarda nada**. Es el comportamiento que queremos.

### ③ Comprobación optimista en `POST /api/content`

En `server.py:1644`. El panel manda el `rev` con el que cargó; el servidor
compara:

| Situación | Respuesta |
|---|---|
| `rev` coincide | `200`, se escribe, `rev` sube |
| `rev` distinto | `409 {"ok":false,"error":"rev_conflict","rev":N}` — no se escribe nada |
| `rev` ausente | `409 {"ok":false,"error":"rev_stale_client"}` |

El tercer caso es deliberado: una pestaña con `admin.html` cacheado de antes de
la actualización no puede colarse por la puerta de atrás saltándose la
comprobación. Al recibir ese 409 el panel hace `location.reload()` y se cura
solo.

El conflicto **no es una avería**, así que sale por `jresp(409, …)`
(`server.py:1481`) y no por `err()` (`server.py:1478`, que devuelve 500). Es el
mismo camino que ya usa `/api/login` para «todavía no hay contraseña». Regístralo
en el log, porque un 409 recurrente es la pista de que el SSE del panel no está
llegando:

```python
log(f"  [contenido] guardado rechazado: el panel traia rev {enviado}, en disco hay {actual}")
```

**La comprobación es solo de `POST /api/content`.** `/api/fx-update` viene de la
extensión, que no maneja `rev`, y no debe quedar sujeta a ella.

### ④ El aviso que falta

En `server.py:1794`, justo tras el bucle de notificación por pantalla:

```python
notify_screen("admin")
```

Una línea. El resto de endpoints ya avisan bien al panel sin saberlo: usan
`notify_all()` (`server.py:426`), que recorre `sse_clients.keys()` e incluye
`"admin"` cuando hay un panel conectado. `fx-update` es el único que notifica
pantalla por pantalla, y por eso es el único que deja al panel fuera.

### ⑤ Manejo del conflicto en el panel

`saveContentLocal()` (`admin.html:3072`) pasa de ignorar la respuesta a mirarla:

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

El cuerpo del POST **no cambia**: el panel ya envía `content` entero, y `rev` vive
dentro porque `GET /api/content` (`server.py:1211`) devuelve el archivo completo.
Solo hay que dejar que viaje y no estorbarlo.

Se reutiliza `toast(msg, isErr)` (`admin.html:3085`) y `loadAll()`
(`admin.html:1057`), que ya existen. **No hace falta ningún estilo nuevo.**

> **No suavices el mensaje.** «Repite lo último que hiciste» orienta; «error al
> guardar» no. En un 409 se pierde la última acción — si añadiste una imagen justo
> cuando el otro equipo escribía, esa imagen no se guarda y hay que volver a
> añadirla. Es la contrapartida deliberada: perder la propia última acción y
> enterarse, en vez de destruir en silencio el trabajo del otro equipo. El
> mensaje tiene que decir exactamente eso.

### ⑥ Restaurar una copia de seguridad

`restaurar_backup` (`server.py:551`) trae el `content.json` de otra instalación
con su propio `rev`. Si coincidiera con el de un panel abierto, ese panel podría
escribir encima de lo recién restaurado creyéndose al día.

Al restaurar, fija `rev = max(local, restaurado) + 1`. Garantiza que el contador
solo crece y que ningún panel abierto de antes de la restauración pueda tener un
`rev` válido.

---

## Pruebas

Patrón del proyecto para servidor (`tests/test_fx_update.py`): levantar un
servidor **real** en un directorio temporal y hablarle por HTTP. Estos fallos
viven en la concurrencia de `ThreadingHTTPServer` y un simulacro no los
reproduce.

El arranque del temporal, copiado de ese archivo:

```python
PORT = 8107   # libre: los demás usan 8086, 8090, 8093, 8097-8101, 8103-8106
TOKEN = "token-de-pruebas-0123456789"

# admin.json con el token, o el servidor no te deja pasar
json.dump({"api_token": TOKEN, "secret": "s" * 64}, open(.../"admin.json", "w"))

# Toda petición autenticada lleva la cabecera:
headers={"Content-Type": "application/json", "X-SignalOS-Token": TOKEN}
```

La cabecera es **`X-SignalOS-Token`** (`server.py:1132`). Sin ella no pasas la
puerta de control.

### `tests/test_concurrencia.py` (nuevo)

| # | Qué comprueba | Por qué importa |
|---|---|---|
| 1 | `rev` sube en `/api/content`, `/api/upload`, `/api/delete`, `/api/fx-update` | Si un camino se olvida de subirlo, la protección tiene un agujero justo por ahí |
| 2 | Guardar con el `rev` correcto → `200` | Que el caso normal no se rompa |
| 3 | Guardar con un `rev` viejo → `409` y `content.json` intacto | El núcleo: es el escenario de las tasas |
| 4 | Guardar sin `rev` → `409 rev_stale_client` | La pestaña cacheada de una versión anterior |
| 5 | `fx-update` emite `update:admin` por SSE | La pieza ④. Abre `/api/events?screen=admin` en un hilo y lee el stream |
| 6 | 20 hilos mezclando subidas y `fx-update`: al final están **todos** los items | La prueba que justifica ② |
| 7 | Arrancar sobre un `content.json` de 1.0.9 (sin `rev`): el `GET` ya devuelve `rev` y el primer guardado da `200` | La migración ① |

> **La prueba 6 hay que verla fallar primero.** Escríbela **antes** de tocar los
> manejadores y ejecútala contra el código actual: tiene que fallar. Si pasa
> antes de existir `contenido_en_edicion()`, está mal escrita — no hay
> suficientes hilos, o no hay solapamiento real, o no comprueba lo que cree.
> Una prueba de concurrencia que pasa contra el código roto no demuestra nada, y
> es facilísimo escribir una así sin darse cuenta. Es la única que demuestra que
> el hueco entre `load_json` y `save_json` era un fallo real y no una
> preocupación teórica.

### `tests/test_backup.py` (extender)

Restaurar deja un `rev` mayor que el que había, **tanto si la copia traía uno más
alto como más bajo**. Los dos casos, o la pieza ⑥ queda medio probada.

### `tests/concurrencia-panel.test.js` (nuevo)

El manejo del 409 en `saveContentLocal`: extraer la función de `admin.html` y
ejecutarla en un `vm` con `fetch` falso — el patrón que `CLAUDE_CODE_PROMPT.md`
describe para `schedule.test.js`.

Es la prueba más cara del lote en relación a lo que aporta, porque hay que fingir
`fetch`, `toast`, `loadAll` y `location`. **Si hay que recortar algo, es la
primera que se quita**: el resto cubre el servidor, que es donde vive el riesgo
de perder datos.

### Cómo se ejecutan

```
npm test                            # solo los .test.js
python tests/test_concurrencia.py   # las de servidor van sueltas
python tests/test_backup.py
```

### Verificación manual (ninguna prueba automática la cubre)

Con el panel abierto en el PC1 y las tasas actualizadas desde el PC2, comprobar
que el PC1 **se refresca solo**. Repetirlo después con el cable de red del PC1
desenchufado unos segundos, para forzar el camino del 409.

---

## Documentación y versión

- **`MANUAL.md`** — apartado nuevo, «Usar el panel desde otro ordenador»: la
  regla de firewall (que el instalador no crea, ya anotado como *gotcha*
  conocido), la URL `http://signage.local/admin.html`, y el campo *Servidor* de
  la extensión.
- **`CHANGELOG.md`** — entrada 1.0.10, en el registro «en cristiano» del resto.
- **`CLAUDE_CODE_PROMPT.md`** — `rev` en la tabla de datos en disco, y el punto
  aplazado (preservar ediciones a medias durante un repintado) en «Pendiente».

### Subir la versión: 1.0.9 → 1.0.10

**Hay un script. Úsalo, no edites a mano:**

```
powershell -ExecutionPolicy Bypass -File tools\subir-version.ps1 1.0.10
```

Cambia de una vez las cuatro ediciones que viven en tres archivos que no se
hablan entre sí: `server.py` (`APP_VERSION`), `installer/setup.iss` (dos veces —
`AppVersion` y `OutputBaseFilename`) y `package.json`. `tests/version-sync.test.js`
vigila que coincidan; el script existe para que nunca lleguen a discrepar.

**Súbela antes de compilar el instalador, sin excepciones.** Ya pasó una vez que
en un solo día salieron cinco builds llamados 1.0.0 y no había forma de saber
cuál tenía instalado cada equipo.

---

## Fuera de alcance

No lo implementes. Está descartado con motivo, y el motivo va aquí para que no
haya que volver a discutirlo:

- **Guardado granular por entidad** (`/api/items/<id>`, etc.). Correcto de raíz y
  permitiría a dos personas editar en paralelo de verdad, pero es un refactor
  profundo de un `admin.html` de 214 KB con `saveContentLocal()` llamado desde
  doce sitios. Desproporcionado para una persona con dos equipos.
- **Preservar ediciones a medias durante un repintado.** `admin.html:1072` hace
  `es.onmessage=()=>loadAll()`, que reconstruye la interfaz ante cualquier aviso
  y se lleva por delante lo que hubiera a medio escribir. Es un comportamiento
  **previo**, no introducido aquí. Para que muerda haría falta estar tecleando en
  el PC1 en el mismo instante en que se pulsa la extensión en el PC2, y una sola
  persona no tiene dos pares de manos. Se anota en «Pendiente» de
  `CLAUDE_CODE_PROMPT.md` por si algún día hay dos empleados editando a la vez.

---

## Aceptación

- [ ] `python tests/test_concurrencia.py` — las 7 pasan.
- [ ] La prueba 6 **se vio fallar** contra el código sin `contenido_en_edicion()`,
      y pasa después. (Si nunca falló, no vale.)
- [ ] `python tests/test_backup.py` pasa, con los dos casos de `rev` de ⑥.
- [ ] `npm test` pasa, incluido `version-sync.test.js`.
- [ ] Migración verificada a mano: arrancar sobre un `content.json` sin `rev`,
      abrir el panel, guardar → `200`, **sin bucle de recargas**.
- [ ] No queda ningún `save_json(CONTENT_FILE, …)` fuera de
      `contenido_en_edicion()`. Compruébalo con
      `grep -n "save_json(CONTENT_FILE" server.py` — solo debe salir el de dentro
      del guardián.
- [ ] Verificación manual de los dos equipos, incluido el caso del cable
      desenchufado.
- [ ] Versión 1.0.10 en los cuatro sitios, y `MANUAL.md`, `CHANGELOG.md` y
      `CLAUDE_CODE_PROMPT.md` actualizados.
