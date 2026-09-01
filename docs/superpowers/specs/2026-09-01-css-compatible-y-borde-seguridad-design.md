# El player en navegadores viejos, y el borde de seguridad

> 2026-09-01. Sale de un aviso de campo: «a veces el contenido no se ve como
> debe». Diagnóstico medido, no supuesto.

## El problema

Axel reportó que el contenido «se sale o no cabe» y que «depende del
televisor». No es sobrebarrido: es **CSS que el navegador de la caja no
entiende**.

La caja MXQ carga `com.android.chrome` **62** (de 2017) como proveedor de
WebView — no el `com.google.android.webview` 119 que tiene instalado. En CSS,
una declaración con propiedad desconocida o valor inválido **se descarta
entera y en silencio**. El `<style>` de `player.html` tiene **58 declaraciones**
que Chrome 62 tira:

| Sintaxis | Desde | Usos |
|---|---|---|
| `clamp()` | Chrome 79 | 38 |
| `gap` (flex y grid) | Chrome 84 | 8 |
| `min()` / `max()` | Chrome 79 | 7 |
| `aspect-ratio` | Chrome 88 | 3 |
| `inset` | Chrome 87 | 2 |

### La medida

Se renderizó el mismo tablero de divisas a 1280×720 dos veces: con
`player.html` y con una copia a la que se le quitaron exactamente esas 58
declaraciones. Arnés: servidor estático + `player.html?preview=1` en un iframe
del tamaño exacto + Chrome headless con `--dump-dom`.

| Medida | Navegador moderno | Chrome 62 |
|---|---|---|
| `.slide` | 1280×720 | **1116×106** |
| ¿llena la pantalla? | sí | **no** |
| filas de divisas | 656 px en 656 | **300 px en un hueco de 23** |
| letra del título | 24,5 px | **16 px** |
| letra de la tasa | 44,4 px | **16 px** |

**La causa estructural es una sola línea:** `.slide{position:absolute;inset:0}`.
Sin `inset`, un elemento absoluto no tiene a qué agarrarse y se encoge al
tamaño de su contenido. Todo lo demás —letras a 16 px, filas desbordando— es
consecuencia de que el contenedor ya no mide lo que el resto del CSS supone.

**Por qué no se vio antes:** la previa del admin corre en el navegador del
usuario, que es moderno. Lo que el panel enseña **no es lo que pinta la caja**.

### Por qué el borde de seguridad no era el arreglo

Fue lo que se pidió, y es una función legítima —hay televisores que recortan
un 3-5 % por sobrebarrido—, pero **no toca esta causa**: un margen quita sitio
a un contenido al que ya le falta. Se hace igualmente, apagado por defecto, y
se decide por pantalla.

## Parte 1 — Respaldos de CSS

**Regla única:** no se quita ninguna declaración moderna. Se le pone delante la
equivalente que un navegador viejo entiende; el moderno la pisa por orden de
cascada. Ninguna pantalla que hoy se ve bien cambia.

| Hoy | Queda |
|---|---|
| `inset:0` | los cuatro longhands — y **es el mismo sitio donde entra el borde de seguridad**, ver Parte 2 |
| `font-size:clamp(28px,6vw,96px)` | `font-size:6vw;font-size:clamp(28px,6vw,96px)` |
| `aspect-ratio:3/2` | alto explícito delante |
| `gap:X` | margen en los hijos donde el hueco sea estructural |

**El respaldo de `clamp(A,B,C)` es B**, el término de en medio, no el mínimo:
`vw`/`vh`/`vmin` existen desde Chrome 26, así que una pantalla vieja conserva
la letra fluida y pierde solo los topes. Poner el mínimo dejaría un 4K con
letra de móvil.

**`gap`, uno por uno.** No hay una sola política porque no son el mismo caso:

| Regla | Contexto | Respaldo |
|---|---|---|
| `.mod-product`, `.mod-comparison` | grid | **`grid-gap`** delante — es exacto y existe desde Chrome 57 |
| `.mod-fx-header`, `.fx-row`, `.weather-details`, `#waiting` | flex | margen en los hijos: en flex no hay equivalente antiguo |
| `.mod-fx-rows` | flex, `gap:0` | nada, ya vale cero |

En grid **sí hay un respaldo exacto** (`grid-gap`), así que ahí no se pierde
nada. En flex no lo hay: se compensa con márgenes en los hijos, que es lo que
se hacía antes de que existiera `gap`.

**La trampa que hay que dejar escrita en el código:** `--fx-title-size:clamp(…)`
es una *custom property*, y esas **admiten cualquier valor** aunque el navegador
no lo entienda. El fallo no ocurre al declararla sino donde se **usa** con
`var()`. El respaldo va en el sitio de uso. Quien lo revise mirando el `:root`
no encontrará nada roto.

### Que no vuelva a pasar

Test nuevo en `npm test`: lee el `<style>` de `player.html` y **exige que toda
declaración con sintaxis moderna tenga su respaldo delante, en la misma regla**.
Estático, sin navegador. Es el patrón de invariante que ya usan
`currency-db-sync.test.js` y `fx-countries-sync.test.js`.

Sin este test, el siguiente `clamp()` que alguien añada reabre el agujero sin
que nada se queje — que es exactamente como se llegó hasta aquí.

## Parte 2 — Borde de seguridad

- Ajuste **por pantalla**: `safe_margin`, entero de **0 a 5** (por ciento),
  **por defecto 0**. Se suma a las claves de pantalla que ya existen
  (`shuffle`, `priority_every`, `standby_image`, `always_on`).
- **Se aplica en el mismo sitio que el respaldo de `inset`**, y esa
  coincidencia es lo que hace que las dos partes se resuelvan con una línea:

  ```css
  .slide{ top:var(--safe,0px); right:var(--safe,0px);
          bottom:var(--safe,0px); left:var(--safe,0px); }
  ```

  Sustituye a `inset:0` en vez de acompañarlo — cuatro longhands que Chrome 62
  entiende, con el margen ya dentro. `var()` existe desde Chrome 49, así que la
  caja también lo lee. `--safe` se pone en `#player` desde JS al aplicar la
  configuración de pantalla; si no hay ajuste, no se define y manda el `0px`.

  **Por qué así y no `padding` en `#player`:** en un elemento absoluto los
  porcentajes de `top`/`bottom` se resuelven contra la **altura** del bloque
  contenedor y los de `left`/`right` contra la **anchura**, de modo que un 3 %
  es un 3 % real de cada lado. Con `padding:3%` los cuatro lados se calculan
  contra la anchura, y en una pantalla apaisada el margen de arriba y abajo
  saldría desproporcionado. Además esto sobrevive a `config.rotation`, que
  intercambia el alto y el ancho del `#player`.
- En el panel, junto al resto de ajustes de pantalla.
- Valor ausente, vacío o fuera de rango → **0**. Nunca puede dejar una pantalla
  con un margen que se coma el contenido.

## Fuera de alcance

- No se reescribe ningún diseño ni cambia el aspecto en pantallas modernas.
- No se toca `admin.html` más allá del campo nuevo.
- Forzar el WebView moderno en la caja (`cmd webviewupdate
  set-webview-implementation com.google.android.webview`) es un apaño de
  operación, no código: sirve para desatascar la tienda hoy, no sustituye a la
  Parte 1 porque hay que repetirlo caja por caja y no cubre los Smart TV.

## Verificación

Criterio de aceptación, en este orden:

1. `npm test` verde, incluido el test de respaldos nuevo.
2. **Renderizar**, que es lo que manda en un fallo visual: con el arnés de
   arriba, la variante sin sintaxis moderna tiene que medir **1280×720** y sus
   filas **no desbordar**. Hoy da 1116×106.
3. La variante moderna no cambia ni un píxel respecto a hoy.

Lo que **no** se puede verificar aquí y hay que decir: cómo queda en la caja
real. Eso pide instalar y mirar.
