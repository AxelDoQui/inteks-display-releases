# Ayuda por familia de aparato — Plan

> **Para agentes:** SUB-SKILL OBLIGATORIA: usa `superpowers:subagent-driven-development` (recomendada) o `superpowers:executing-plans` para implementar tarea por tarea. Los pasos llevan casilla (`- [ ]`).

**Goal:** Que la página de Ayuda del panel diga con qué reproducir y cómo dejarlo montado, por familia de aparato, y que deje de dar instrucciones que ya no funcionan.

**Architecture:** Todo el contenido nuevo vive en la página `page-help` de `admin.html` como tarjetas `<details>`. Un test estático lee esa página y comprueba tres cosas: que las instrucciones caducadas no han vuelto, que están las seis tarjetas, y que la del Fire TV Stick sigue diciendo que no está probada. `MANUAL.md` pierde su sección larga y remite al panel, para que solo haya un texto largo.

**Tech Stack:** HTML/CSS puro (sin JS nuevo: `<details>` es nativo), tests con `node:test` de la stdlib.

## Global Constraints

- **Sin frameworks JS y sin paso de build.** Los `.html` se editan y se sirven tal cual.
- **Sin dependencias nuevas** en `package.json`.
- **Cero JavaScript nuevo.** El plegado es `<details>`/`<summary>`, nativo.
- **Solo hechos verificados.** Si una afirmación no está en la tabla de la especificación, no se escribe. Nada de pasos modelo a modelo inventados.
- **El Fire TV Stick va marcado como no probado**, con esas palabras.
- Textos en **español**, en el tono del `MANUAL.md`: directo, sin jerga, dirigido a quien atiende una tienda.
- Subir versión con `tools\subir-version.ps1` antes de compilar nada.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `tests/ayuda-aparatos.test.js` | **Nuevo.** El invariante: no vuelven las instrucciones caducadas, están las seis tarjetas, y el Fire Stick sigue marcado como no probado. |
| `admin.html` | La página `page-help` (líneas 984-1034) y tres reglas de CSS para el `<summary>`. |
| `MANUAL.md` | La sección *Con qué reproducir* se reduce a un resumen que remite al panel. |
| `CHANGELOG.md`, `CLAUDE_CODE_PROMPT.md` | Documentación del cambio. |

---

### Task 1: El invariante, y arreglar la tarjeta que engaña

**Files:**
- Create: `tests/ayuda-aparatos.test.js`
- Modify: `admin.html:987-995` (la tarjeta «Conectar pantallas»)

**Interfaces:**
- Consumes: nada.
- Produces: la función `ayuda()` del test, que devuelve el HTML de `page-help`. Las tareas 2 y 3 añaden asserts que la usan.

- [ ] **Step 1: Escribir el test**

Crear `tests/ayuda-aparatos.test.js`:

```js
/**
 * La ayuda del panel no puede mentir.
 *
 * La tarjeta «Conectar pantallas» describia un flujo de desarrollo de una
 * version temprana: `python server.py`, el puerto 8080 y escribir la URL a mano
 * en cada tablet. Hoy el servidor lo arranca la tarea programada, el puerto es
 * el 80 y las pantallas se emparejan por PIN. Quien siguiera esa tarjeta no
 * conectaba nada.
 *
 * Una ayuda equivocada es peor que ninguna: manda a alguien a una tienda a
 * seguir pasos que no funcionan. Este test la vigila.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const ADMIN = path.join(__dirname, "..", "admin.html");

/** El HTML de la pagina de Ayuda, de su apertura al siguiente bloque. */
function ayuda() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf('<div class="page" id="page-help">');
  assert.ok(a >= 0, "no se encuentra page-help en admin.html");
  const candidatos = [
    src.indexOf('<div class="page"', a + 10),
    src.indexOf('<div class="modal-bd"', a + 10)
  ].filter(i => i > 0);
  const b = candidatos.length ? Math.min(...candidatos) : src.length;
  return src.slice(a, b);
}

test("la ayuda no manda ejecutar python ni usar el puerto 8080", () => {
  const h = ayuda();
  const caducadas = [
    ["python server.py", "el servidor lo arranca la tarea programada"],
    [":8080",            "el puerto es el 80, con 9000 de reserva"]
  ];
  const fallos = caducadas
    .filter(([txt]) => h.includes(txt))
    .map(([txt, por]) => `«${txt}» — ${por}`);
  assert.deepStrictEqual(fallos, [],
    "La ayuda vuelve a dar instrucciones que no funcionan:\n  " + fallos.join("\n  "));
});

test("la ayuda explica el emparejamiento por PIN, que es el flujo real", () => {
  const h = ayuda().toLowerCase();
  assert.ok(h.includes("pin"), "la ayuda no menciona el PIN de emparejamiento");
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: **FAIL** en «la ayuda no manda ejecutar python ni usar el puerto 8080», listando las dos cadenas.

- [ ] **Step 3: Reescribir la tarjeta**

En `admin.html`, sustituir el contenido de la tarjeta «Conectar pantallas» (línea ~987) por el flujo real:

```html
  <div class="card">
    <div class="card-title">Conectar una pantalla</div>
    <div style="font-size:13px;color:var(--muted);line-height:1.9">
      <p><strong style="color:var(--text)">1.</strong> En el aparato —tablet, televisor o caja— abre el navegador
      y entra en <code style="background:var(--s2);padding:2px 6px;border-radius:4px;font-family:monospace">http://IP-DEL-ORDENADOR/pair</code></p>
      <p><strong style="color:var(--text)">2.</strong> Escribe el <strong style="color:var(--text)">PIN</strong> que aparece
      en <em>Ajustes → Seguridad</em> de este panel. Vale 10 minutos.</p>
      <p><strong style="color:var(--text)">3.</strong> Ponle nombre a la pantalla y ya está reproduciendo.</p>
      <p style="margin-top:10px">Para girarla, en la tarjeta de la pantalla tienes la rotación (0, 90, 180 o 270).
      No hace falta tocar la dirección.</p>
      <p style="margin-top:10px"><strong style="color:var(--text)">En una caja Android usa la IP</strong>, no
      <code style="background:var(--s2);padding:2px 6px;border-radius:4px;font-family:monospace">signage.local</code>:
      Android no resuelve esos nombres. En iPhone y Mac sí funcionan.</p>
    </div>
  </div>
```

- [ ] **Step 4: Ver el test en verde**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: PASS, 2 tests

- [ ] **Step 5: La suite entera, que siete tests leen admin.html**

Run: `npm test 2>&1 | tail -6`
Expected: 0 fallos. Si algo se rompe, mira `clonar-pantalla.test.js`, `concurrencia-panel.test.js`, `currency-db-sync.test.js`, `extension-fx-picker.test.js`, `fx-countries-sync.test.js`, `fx-currency-picker.test.js` o `reordenar-listas.test.js`: extraen bloques de `admin.html` y son sensibles a que se muevan.

- [ ] **Step 6: Commit**

```bash
git add tests/ayuda-aparatos.test.js admin.html
git commit -m "El panel: la ayuda de conectar pantallas explicaba un flujo que ya no existe"
```

---

### Task 2: Las cinco tarjetas de familia

**Files:**
- Modify: `admin.html` (dentro de `page-help`, tras la tarjeta de conectar)
- Modify: `tests/ayuda-aparatos.test.js`

**Interfaces:**
- Consumes: `ayuda()` de la Task 1.
- Produces: seis elementos `<details class="aparato">`, uno por familia más el transversal de la Task 3.

- [ ] **Step 1: Añadir el test**

Añadir a `tests/ayuda-aparatos.test.js`:

```js
const FAMILIAS = [
  "Tablet o móvil",
  "Televisor con su propio navegador",
  "Caja Android TV",
  "Amazon Fire TV Stick",
  "Mini PC"
];

test("hay una tarjeta por familia de aparato", () => {
  const h = ayuda();
  const faltan = FAMILIAS.filter(f => !h.includes(f));
  assert.deepStrictEqual(faltan, [],
    "Faltan tarjetas de aparato en la ayuda:\n  " + faltan.join("\n  "));
});

/**
 * Del Fire TV Stick NO hay ninguna comprobacion. Fire OS es Android y admite
 * instalar APKs de lado, asi que la app deberia funcionar — pero «deberia» no
 * es «funciona», y la app declara leanback y apunta a API 28.
 *
 * Prometer lo que nadie ha visto manda a alguien a una tienda con un aparato
 * que no arranca. Cuando alguien lo pruebe de verdad, se quita el aviso Y se
 * quita este test, en el mismo commit.
 */
test("el Fire TV Stick sigue marcado como no probado", () => {
  const h = ayuda();
  const i = h.indexOf("Amazon Fire TV Stick");
  assert.ok(i >= 0, "no está la tarjeta del Fire TV Stick");
  const tarjeta = h.slice(i, i + 2000).toLowerCase();
  assert.ok(tarjeta.includes("no lo hemos probado"),
    "La tarjeta del Fire TV Stick ha perdido el aviso de que no está probado.\n" +
    "Si es que ya se probó, quita también este test. Si no, devuélvelo.");
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: FAIL en «hay una tarjeta por familia» listando las cinco, y FAIL en el del Fire Stick.

- [ ] **Step 3: Escribir las cinco tarjetas**

En `admin.html`, dentro de `page-help`, **después** de la tarjeta de conectar y **antes** de «Extensión de Chrome»:

```html
  <div class="card">
    <div class="card-title">Con qué reproducir</div>
    <div style="font-size:13px;color:var(--muted);line-height:1.9;margin-bottom:12px">
      Cualquier pantalla con navegador vale para empezar. Lo que cambia entre unas y
      otras es cuánto aguantan encendidas. Abre la que tengas:
    </div>

    <details class="aparato">
      <summary>Tablet o móvil</summary>
      <p>Lo más fácil y lo que mejor va para probar. Abre el navegador, entra en
      <code>/pair</code>, escribe el PIN y listo. No hay que instalar nada.</p>
      <p>Ponle que no se apague la pantalla en los ajustes del propio aparato, y
      enchufado a la corriente.</p>
    </details>

    <details class="aparato">
      <summary>Televisor con su propio navegador</summary>
      <p>Sirve para empezar y va bien en una pantalla que se apaga por la noche.
      Pero <strong>el navegador de fábrica de un televisor no está pensado para
      tener una página abierta doce horas seguidas</strong>, y cuando falla no
      avisa: cierra la página y deja el escaparate en negro.</p>
      <p><strong style="color:var(--text)">Pasó de verdad en una tienda, con un LG:</strong>
      el navegador se cerraba solo cada dos minutos. Se descartaron el protector de
      pantalla, el ahorro de energía, el HDMI-CEC y el propio programa —se probó con
      la versión corregida y siguió igual—. <strong>Se resolvió cambiando el aparato,
      no la página.</strong></p>
      <p>Si la pantalla tiene que estar encendida todo el día, vete a una cajita.</p>
    </details>

    <details class="aparato">
      <summary>Caja Android TV</summary>
      <p><strong style="color:var(--text)">Es lo recomendado para un escaparate.</strong>
      Una caja barata enchufada al HDMI: el televisor pasa a ser solo la pantalla.
      Dos formas de montarla:</p>
      <p><strong style="color:var(--text)">Con la app de InTeks</strong> (un archivo
      <code>.apk</code>, pídela). Encuentra el ordenador sola —no hay que escribir
      ninguna dirección con el mando—, arranca al encender la caja y enciende el
      televisor. Si el ordenador cambia de dirección, lo vuelve a buscar.</p>
      <ul style="margin:0 0 10px 18px">
        <li>Para tocar la caja —cambiar el wifi, entrar en sus ajustes—:
        <strong>cinco veces seguidas la tecla «atrás»</strong>. Se aparta cinco
        minutos y vuelve sola.</li>
        <li>Si alguna vez hace falta escribir la dirección a mano, pulsa
        <strong>OK</strong> mientras pone «Buscando…».</li>
      </ul>
      <p><strong style="color:var(--text)">Con Fully Kiosk Browser</strong> (unos 7 €,
      pago único). Copia el enlace directo de la pantalla desde su tarjeta y pégalo en
      <em>Start URL</em>. Activa <em>Keep Screen On</em>, <em>Start on Boot</em> y
      <em>Kiosk Mode</em>, y <strong>desactiva el salvapantallas</strong> de la propia
      app, que viene puesto y taparía el contenido.</p>
      <p>Dos cosas que despistan: estas cajas <strong>no tienen táctil</strong> aunque
      el televisor sí lo tenga, y hay que usar <strong>la IP</strong> y nunca
      <code>signage.local</code>.</p>
    </details>

    <details class="aparato">
      <summary>Amazon Fire TV Stick</summary>
      <p>Por dentro es Android, así que en principio vale lo mismo que para una caja
      Android: se le instalan aplicaciones desde un ordenador y le aplican las mismas
      pegas —la IP en vez de <code>signage.local</code>, y nada de táctil—.</p>
      <p><strong style="color:var(--text)">Aviso honesto: no lo hemos probado todavía.</strong>
      No sabemos si la app de InTeks arranca bien ahí. Si vas a montar una tienda con
      uno, pruébalo antes en casa; y si funciona, dilo y quitamos este aviso.</p>
    </details>

    <details class="aparato">
      <summary>Mini PC</summary>
      <p>El más caro y el más previsible. Un ordenador pequeño con el navegador en
      modo pantalla completa arrancando solo. Si ya tienes que poner un ordenador
      para el programa, a veces sale a cuenta que sea el mismo.</p>
    </details>
  </div>
```

- [ ] **Step 4: Ver los tests en verde**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add admin.html tests/ayuda-aparatos.test.js
git commit -m "El panel: la ayuda explica con que reproducir, por familia de aparato"
```

---

### Task 3: La tarjeta de diagnóstico

**Files:**
- Modify: `admin.html` (dentro de `page-help`)
- Modify: `tests/ayuda-aparatos.test.js`

**Interfaces:**
- Consumes: `ayuda()` de la Task 1.
- Produces: nada que consuman las siguientes.

- [ ] **Step 1: Añadir el test**

Añadir a `tests/ayuda-aparatos.test.js`:

```js
const SINTOMAS = [
  "Faltan trozos por los bordes",
  "No llena la pantalla",
  "No carga en la caja Android",
  "No responde al tacto",
  "Desde otro aparato no entra"
];

test("la ayuda cubre los fallos que ya han pasado en tienda", () => {
  const h = ayuda();
  const faltan = SINTOMAS.filter(s => !h.includes(s));
  assert.deepStrictEqual(faltan, [],
    "Faltan sintomas en la tarjeta de diagnostico:\n  " + faltan.join("\n  "));
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: FAIL listando los cinco síntomas.

- [ ] **Step 3: Escribir la tarjeta**

En `admin.html`, justo después de la tarjeta «Con qué reproducir»:

```html
  <div class="card">
    <div class="card-title">Si algo se ve mal</div>
    <div style="font-size:13px;color:var(--muted);line-height:1.9">

      <details class="aparato">
        <summary>Faltan trozos por los bordes</summary>
        <p>El televisor está recortando la imagen; es cosa suya y muchos lo hacen.
        En la ventana de <strong>Playlist</strong> de esa pantalla sube el
        <strong>margen de seguridad</strong> (de 0 a 5 %). Súbelo solo en la pantalla
        que lo necesite y lo justo: el margen también quita sitio.</p>
      </details>

      <details class="aparato">
        <summary>No llena la pantalla, o la letra sale diminuta</summary>
        <p>Le pasaba a las cajas con navegador antiguo: se saltaban en silencio medio
        centenar de reglas de estilo. <strong>Arreglado en la versión 1.0.33</strong>
        — actualiza el programa y la pantalla se recarga sola.</p>
      </details>

      <details class="aparato">
        <summary>No carga en la caja Android</summary>
        <p>Usa <strong>la IP</strong> del ordenador, nunca <code>signage.local</code>.
        Android no resuelve esos nombres; iPhone y Mac sí, y por eso el mismo enlace
        funciona en un móvil y se queda cargando para siempre en la caja. Parece un
        problema de red y es de nombres.</p>
      </details>

      <details class="aparato">
        <summary>No responde al tacto</summary>
        <p>Las cajas de TV no tienen táctil aunque el televisor sí lo tenga. No es un
        fallo. Si necesitas que alguien toque la pantalla, usa una tablet.</p>
      </details>

      <details class="aparato">
        <summary>Desde otro aparato no entra, pero en el ordenador va</summary>
        <p>Es el cortafuegos de Windows. El instalador crea la regla desde la versión
        1.0.14; si la instalación es más antigua, reinstala.</p>
        <p>Y ojo con la prueba: abrir la dirección <strong>desde el propio ordenador
        no demuestra nada</strong>, porque ese tráfico no pasa por el filtro. Hace
        falta probar desde otro aparato.</p>
      </details>

    </div>
  </div>
```

- [ ] **Step 4: Ver el test en verde**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: PASS, 5 tests

- [ ] **Step 5: Commit**

```bash
git add admin.html tests/ayuda-aparatos.test.js
git commit -m "El panel: la ayuda incluye los fallos que ya han pasado en tienda"
```

---

### Task 4: Que las tarjetas plegables se vean como el resto

**Files:**
- Modify: `admin.html` (el `<style>`, junto al resto de reglas de `.card`)

**Interfaces:**
- Consumes: los `<details class="aparato">` de las tareas 2 y 3.
- Produces: nada.

- [ ] **Step 1: Añadir el CSS**

En `admin.html`, en el `<style>`, después de la regla `.card-title`:

```css
/* Tarjetas plegables de la ayuda. Se usa <details>, que es nativo desde Chrome
   12, en vez de un acordeon a mano: el panel no tenia ningun plegable y no
   merece funciones nuevas en un archivo de 226 KB para algo que ya hace el
   navegador. Van cerradas al abrir la pagina porque esto se consulta desde el
   movil, de pie y delante de la pantalla que falla: seis familias abiertas de
   golpe serian un muro de scroll. */
.aparato{border:1px solid var(--b);border-radius:var(--r);margin-bottom:8px;background:var(--s2)}
.aparato>summary{cursor:pointer;padding:11px 14px;font-weight:600;color:var(--text);font-size:13px;list-style:none}
.aparato>summary::-webkit-details-marker{display:none}
.aparato>summary::before{content:"▸ ";color:var(--accent)}
.aparato[open]>summary::before{content:"▾ "}
.aparato[open]>summary{border-bottom:1px solid var(--b)}
.aparato>p,.aparato>ul{margin:10px 14px;font-size:13px;line-height:1.8}
.aparato code{background:var(--s1);padding:2px 6px;border-radius:4px;font-family:monospace}
```

- [ ] **Step 2: Los objetivos táctiles en móvil**

En el bloque `@media (max-width:560px)` (línea ~254), añadir:

```css
  /* 44 px de alto para el dedo, como el resto de botones del panel en movil. */
  .aparato>summary{padding:14px;min-height:44px;box-sizing:border-box}
```

- [ ] **Step 3: Comprobar que nada más se rompió**

Run: `npm test 2>&1 | tail -6`
Expected: 0 fallos

- [ ] **Step 4: Commit**

```bash
git add admin.html
git commit -m "El panel: estilo de las tarjetas plegables de la ayuda"
```

---

### Task 5: El manual, a resumen

**Files:**
- Modify: `MANUAL.md` (la sección *Con qué reproducir: el televisor o una cajita*, líneas ~58-117)
- Modify: `tests/ayuda-aparatos.test.js`

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: Añadir el test**

Añadir a `tests/ayuda-aparatos.test.js`:

```js
const MANUAL = path.join(__dirname, "..", "MANUAL.md");

/**
 * No puede haber dos textos largos sobre lo mismo.
 *
 * Este proyecto ya se ha llevado ese golpe dos veces -las divisas duplicadas
 * entre libreria y playlist, y CURRENCY_DB entre admin.html y parser.js-, y sin
 * paso de compilacion no hay forma de generar uno a partir del otro. Asi que el
 * texto largo vive en el panel y el manual remite a el.
 */
test("el manual no duplica la guia de aparatos, remite al panel", () => {
  const m = fs.readFileSync(MANUAL, "utf8");
  const i = m.indexOf("## Con qué reproducir");
  assert.ok(i >= 0, "no se encuentra la sección de aparatos en MANUAL.md");
  const j = m.indexOf("\n## ", i + 5);
  const seccion = m.slice(i, j > 0 ? j : m.length);

  assert.ok(seccion.toLowerCase().includes("ayuda"),
    "La sección del manual debe remitir a la Ayuda del panel.");
  assert.ok(seccion.split("\n").length < 30,
    `La sección del manual ha vuelto a crecer (${seccion.split("\n").length} líneas).\n` +
    "El texto largo va en la Ayuda del panel; aquí solo el resumen.");
});
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: FAIL — la sección tiene unas 60 líneas.

- [ ] **Step 3: Recortar la sección**

En `MANUAL.md`, sustituir toda la sección *Con qué reproducir: el televisor o una cajita* —incluidas sus subsecciones *Cómo se deja montada* y *La app propia de InTeks*— por:

```markdown
## Con qué reproducir: el televisor o una cajita

Cualquier pantalla con navegador vale para empezar. Lo que cambia entre unas y
otras es cuánto aguantan encendidas: **el navegador de fábrica de un televisor
no está pensado para tener una página abierta doce horas seguidas**, y cuando
falla no avisa —cierra la página y deja el escaparate en negro—. Pasó con un LG
en una tienda y se resolvió cambiando el aparato, no la página.

Para un escaparate que está encendido todo el día, lo recomendado es una **caja
Android barata** enchufada al HDMI, con la app de InTeks o con Fully Kiosk.

> **La guía completa está en el panel**, en **Ayuda → Con qué reproducir**: una
> ficha por tipo de aparato —tablet, televisor, caja Android, Fire TV Stick,
> mini PC— con cómo dejarlo montado y las pegas de cada uno. Está ahí y no aquí
> para que haya un solo texto que mantener, y para tenerlo a mano cuando estás
> delante de la pantalla que falla.
```

- [ ] **Step 4: Ver el test en verde**

Run: `node --test tests/ayuda-aparatos.test.js`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add MANUAL.md tests/ayuda-aparatos.test.js
git commit -m "El manual: la guia de aparatos se va al panel y aqui queda el resumen"
```

---

### Task 6: Verificar renderizando

**Files:**
- Ninguno. Es comprobación.

> **Por qué:** los tests comprueban que el texto **está**. Que se **lea** —que las tarjetas plieguen, que quepan en un móvil, que el `<summary>` no se salga de la caja— no lo caza ningún test. En este proyecto un fallo visual se renderiza.

- [ ] **Step 1: Extraer la página de Ayuda a una página suelta**

`SP` es una carpeta temporal cualquiera fuera del repositorio (el scratchpad de
la sesión, o `mkdir -p /tmp/arnes-ayuda`). No se escribe nada dentro del
proyecto: esto es un arnés, no un artefacto.

```bash
SP=/tmp/arnes-ayuda && mkdir -p "$SP"
python - "$SP/ayuda.html" <<'PYEOF'
import re, sys, pathlib
t = pathlib.Path("admin.html").read_text(encoding="utf-8")
estilo = re.search(r'<style>([\s\S]*?)</style>', t).group(1)
a = t.index('<div class="page" id="page-help">')
b = min(i for i in (t.index('<div class="page"', a+10), t.index('<div class="modal-bd"', a+10)) if i > 0)
pagina = f"""<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Space+Mono:wght@400;700&display=swap">
<style>{estilo}
  body{{margin:0;padding:16px}} .page{{display:block !important}}
</style>
{t[a:b]}"""
pathlib.Path(sys.argv[1]).write_text(pagina, encoding="utf-8")
print("ayuda extraida")
PYEOF
cd "$SP" && python -m http.server 8097 --bind 127.0.0.1 &
```

- [ ] **Step 2: Fotografiar en escritorio y en móvil**

```bash
chrome --headless=new --disable-gpu --virtual-time-budget=9000 \
  --window-size=1100,900 --hide-scrollbars --screenshot="$SP/ayuda-1100.png" \
  "http://127.0.0.1:8097/ayuda.html"
```

Para los 560 px **no vale `--window-size=560`**: Chrome headless impone un ancho mínimo de ventana de ~504 px, así que el viewport no baja de ahí y mides un ancho que no es el que pediste. Hay que meterlo en un **iframe** del ancho exacto, igual que se hizo al fotografiar el panel responsive. Guardar como `$SP/movil.html`:

```html
<!doctype html><meta charset="utf-8"><title>ayuda a 560</title>
<style>body{margin:0;background:#333}iframe{width:560px;height:1400px;border:0;display:block}</style>
<iframe src="ayuda.html"></iframe>
```

y fotografiarlo:

```bash
chrome --headless=new --disable-gpu --virtual-time-budget=9000 \
  --window-size=600,1450 --hide-scrollbars --screenshot="$SP/ayuda-560.png" \
  "http://127.0.0.1:8097/movil.html"
```

- [ ] **Step 3: Mirar las capturas y comprobar**

| Qué | Criterio |
|---|---|
| Las tarjetas | Cerradas al cargar, con el triángulo `▸` naranja |
| El `<summary>` | En una línea, sin desbordar la caja |
| A 560 px | El texto no se sale y los títulos son tocables |
| La tarjeta de conectar | Sin rastro de `python server.py` ni de `:8080` |

- [ ] **Step 4: Parar el servidor de pruebas**

Matar **solo** el proceso que escucha en el 8097, por PID. No usar `taskkill` por nombre de imagen: mataría también el servidor real de InTeks si corriera con el mismo ejecutable.

- [ ] **Step 5: Commit** (solo si hubo arreglos)

```bash
git add admin.html
git commit -m "El panel: ajustes de la ayuda tras verla renderizada"
```

---

### Task 7: Versión, changelog y contexto

**Files:**
- Modify: `CHANGELOG.md`, `CLAUDE_CODE_PROMPT.md`
- Modify (por script): `server.py`, `installer/setup.iss`, `package.json`, `android/app/build.gradle.kts`

- [ ] **Step 1: Subir la versión**

```bash
powershell -ExecutionPolicy Bypass -File tools\subir-version.ps1 1.0.34
```

- [ ] **Step 2: CHANGELOG**

Entrada `## 1.0.34 — 2026-09-01`, apartado **Nuevo**, escrita para quien atiende la tienda:

- **La ayuda del panel explica con qué reproducir.** Una ficha por tipo de
  aparato —tablet, televisor, caja Android, Fire TV Stick, mini PC— con cómo
  dejarlo montado y las pegas de cada uno, más una lista de «si algo se ve mal»
  con los fallos que ya han pasado en tienda.

Y apartado **Corregido**:

- **La ayuda de conectar pantallas explicaba un flujo que ya no existe** (pedía
  ejecutar Python a mano y usar el puerto 8080). Ahora explica el
  emparejamiento por PIN, que es como funciona.

- [ ] **Step 3: `CLAUDE_CODE_PROMPT.md`**

En la sección *Secciones del admin*, anotar que **Ayuda es ahora el texto largo
sobre aparatos y `MANUAL.md` el resumen**, y que `tests/ayuda-aparatos.test.js`
vigila tres cosas: que no vuelvan las instrucciones caducadas, que estén las
seis fichas, y que **el Fire TV Stick siga marcado como no probado**. Actualizar
la línea `Actualizado:` y el recuento de tests de `npm test`.

- [ ] **Step 4: Todo verde**

Run: `npm test 2>&1 | tail -6`
Expected: 0 fallos

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "1.0.34: la ayuda del panel explica con que reproducir"
```

---

## Notas para quien lo ejecute

- **No inventes pasos de ningún modelo.** Si te tienta escribir «en un Samsung
  ve a Ajustes → tal», para: no está comprobado. La ayuda vale justo lo que vale
  su parte más floja.
- **El aviso del Fire TV Stick no se quita** hasta que alguien lo pruebe de
  verdad. Y cuando se quite, se quita también su test, en el mismo commit.
- **Siete tests leen `admin.html`** extrayendo bloques suyos. Ejecuta `npm test`
  entero después de cada cambio, no solo el de la ayuda.
- **Cero JavaScript nuevo.** Si te ves escribiendo una función para plegar algo,
  es que no estás usando `<details>`.
