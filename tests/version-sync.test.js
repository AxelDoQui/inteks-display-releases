/**
 * La versión está escrita en tres sitios que no se hablan entre sí:
 * server.py (lo que reporta el programa en marcha), installer/setup.iss (lo que
 * ve Windows en "Programas instalados") y package.json.
 *
 * Si divergen, el panel de una tienda dice una versión y el instalador otra, y
 * en cuanto haya varias tiendas instaladas eso convierte cualquier soporte en
 * adivinanza: no se sabe qué codigo esta corriendo realmente ese equipo.
 *
 * Al subir de version hay que tocar los tres. Este test lo recuerda.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..");
const leer = f => fs.readFileSync(path.join(ROOT, f), "utf8");

function unico(archivo, patron, que) {
  const m = leer(archivo).match(patron);
  if (!m) throw new Error(`No se encuentra ${que} en ${archivo} (patrón ${patron}).`);
  return m[1];
}

const enServer = () => unico("server.py", /^APP_VERSION\s*=\s*"([^"]+)"/m, "APP_VERSION");
const enSetup = () => unico("installer/setup.iss", /^AppVersion=(.+)$/m, "AppVersion");
const enSetupNombre = () =>
  unico("installer/setup.iss", /^OutputBaseFilename=.*_v([0-9.]+)\s*$/m, "OutputBaseFilename");
const enPackage = () => JSON.parse(leer("package.json")).version;
const enAndroid = () =>
  unico("android/app/build.gradle.kts", /versionName\s*=\s*"([^"]+)"/, "versionName");

test("el servidor y el instalador dicen la misma versión", () => {
  assert.strictEqual(enServer(), enSetup(),
    "server.py APP_VERSION y setup.iss AppVersion no coinciden");
});

test("el nombre del .exe lleva esa misma versión", () => {
  // Si no, se acumulan instaladores con el mismo nombre y contenido distinto.
  assert.strictEqual(enSetupNombre(), enServer(),
    "OutputBaseFilename no coincide con APP_VERSION");
});

test("package.json va al mismo paso", () => {
  assert.strictEqual(enPackage(), enServer(),
    "package.json version no coincide con APP_VERSION");
});

test("la app Android va al mismo paso", () => {
  // Sin esto el APK saldria con la version que le tocara y no habria forma de
  // saber que codigo tiene instalado una tienda en su caja de TV.
  assert.strictEqual(enAndroid(), enServer(),
    "android/app/build.gradle.kts versionName no coincide con APP_VERSION");
});

test("la versión tiene forma de versión", () => {
  assert.match(enServer(), /^\d+\.\d+\.\d+$/);
});
