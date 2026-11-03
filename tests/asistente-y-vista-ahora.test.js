/**
 * Asistente de primer arranque, guía de la LG y «Ver ahora» del panel.
 * Son piezas de pantalla: se comprueba que existen, que el script del panel sigue
 * siendo JavaScript válido y que el asistente solo sale cuando toca.
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const leer = (f) => fs.readFileSync(path.join(__dirname, "..", f), "utf8");
const admin = leer("admin.html");

test("el script del panel sigue siendo JavaScript válido", () => {
  const scripts = [...admin.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  assert.ok(scripts.length >= 1);
  scripts.forEach((m) => assert.doesNotThrow(() => new vm.Script(m[1])));
});

test("tras crear la contraseña se va al asistente; entrar normal, no", () => {
  const l = leer("login.html");
  assert.ok(l.includes('SETUP ? "/admin.html?asistente=1" : "/admin.html"'));
});

test("el asistente tiene sus tres pasos y solo se abre con ?asistente o desde Ajustes", () => {
  ["asist-modal", "asist-1", "asist-2", "asist-3", "asist-pin"].forEach((id) =>
    assert.ok(admin.includes(`id="${id}"`), id));
  assert.ok(/URLSearchParams\(location\.search\)\.has\("asistente"\)/.test(admin));
  assert.ok(admin.includes('onclick="asistenteAbrir()"'), "botón en Ajustes");
  // El PIN del asistente va al mismo sitio que el de la tarjeta de Ajustes.
  assert.ok(admin.includes('"/api/acceso-remoto/activar"'));
});

test("la mini-app de la LG se vigila por defecto y la guía explica el reposo", () => {
  assert.ok(/id="lg-vig" checked/.test(admin));
  assert.ok(admin.includes("Salvapantallas / Modo ambiente"));
  assert.ok(admin.includes("IP fija"));
});

test("«Ver ahora» existe en la tarjeta y su ventana usa el reproductor en modo previa", () => {
  assert.ok(admin.includes("onclick=\"verAhora('${sid}')\""));
  assert.ok(admin.includes('id="ahora-modal"'));
  assert.ok(admin.includes("/player.html?preview=1"));
  assert.ok(admin.includes("function cerrarAhora"));
});

test("el instalador avisa de que el acceso remoto se termina en el panel", () => {
  const i = leer("installer/setup.iss");
  assert.ok(i.includes("cuenta.inteksdisplay.com"));
});

test("Ajustes está ordenado en tres bloques y no se pierde ninguna tarjeta", () => {
  const ini = admin.indexOf('id="page-settings"');
  const bloque = admin.slice(ini, admin.indexOf('<div class="page"', ini + 10));
  const grupos = [...bloque.matchAll(/class="aj-grupo">([^<]+)</g)].map((m) => m[1]);
  assert.deepStrictEqual(grupos, ["ESTA INSTALACIÓN", "PANTALLAS", "AVISOS, COPIAS Y ARCHIVOS"]);
  assert.strictEqual((bloque.match(/<div class="card[ "]/g) || []).length, 9);
  ["card-acceso", "card-lg", "set-name", "set-tg-token", "set-newpass"].forEach((id) =>
    assert.ok(bloque.includes(`id="${id}"`), id));
});

test("en móvil las ventanas ocupan todo el ancho aunque lleven ancho propio", () => {
  assert.ok(admin.includes("width:100%!important;max-width:100%!important"));
});
