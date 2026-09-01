# CSS compatible con navegadores viejos + borde de seguridad — Plan

> **Para agentes:** SUB-SKILL OBLIGATORIA: usa `superpowers:subagent-driven-development` (recomendada) o `superpowers:executing-plans` para implementar tarea por tarea. Los pasos llevan casilla (`- [ ]`).

**Goal:** Que `player.html` se pinte igual en un WebView de 2017 que en uno moderno, y añadir un margen de seguridad opcional por pantalla.

**Architecture:** Ninguna declaración moderna se borra: se le pone delante la equivalente antigua y la cascada hace el resto. La única excepción es `inset:0`, que se sustituye por sus cuatro longhands porque ahí mismo entra el margen de seguridad (`top:var(--safe,0px)`…). Un test estático lee el `<style>` de `player.html` y exige el respaldo, para que el próximo `clamp()` no reabra el agujero en silencio.

**Tech Stack:** HTML/CSS/JS puro (sin frameworks, sin paso de compilación), tests con `node:test` de la stdlib.

## Global Constraints

- **Sin frameworks JS y sin paso de build.** Los `.html` se editan y se sirven tal cual.
- **Sin dependencias nuevas** en `package.json`. Los tests usan solo `node:test`, `node:assert`, `node:fs`, `node:path`.
- **Navegador objetivo mínimo: Chrome 62.** Nada de `clamp()`, `min()`, `max()`, `gap` en flex, `aspect-ratio` ni `inset` sin respaldo.
- **El aspecto en navegadores modernos no puede cambiar ni un píxel.**
- `safe_margin`: entero **0 a 5**, por defecto **0**. Valor ausente, vacío o fuera de rango → **0**.
- Comentarios y nombres en **español**, como el resto del repo.
- Subir versión con `tools\subir-version.ps1` **antes** de compilar nada.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `tests/css-respaldos.test.js` | **Nuevo.** El invariante: toda sintaxis moderna del `<style>` de `player.html` lleva respaldo. |
| `tests/margen-seguro.test.js` | **Nuevo.** La función que traduce `safe_margin` a CSS. |
| `player.html` | El `<style>` (respaldos) y el bloque de margen seguro en el JS. |
| `admin.html` | Un campo en el modal de playlist, junto a «prioridad ⭐ cada». |
| `CHANGELOG.md`, `CLAUDE_CODE_PROMPT.md`, `MANUAL.md` | Documentación del cambio. |

---

### Task 1: El invariante — test de respaldos (queda en ROJO a propósito)

**Files:**
- Create: `tests/css-respaldos.test.js`

**Interfaces:**
- Consumes: nada.
- Produces: nada que consuma otra tarea. Es la red que valida las tareas 2-5.

- [ ] **Step 1: Escribir el test**

Crear `tests/css-respaldos.test.js`:

```js
/**
 * Que el player se pinte en un navegador viejo.
 *
 * La caja Android de la tienda carga com.android.chrome 62, de 2017, aunque
 * tenga instalado el WebView 119. En CSS, una declaracion con propiedad
 * desconocida o valor invalido SE DESCARTA ENTERA Y EN SILENCIO: no hay error,
 * no hay aviso, simplemente no existe.
 *
 * Paso de verdad (2026-09-01): `.slide{position:absolute;inset:0}` -inset es
 * Chrome 87- dejaba la diapositiva sin nada a que agarrarse, encogida a
 * 1116x106 en vez de 1280x720, con las filas de divisas desbordando y toda la
 * letra a 16px. En el escaparate de una tienda.
 *
 * Este test es la red: sin el, el proximo clamp() que alguien añada reabre el
 * agujero sin que nada se queje, que es exactamente como se llego hasta aqui.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const PLAYER = path.join(__dirname, "..", "player.html");

/**
 * Las reglas del CSS, una a una.
 *
 * Se buscan bloques `{...}` SIN llaves dentro, que son los cuerpos de regla de
 * verdad. Un `@media{...}` lleva llaves dentro, asi que no casa y sus reglas
 * interiores se recogen por su cuenta: no hace falta tratarlo aparte.
 */
function reglas() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf("<style>");
  const b = src.indexOf("</style>", a + 1);
  assert.ok(a >= 0 && b > a, "no se encuentra el <style> de player.html");
  const css = src.slice(a + "<style>".length, b);

  const salida = [];
  const re = /([^{}]*)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(css)) !== null) {
    const selector = m[1].split(/[;}]/).pop().trim();
    const decls = m[2]
      .split(";")
      .map(d => d.trim())
      .filter(Boolean)
      .map(d => {
        const i = d.indexOf(":");
        return i < 0 ? null : { prop: d.slice(0, i).trim(), valor: d.slice(i + 1).trim() };
      })
      .filter(Boolean);
    if (decls.length) salida.push({ selector, decls });
  }
  return salida;
}

/** ¿Hay antes una declaracion de esta misma propiedad en la misma regla? */
function tieneRespaldoAntes(decls, indice) {
  const prop = decls[indice].prop;
  return decls.slice(0, indice).some(d => d.prop === prop);
}

const FUNCIONES_MODERNAS = /(?:^|[\s(,])(?:clamp|min|max)\(/;

test("toda declaracion con clamp()/min()/max() lleva su respaldo delante", () => {
  const fallos = [];
  for (const r of reglas()) {
    r.decls.forEach((d, i) => {
      if (!FUNCIONES_MODERNAS.test(d.valor)) return;
      // Las custom properties admiten cualquier valor: el fallo no ocurre al
      // declararlas sino donde se usan con var(). Se comprueban alli.
      if (d.prop.startsWith("--")) return;
      if (!tieneRespaldoAntes(r.decls, i)) {
        fallos.push(`${r.selector} { ${d.prop}: ${d.valor} }`);
      }
    });
  }
  assert.deepStrictEqual(fallos, [],
    `Sin respaldo para Chrome 62. Pon delante la misma propiedad con el termino\n` +
    `de en medio del clamp (ej: font-size:6vw antes de font-size:clamp(28px,6vw,96px)):\n  ` +
    fallos.join("\n  "));
});

test("no se usa inset: en ninguna regla", () => {
  const fallos = [];
  for (const r of reglas()) {
    for (const d of r.decls) {
      if (d.prop === "inset") fallos.push(`${r.selector} { inset: ${d.valor} }`);
    }
  }
  assert.deepStrictEqual(fallos, [],
    "inset es Chrome 87. Usa top/right/bottom/left, que ademas es donde entra --safe:\n  " +
    fallos.join("\n  "));
});

/** `gap`, `row-gap` y `column-gap`: las tres llegaron a la vez y las tres faltan. */
const PROPS_HUECO = ["gap", "row-gap", "column-gap"];

test("gap en una rejilla lleva grid-gap delante", () => {
  const fallos = [];
  for (const r of reglas()) {
    const esRejilla = r.decls.some(d => d.prop === "display" && /grid/.test(d.valor));
    if (!esRejilla) continue;
    r.decls.forEach((d, i) => {
      if (!PROPS_HUECO.includes(d.prop)) return;
      const tiene = r.decls.slice(0, i).some(x => x.prop === "grid-" + d.prop || x.prop === "grid-gap");
      if (!tiene) fallos.push(`${r.selector} { ${d.prop}: ${d.valor} }`);
    });
  }
  assert.deepStrictEqual(fallos, [],
    "gap sin prefijo en grid es Chrome 66; grid-gap existe desde la 57:\n  " +
    fallos.join("\n  "));
});

/**
 * En FLEX no hay respaldo antiguo de `gap`: hay que separar con margenes en los
 * hijos. Como eso no se puede comprobar leyendo la regla, se lleva una lista
 * explicita. Añadir una entrada aqui obliga a mirar si los hijos ya se separan.
 */
const FLEX_CON_GAP_REVISADOS = [
  ".mod-fx-header",   // margen compensado
  ".fx-row",          // margen compensado
  ".weather-details", // margen compensado
  "#waiting",         // margen compensado
  ".mod-fx-rows",     // gap:0, no hay nada que compensar
  ".apilado"          // row-gap con flex-wrap: se acepta perderlo, es 1vh
];

test("ningun flex nuevo usa gap sin haberlo pensado", () => {
  const nuevos = [];
  for (const r of reglas()) {
    const esRejilla = r.decls.some(d => d.prop === "display" && /grid/.test(d.valor));
    if (esRejilla) continue;
    if (!r.decls.some(d => PROPS_HUECO.includes(d.prop))) continue;
    if (!FLEX_CON_GAP_REVISADOS.includes(r.selector)) nuevos.push(r.selector);
  }
  assert.deepStrictEqual(nuevos, [],
    "gap en flex es Chrome 84 y no tiene equivalente antiguo. Separa los hijos\n" +
    "con margenes dentro del @supports y añade el selector a\n" +
    "FLEX_CON_GAP_REVISADOS:\n  " + nuevos.join("\n  "));
});

/**
 * `aspect-ratio` es Chrome 88, pero aqui solo se usa sobre IMAGENES, y una
 * imagen sin aspect-ratio se dibuja con su proporcion natural — que es
 * justo lo que se le estaba pidiendo. La degradacion es aceptable y no
 * merece inventarle un respaldo con el truco del padding, que ademas
 * romperia el `object-fit`.
 *
 * La lista existe para que un aspect-ratio nuevo sobre algo que NO sea una
 * imagen obligue a pararse: ahi si dejaria un hueco de alto cero.
 *
 * OJO: este test solo ve el <style>. La bandera de `.fx-flag` lleva el suyo
 * en un `style=` en linea dentro de una plantilla de JS, y hay que mirarla a
 * mano (`grep aspect-ratio player.html`).
 */
const ASPECT_RATIO_REVISADOS = [".product-image", ".comparison-image"];

test("aspect-ratio solo donde la proporcion natural sirve de respaldo", () => {
  const nuevos = [];
  for (const r of reglas()) {
    if (!r.decls.some(d => d.prop === "aspect-ratio")) continue;
    if (!ASPECT_RATIO_REVISADOS.includes(r.selector)) nuevos.push(r.selector);
  }
  assert.deepStrictEqual(nuevos, [],
    "aspect-ratio es Chrome 88. Sobre una imagen se puede perder (queda su\n" +
    "proporcion natural); sobre una caja deja alto cero. Comprueba cual es y\n" +
    "añadelo a ASPECT_RATIO_REVISADOS:\n  " + nuevos.join("\n  "));
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/css-respaldos.test.js`
Expected: **FAIL** en varios tests. En concreto `no se usa inset:` señalando `.slide`, y el de `clamp()` listando decenas de reglas. Es lo correcto: el código todavía no está arreglado.

Anota el número de fallos que salen; las tareas 2-5 lo bajan hasta cero.

- [ ] **Step 3: Commit**

```bash
git add tests/css-respaldos.test.js
git commit -m "Test: el player tiene que pintarse en un navegador de 2017"
```

---

### Task 2: `.slide` sin `inset` y con el gancho del margen

**Files:**
- Modify: `player.html:15` (la regla `.slide`)
- Test: `tests/css-respaldos.test.js` (ya existe, Task 1)

**Interfaces:**
- Consumes: nada.
- Produces: la variable CSS **`--safe`**, que se lee en `.slide` con `var(--safe,0px)`. La Task 3 la escribe desde JS sobre `#player`.

- [ ] **Step 1: Ver el test en rojo para esta regla concreta**

Run: `node --test tests/css-respaldos.test.js 2>&1 | grep -A3 "no se usa inset"`
Expected: FAIL nombrando `.slide { inset: 0 }`

- [ ] **Step 2: Cambiar la regla**

En `player.html` línea 15, sustituir `position:absolute;inset:0;` por los cuatro longhands. La regla queda:

```css
.slide{position:absolute;top:var(--safe,0px);right:var(--safe,0px);bottom:var(--safe,0px);left:var(--safe,0px);opacity:0;display:flex;align-items:center;justify-content:center;background:#000;
```

(el resto de la regla, a partir de `opacity:0`, no se toca)

Y justo encima de la regla, el comentario que explica por qué no es `inset`:

```css
/* Los cuatro longhands y no inset:0 por DOS motivos. Uno: inset es Chrome 87 y
   la caja de la tienda carga Chrome 62, donde la declaracion se descarta entera
   y la diapositiva se encoge al tamaño de su contenido -medido: 1116x106 en vez
   de 1280x720-. Dos: aqui es donde entra el margen de seguridad, porque en un
   elemento absoluto los porcentajes de top/bottom se miden contra el ALTO del
   contenedor y los de left/right contra el ANCHO, asi que un 3% es un 3% real
   de cada lado. Con padding:3% los cuatro se medirian contra el ancho. */
```

- [ ] **Step 3: Ver ese test en verde**

Run: `node --test tests/css-respaldos.test.js 2>&1 | grep "no se usa inset"`
Expected: `ok` (los de `clamp()` y `gap` siguen en rojo, es lo esperado)

- [ ] **Step 4: Commit**

```bash
git add player.html
git commit -m "El player: la diapositiva se posiciona sin inset, que es de 2020"
```

---

### Task 3: El margen de seguridad en el player

**Files:**
- Create: `tests/margen-seguro.test.js`
- Modify: `player.html` (bloque nuevo de JS + dos llamadas)

**Interfaces:**
- Consumes: la variable CSS `--safe` de la Task 2.
- Produces: `margenSeguroCss(cfg)` → `string`. Devuelve `"0px"` o `"N%"`. Y `aplicarMargenSeguro(cfg)`, que la escribe en `#player`.

- [ ] **Step 1: Escribir el test**

Crear `tests/margen-seguro.test.js`:

```js
/**
 * El margen de seguridad de los bordes.
 *
 * Algunos televisores recortan un 3-5% de cada borde (sobrebarrido), asi que se
 * puede pedir que el contenido se separe. Va por pantalla y por defecto a CERO:
 * un margen puesto donde no hace falta quita sitio a un tablero que ya va
 * justo, asi que nadie lo sufre hasta que lo activa.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const PLAYER = path.join(__dirname, "..", "player.html");
const INICIO = "// ── Margen de seguridad";
const FIN = "// ── fin del margen de seguridad";

function cargar() {
  const src = fs.readFileSync(PLAYER, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  assert.ok(a >= 0 && b > a, "no se encuentra el bloque del margen en player.html");
  const ctx = { document: { getElementById: () => null } };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

test("sin ajuste no hay margen", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss(null), "0px");
  assert.strictEqual(margenSeguroCss({}), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: 0 }), "0px");
});

test("un ajuste normal se convierte en porcentaje", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss({ safe_margin: 3 }), "3%");
  assert.strictEqual(margenSeguroCss({ safe_margin: 5 }), "5%");
});

test("se recorta a 5 y nunca es negativo", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss({ safe_margin: 40 }), "5%");
  assert.strictEqual(margenSeguroCss({ safe_margin: -3 }), "0px");
});

test("la basura vale cero, no rompe la pantalla", () => {
  const { margenSeguroCss } = cargar();
  // Un valor raro en content.json no puede dejar un escaparate en blanco.
  assert.strictEqual(margenSeguroCss({ safe_margin: "" }), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: "tres" }), "0px");
  assert.strictEqual(margenSeguroCss({ safe_margin: null }), "0px");
});

test("un decimal se queda en el entero de abajo", () => {
  const { margenSeguroCss } = cargar();
  assert.strictEqual(margenSeguroCss({ safe_margin: 2.7 }), "2%");
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/margen-seguro.test.js`
Expected: FAIL — «no se encuentra el bloque del margen en player.html»

- [ ] **Step 3: Escribir el bloque**

En `player.html`, justo **antes** de `function applyRotation(deg){` (línea ~227):

```js
// ── Margen de seguridad
/**
 * Cuanto separar el contenido de los bordes, en CSS.
 *
 * Hay televisores que recortan un 3-5% de cada borde (sobrebarrido) y se comen
 * lo que haya pegado al filo. Va POR PANTALLA y por defecto a cero: un margen
 * donde no hace falta le quita sitio a un tablero que ya va justo, asi que solo
 * lo paga quien lo pide.
 *
 * Se recorta a 5 a proposito: mas que eso no es un margen, es un problema de
 * configuracion del televisor, y dejarlo subir mas solo esconderia el sintoma.
 */
function margenSeguroCss(cfg){
  const n=Math.floor(Number(cfg&&cfg.safe_margin));
  if(!isFinite(n)||n<=0) return "0px";
  return Math.min(5,n)+"%";
}

/** Lo escribe en #player, que es el bloque contenedor de las diapositivas. */
function aplicarMargenSeguro(cfg){
  const p=document.getElementById("player");
  if(p) p.style.setProperty("--safe",margenSeguroCss(cfg));
}
// ── fin del margen de seguridad
```

- [ ] **Step 4: Ver el test en verde**

Run: `node --test tests/margen-seguro.test.js`
Expected: PASS, 5 tests

- [ ] **Step 5: Llamarlo donde se aplica la configuración de pantalla**

En `player.html` hay dos sitios donde se asigna `screenConfig` y se llama a `aplicarTransicion(screenConfig)` — la caché (línea ~554) y el refresco de playlist (línea ~662). Añadir la llamada al lado en **ambos**:

```js
aplicarTransicion(screenConfig);
aplicarMargenSeguro(screenConfig);
```

Los dos, no uno: si solo se pone en el refresco, una pantalla que arranca sin servidor pinta desde la caché **sin** el margen y salta al ponerse en contacto.

- [ ] **Step 6: Toda la suite en verde salvo lo que falta**

Run: `npm test 2>&1 | tail -5`
Expected: pasan `margen-seguro` y los de siempre; `css-respaldos` sigue en rojo por `clamp()` y `gap`.

- [ ] **Step 7: Commit**

```bash
git add player.html tests/margen-seguro.test.js
git commit -m "El player: margen de seguridad opcional por pantalla, a cero por defecto"
```

---

### Task 4: Respaldos de `clamp()`, `min()` y `max()`

**Files:**
- Modify: `player.html` (el `<style>`)

**Interfaces:**
- Consumes: el test de la Task 1.
- Produces: nada nuevo.

- [ ] **Step 1: Ver el rojo y contar**

Run: `node --test tests/css-respaldos.test.js 2>&1 | grep -c "^\s*[.#]"`
Anota el número de reglas señaladas.

- [ ] **Step 2: Aplicar la transformación**

**La regla:** delante de cada declaración con `clamp(A,B,C)` va la misma propiedad con **B**, el término de en medio. `vw`/`vh`/`vmin` existen desde Chrome 26, así que una pantalla vieja conserva la letra fluida y pierde solo los topes. Poner **A** dejaría un 4K con letra de móvil.

Ejemplo de lo que tiene que quedar:

```css
.text-slide h1{font-size:6vw;font-size:clamp(28px,6vw,96px);font-weight:700;...}
```

Guardar este script como `aplicar-respaldos.js` en la raíz, ejecutarlo **una vez** y borrarlo después:

```js
// Un solo uso: pone el respaldo delante de cada clamp()/min()/max().
const fs = require("node:fs");
const F = "player.html";
const src = fs.readFileSync(F, "utf8");
const a = src.indexOf("<style>"), b = src.indexOf("</style>", a + 1);
let css = src.slice(a, b), n = 0;

// El termino de en medio de clamp(A,B,C), respetando parentesis anidados.
function medio(args) {
  const partes = []; let prof = 0, act = "";
  for (const c of args) {
    if (c === "(") prof++;
    if (c === ")") prof--;
    if (c === "," && prof === 0) { partes.push(act); act = ""; continue; }
    act += c;
  }
  partes.push(act);
  return partes.length === 3 ? partes[1].trim() : null;
}

css = css.replace(/([-a-zA-Z]+)\s*:\s*(clamp\(([^;{}]*)\))/g, (m, prop, todo, args) => {
  if (prop.startsWith("--")) return m;      // las custom props aceptan cualquier cosa
  const b2 = medio(args);
  if (!b2) return m;
  n++;
  return `${prop}:${b2};${prop}:${todo}`;
});

fs.writeFileSync(F, src.slice(0, a) + css + src.slice(b), "utf8");
console.log("respaldos puestos:", n);
```

Run: `node aplicar-respaldos.js && rm aplicar-respaldos.js`
Expected: `respaldos puestos: 38`

- [ ] **Step 2b: Revisar el diff, que es una reescritura automática de CSS**

Run: `git diff player.html | head -60`

Mirar **una por una** que cada línea tocada tenga la forma `prop:B;prop:clamp(A,B,C)` y nada más. Un `clamp()` con paréntesis anidados —`clamp(16px, calc(2vw + 4px), 40px)`— puede hacer que la captura del script se pase de largo. Si ves cualquier declaración partida o un valor comido:

```bash
git checkout player.html
```

y hazlo a mano. Son 38, se tarda menos que en depurar una expresión regular.

- [ ] **Step 3: Los `min()`/`max()` sueltos, a mano**

El script solo cubre `clamp()`. Los `min()`/`max()` que queden los señala el test: para cada uno, poner delante la misma propiedad con **el término más conservador** (el que no depende del viewport).

Run: `node --test tests/css-respaldos.test.js 2>&1 | grep -A20 "clamp()/min()/max()"`
y arreglar uno a uno los que liste.

- [ ] **Step 4: Los `var()` de custom properties con `clamp()` dentro**

`--fx-title-size:clamp(16px,3.4vmin,40px)` **no** la toca el script, a propósito: una custom property admite cualquier valor y no falla al declararse. Falla donde se **usa**. Buscar los usos:

Run: `grep -n 'var(--fx-title-size' player.html`

Y en cada uso, poner delante el respaldo:

```css
font-size:3.4vmin;font-size:var(--fx-title-size);
```

- [ ] **Step 5: Ver los tests de clamp en verde**

Run: `node --test tests/css-respaldos.test.js`
Expected: pasa «toda declaracion con clamp()/min()/max() lleva su respaldo delante». Los de `gap` y `aspect-ratio` pueden seguir en rojo.

- [ ] **Step 6: Commit**

```bash
git add player.html
git commit -m "El player: respaldo de tamaños para navegadores sin clamp()"
```

---

### Task 5: Respaldos de `gap` y `aspect-ratio`

**Files:**
- Modify: `player.html` (el `<style>`)

**Interfaces:**
- Consumes: el test de la Task 1, incluida la lista `FLEX_CON_GAP_REVISADOS`.
- Produces: nada nuevo.

- [ ] **Step 1: Las rejillas — respaldo exacto y gratis**

`.mod-product` y `.mod-comparison` son `display:grid`. Ahí **sí** hay equivalente antiguo: `grid-gap`, que existe desde Chrome 57. Poner delante:

```css
.mod-product{...;display:grid;grid-template-columns:1fr 1fr;grid-gap:6vw;gap:6vw;...}
.mod-comparison{...;display:grid;grid-template-columns:1fr 1fr;grid-gap:4vw;gap:4vw;...}
```

- [ ] **Step 2: Los flex — márgenes, pero solo donde falta `gap`**

En flex no hay equivalente antiguo, así que hay que separar los hijos con margen. Pero **el margen no puede ir suelto**: se sumaría al `gap` en los navegadores modernos y el `3%` de la cabecera pasaría a `6%`, que se ve. Va dentro de una consulta de características, que existe desde Chrome 28 y por tanto la caja la entiende.

Añadir al final del `<style>`:

```css
/* Huecos de flex para navegadores sin `gap`.
   En Chrome 62 `gap` no existe ni siquiera en grid, asi que la consulta es
   falsa alli -y entran los margenes- y verdadera en cualquier navegador
   moderno, que se queda con su gap y NO suma el margen.
   Hueco conocido y asumido: entre Chrome 66 y 83 `gap` valia en grid pero no
   en flex, asi que ahi esto no entra y los huecos de flex quedan a cero. El
   objetivo es la caja de 2017, no toda la historia de Chrome. */
@supports not (gap:1px){
  .mod-fx-header>*+*{margin-left:3%}
  .fx-row>*+*{margin-left:2.5%}
  .weather-details>*+*{margin-left:4vw}
  #waiting>*+*{margin-top:16px}
}
```

`.mod-fx-rows` tiene `gap:0` y `.apilado` usa `row-gap:1vh` con `flex-wrap`: la primera no tiene nada que compensar y la segunda perdería 1vh de separación entre líneas, que es asumible. Las dos se quedan en la lista del test con su comentario.

- [ ] **Step 3: `aspect-ratio` — comprobar que solo está sobre imágenes**

Run: `grep -n 'aspect-ratio' player.html`
Expected: tres sitios — `.product-image`, `.comparison-image` y el `style=` en línea de la bandera (`vendor/flags`).

**Los tres son imágenes, así que no se toca ninguno.** Una imagen sin `aspect-ratio` se dibuja con su proporción natural, que es justo lo que se le pedía; inventarle un respaldo con el truco de `padding-bottom` rompería el `object-fit` que ya llevan. Lo que sí hay que hacer es dejarlo escrito, porque el próximo que lo lea va a querer "arreglarlo":

En el `<style>`, encima de `.product-image`:

```css
/* aspect-ratio es Chrome 88 y en la caja de la tienda se descarta. Se acepta:
   son imagenes, y sin el se dibujan con su proporcion natural. No poner el
   truco de height:0;padding-bottom:100% — rompe el object-fit de al lado. */
```

- [ ] **Step 4: Test de respaldos entero en verde**

Run: `node --test tests/css-respaldos.test.js`
Expected: PASS, los 5 tests

- [ ] **Step 5: Commit**

```bash
git add player.html
git commit -m "El player: respaldo de gap y aspect-ratio para navegadores viejos"
```

---

### Task 6: Verificar renderizando (el paso que no se salta)

**Files:**
- Ninguno. Es comprobación.

**Interfaces:**
- Consumes: `player.html` ya arreglado.
- Produces: la prueba de que funciona, o el rojo que dice que no.

> **Por qué este paso existe:** en este proyecto un fallo visual **se renderiza, no se lee**. Un título recortado se «arregló» dos veces sin efecto hasta fotografiarlo. Los tests de arriba comprueban que el respaldo *está escrito*; solo el navegador dice si *funciona*.

- [ ] **Step 1: Preparar el arnés**

```bash
mkdir -p /tmp/arnes/vendor && cp player.html /tmp/arnes/ && cp -r vendor/flags /tmp/arnes/vendor/
```

- [ ] **Step 2: Generar la variante «Chrome 62»**

Guardar como `/tmp/arnes/simular62.py` y ejecutarlo desde `/tmp/arnes`. Quita exactamente lo que Chrome 62 descarta. **Los respaldos que acabas de poner sobreviven**, porque son sintaxis antigua — de eso va la prueba.

```python
import re, pathlib
src = pathlib.Path("player.html").read_text(encoding="utf-8")
quitadas = {}
def tirar(patron, etiqueta, texto):
    def rep(m):
        quitadas[etiqueta] = quitadas.get(etiqueta, 0) + 1
        return ""
    return re.sub(patron, rep, texto)
t = src
t = tirar(r'(?<![-a-z])inset\s*:[^;}"]*;?', "inset", t)
t = tirar(r'(?<![-a-z])(?:row-|column-)?gap\s*:[^;}"]*;?', "gap", t)
t = tirar(r'(?<![-a-z])aspect-ratio\s*:[^;}"]*;?', "aspect-ratio", t)
t = tirar(r'[-a-zA-Z]+\s*:[^;}"]*\bclamp\([^;}"]*;?', "clamp()", t)
t = tirar(r'[-a-zA-Z]+\s*:[^;}"]*(?<![-a-z])(?:min|max)\([^;}"]*;?', "min()/max()", t)
pathlib.Path("player62.html").write_text(t, encoding="utf-8")
for k, v in sorted(quitadas.items()): print(f"{k:14} {v}")
```

Run: `cd /tmp/arnes && python simular62.py`
Expected: imprime el recuento de lo descartado (antes del arreglo eran 58 declaraciones).

- [ ] **Step 3: La página que mide**

Guardar como `/tmp/arnes/marco.html`:

```html
<!doctype html><meta charset="utf-8"><title>arnes</title>
<style>body{margin:0;background:#222}#salida{color:#0f0;font:12px monospace;white-space:pre}</style>
<div id="salida">midiendo…</div>
<script>
const q=new URLSearchParams(location.search);
const ARCHIVO=q.get("p")||"player.html";
const W=+(q.get("w")||1280), H=+(q.get("h")||720);
const ITEM={id:"fx1",type:"fx",title:"Western Union - Tipos de cambio",
  base_currency:"EUR",bg:"#0A2540",color:"#ffffff",duration:10,
  rows:[{flag:"co",country:"Colombia",currency:"Peso colombiano",code:"COP",rate:"3642,02"},
        {flag:"py",country:"Paraguay",currency:"Guaranies",code:"PYG",rate:"6840,13"},
        {flag:"hn",country:"Honduras",currency:"Lempiras",code:"HNL",rate:"31,10"},
        {flag:"ve",country:"Venezuela",currency:"Dolar estadounidense",code:"USD",rate:"1,05"},
        {flag:"ph",country:"Filipinas",currency:"Peso filipino",code:"PHP",rate:"65,40",agent:"RIA & Palawan Express"},
        {flag:"ma",country:"Marruecos",currency:"Dirham",code:"MAD",rate:"10,82"}]};
const ifr=document.createElement("iframe");
ifr.style.cssText="width:"+W+"px;height:"+H+"px;border:0;display:block";
ifr.src=ARCHIVO+"?preview=1";
document.body.appendChild(ifr);
let enviado=false;
addEventListener("message",e=>{
  if((e.data||{}).type==="preview-ready" && !enviado){
    enviado=true;
    ifr.contentWindow.postMessage({type:"preview-item",item:ITEM,rotation:0},"*");
    setTimeout(medir,1200);
  }
});
function r(el){ if(!el) return null; const b=el.getBoundingClientRect();
  return {w:Math.round(b.width),h:Math.round(b.height)}; }
function medir(){
  const d=ifr.contentDocument, w=ifr.contentWindow;
  const slide=d.querySelector(".slide"), rows=d.querySelector(".mod-fx-rows");
  const s=r(slide);
  document.getElementById("salida").textContent="RESULTADO="+JSON.stringify({
    archivo:ARCHIVO, viewport:{w:w.innerWidth,h:w.innerHeight}, slide:s,
    llenaLaPantalla: !!(s && Math.abs(s.w-w.innerWidth)<2 && Math.abs(s.h-w.innerHeight)<2),
    filasDesbordan: rows ? (rows.scrollHeight>rows.clientHeight+1) : null,
    letraTasa: (d.querySelector(".fx-rate-val")||{}) &&
      (d.querySelector(".fx-rate-val")?getComputedStyle(d.querySelector(".fx-rate-val")).fontSize:"?")
  });
}
</script>
```

Luego servir y medir las dos variantes:

```bash
cd /tmp/arnes && python -m http.server 8099 --bind 127.0.0.1 &
for V in player.html player62.html; do
  chrome --headless=new --disable-gpu --virtual-time-budget=8000 --dump-dom \
    "http://127.0.0.1:8099/marco.html?p=$V&w=1280&h=720" | grep -o 'RESULTADO=.*' | head -1
done
```

- [ ] **Step 4: El criterio de aceptación**

| Medida | Antes (roto) | Tiene que dar |
|---|---|---|
| `.slide` | 1116×106 | **1280×720** |
| filas desbordan | sí (300 px en 23) | **no** |
| letra de la tasa | 16 px | **> 30 px** |

Si `.slide` no mide 1280×720, **para**: el respaldo de `inset` no está haciendo su trabajo y no sirve de nada seguir.

- [ ] **Step 5: Comprobar que lo moderno no cambió**

Renderizar también `player.html` (el de verdad) y comparar con la captura de antes del cambio. Tiene que ser **idéntica**. Si cambió algo, un respaldo se está colando por encima de la declaración moderna: revisa el orden, la antigua va **primero**.

- [ ] **Step 6: Commit** (solo si hubo arreglos en este paso)

```bash
git add player.html
git commit -m "El player: ajustes tras verificar el render en navegador viejo"
```

---

### Task 7: El campo en el panel

**Files:**
- Modify: `admin.html:1128-1133` (el HTML, junto a «prioridad ⭐ cada»)
- Modify: `admin.html:1852` (cargar el valor)
- Modify: `admin.html:2011-2013` (guardarlo)

**Interfaces:**
- Consumes: la clave `safe_margin` que lee `margenSeguroCss()` en el player (Task 3).
- Produces: `content.screens[sid].safe_margin` como entero 0-5.

- [ ] **Step 1: El campo**

En `admin.html`, dentro del mismo `<div>` que contiene `plm-priority-wrap` (línea ~1133), después de ese `<span>`:

```html
<span style="display:flex;align-items:center;gap:6px;font-size:12px">
  <span style="color:var(--muted)">margen de seguridad</span>
  <input class="finput" id="plm-safe-margin" type="number" min="0" max="5" step="1"
         value="0" style="width:56px"
         title="Separa el contenido de los bordes. Solo hace falta en televisores que recortan la imagen (sobrebarrido). 0 = sin margen.">
  <span style="color:var(--muted)">%</span>
</span>
```

- [ ] **Step 2: Cargarlo al abrir el modal**

En `admin.html` línea ~1852, junto a la línea de `plm-priority-every`:

```js
document.getElementById("plm-safe-margin").value=cfg.safe_margin||0;
```

- [ ] **Step 3: Guardarlo**

En `admin.html` línea ~2013, después del bloque de `priority_every`:

```js
const margen=parseInt(document.getElementById("plm-safe-margin").value,10);
content.screens[editingScreen].safe_margin=
  isNaN(margen)?0:Math.max(0,Math.min(5,margen));
```

El recorte va **en los dos sitios** —aquí y en `margenSeguroCss()`— a propósito: el panel no es el único que escribe `content.json` (está la extensión, está una copia restaurada), así que el player no puede fiarse de que le llegue un valor sano.

- [ ] **Step 4: Probarlo de verdad**

```bash
python server.py --port 8080
```

Abrir `http://127.0.0.1:8080/admin.html`, poner margen 5 en una pantalla, guardar, y abrir `http://127.0.0.1:8080/player.html?screen=<nombre>`. El contenido tiene que separarse de los bordes. Ponerlo a 0 y comprobar que vuelve a pegarse.

- [ ] **Step 5: Commit**

```bash
git add admin.html
git commit -m "El panel: margen de seguridad por pantalla"
```

---

### Task 8: Versión, changelog y documentación

**Files:**
- Modify: `CHANGELOG.md`, `CLAUDE_CODE_PROMPT.md`, `MANUAL.md`
- Modify (por script): `server.py`, `installer/setup.iss`, `package.json`, `android/app/build.gradle.kts`

- [ ] **Step 1: Subir la versión**

```bash
powershell -ExecutionPolicy Bypass -File tools\subir-version.ps1 1.0.33
```

- [ ] **Step 2: CHANGELOG**

Entrada `## 1.0.33 — 2026-09-01` con dos apartados, escritos para el que atiende una tienda y no para el que escribe el código:

- **Corregido:** el contenido se veía mal en las cajas de TV con navegador antiguo — se salía, la letra salía diminuta y el tablero no llenaba la pantalla. Ahora se ve igual en cualquier pantalla.
- **Nuevo:** margen de seguridad por pantalla (0-5 %), para televisores que recortan los bordes. Por defecto 0.

- [ ] **Step 3: `CLAUDE_CODE_PROMPT.md`**

Añadir a *Gotchas de despliegue* el caso completo: qué se midió (1116×106 frente a 1280×720), que la causa era `inset`, que **la previa del admin corre en un navegador moderno y por eso no enseña lo que pinta la caja**, y que `tests/css-respaldos.test.js` es lo que impide que vuelva. Actualizar la línea de `Actualizado:` y el recuento de tests de `npm test`.

- [ ] **Step 4: `MANUAL.md`**

En la sección de ajustes de pantalla, dos frases: qué es el margen de seguridad, y que **solo hay que tocarlo si el televisor recorta los bordes** — no es un ajuste de estética.

- [ ] **Step 5: Todo verde**

Run: `npm test 2>&1 | tail -6`
Expected: 0 fallos, con los tests nuevos dentro del total.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "1.0.33: el contenido se ve igual en las cajas con navegador viejo"
```

---

## Notas para quien lo ejecute

- **El orden importa en el CSS.** El respaldo va **primero** y la declaración moderna **después**. Al revés no hace nada: el navegador viejo descarta la moderna y se queda sin respaldo, y el moderno se queda con la antigua.
- **No borres la declaración moderna.** La única que desaparece es `inset:0`, y solo porque sus longhands hacen exactamente lo mismo y además llevan el margen dentro.
- **No toques `admin.html` más de lo que dice la Task 7.** El panel se ve en navegadores modernos; su CSS no es el problema.
- **Si un test te estorba, no lo relajes.** El de `FLEX_CON_GAP_REVISADOS` está para que añadir un `gap` nuevo en flex obligue a pararse a pensar; quitar el selector de la lista es saltarse el aviso, no arreglarlo.
