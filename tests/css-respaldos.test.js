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
  // Fuera los comentarios ANTES de trocear: este CSS lleva comentarios largos
  // entre reglas, y sin quitarlos el selector sale con el comentario pegado.
  const css = src.slice(a + "<style>".length, b).replace(/\/\*[\s\S]*?\*\//g, "");

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

/**
 * La trampa de las custom properties.
 *
 * `--fx-title-size:clamp(...)` NO falla al declararse: una custom property
 * admite cualquier secuencia de tokens aunque el navegador no la entienda. El
 * fallo llega donde se USA: al sustituir, `font-size:clamp(...)` es invalida y
 * la propiedad se queda con lo heredado o con su valor inicial.
 *
 * Y eso no es un detalle cosmetico: `.mod-fx-logo{height:var(--fx-title-size)}`
 * se quedaria con `height:auto`, que es exactamente el fallo ya documentado del
 * logo saliendo a 99px donde su CSS pedia 20, comiendose el 26% del ancho y
 * dejando el titulo en «TIPOS DE…».
 *
 * Quien revise esto mirando solo el :root no encontrara nada roto.
 */
test("usar una variable con sintaxis moderna dentro tambien lleva respaldo", () => {
  const todas = reglas();
  const sospechosas = new Set();
  for (const r of todas) {
    for (const d of r.decls) {
      if (d.prop.startsWith("--") && FUNCIONES_MODERNAS.test(d.valor)) {
        sospechosas.add(d.prop);
      }
    }
  }
  const fallos = [];
  for (const r of todas) {
    r.decls.forEach((d, i) => {
      if (d.prop.startsWith("--")) return;
      const usa = [...sospechosas].some(v => d.valor.includes("var(" + v));
      if (!usa) return;
      if (!tieneRespaldoAntes(r.decls, i)) {
        fallos.push(`${r.selector} { ${d.prop}: ${d.valor} }`);
      }
    });
  }
  assert.deepStrictEqual(fallos, [],
    "Estas variables llevan clamp()/min()/max() dentro: " + [...sospechosas].join(", ") +
    "\nEn Chrome 62 la sustitucion es invalida y la propiedad se queda sin valor.\n" +
    "Pon delante la misma propiedad con el termino de en medio:\n  " + fallos.join("\n  "));
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
 * hijos, dentro de un @supports para no sumarlos tambien en los navegadores
 * modernos. Como eso no se puede comprobar leyendo la regla, se lleva una lista
 * explicita. Añadir una entrada aqui obliga a mirar si los hijos ya se separan.
 */
const FLEX_CON_GAP_REVISADOS = [
  ".mod-fx-header",   // margen compensado
  ".fx-row",          // margen compensado
  ".weather-details", // margen compensado
  "#waiting",         // margen compensado
  ".mod-fx-rows",           // gap:0, no hay nada que compensar
  ".mod-fx-header.apilado"  // row-gap con flex-wrap: se acepta perderlo, es 1vh
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
 * imagen sin aspect-ratio se dibuja con su proporcion natural — que es justo
 * lo que se le estaba pidiendo. La degradacion es aceptable y no merece
 * inventarle un respaldo con el truco del padding, que ademas romperia el
 * `object-fit` que llevan al lado.
 *
 * La lista existe para que un aspect-ratio nuevo sobre algo que NO sea una
 * imagen obligue a pararse: ahi si dejaria un hueco de alto cero.
 *
 * OJO: este test solo ve el <style>. La bandera lleva el suyo en un `style=`
 * en linea dentro de una plantilla de JS: `grep aspect-ratio player.html`.
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
