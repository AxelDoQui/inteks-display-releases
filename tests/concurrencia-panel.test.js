/**
 * Tests del manejo del conflicto (409) al guardar desde el panel.
 *
 * admin.html es un HTML monolítico con el JS inline, así que no hay nada que
 * importar. En vez de copiar la función aquí (una copia se desincroniza al
 * primer cambio y dejaría de probar nada), este arnés EXTRAE saveContentLocal()
 * tal cual está en admin.html y la ejecuta en un contexto vm con fetch falso.
 *
 * Qué se prueba y por qué importa: si otro equipo escribió mientras este panel
 * tenía datos viejos, el servidor rebota con 409. El panel NO puede tragárselo
 * en silencio —el usuario creería que guardó— ni reintentar a lo bruto, que
 * volvería a destruir lo del otro equipo.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");

// ── Extrae saveContentLocal() tal cual está en admin.html
function extraerFuente() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const from = src.indexOf("async function saveContentLocal()");
  const to = src.indexOf("function openPlayer()");
  if (from === -1 || to === -1 || to <= from) {
    throw new Error(
      "No se encuentran saveContentLocal()/openPlayer() en admin.html. " +
      "Si se han renombrado, actualiza los marcadores de este arnés."
    );
  }
  return src.slice(from, to);
}

/**
 * Ejecuta saveContentLocal() contra una respuesta de servidor fingida.
 * Devuelve el registro de lo que hizo: qué se envió, qué avisos salieron,
 * si recargó la página y si volvió a cargar los datos.
 */
async function guardarCon(respuesta, contenido = { items: [], screens: {}, rev: 7 }) {
  const registro = {
    enviado: null, toasts: [], recargas: 0, loadAlls: 0,
  };

  const ctx = {
    content: contenido,
    async fetch(url, opciones) {
      registro.enviado = { url, cuerpo: JSON.parse(opciones.body) };
      return {
        status: respuesta.status,
        ok: respuesta.status >= 200 && respuesta.status < 300,
        json: async () => respuesta.cuerpo,
      };
    },
    // Dependencias reales de la función: si se añade alguna más y no se
    // inyecta aquí, el bloque revienta con ReferenceError.
    toast(msg, isErr) { registro.toasts.push({ msg, isErr: !!isErr }); },
    async loadAll() { registro.loadAlls++; },
    location: { reload() { registro.recargas++; } },
  };
  vm.createContext(ctx);
  vm.runInContext(extraerFuente(), ctx);
  await ctx.saveContentLocal();
  return registro;
}

test("el rev viaja en el cuerpo: es lo que permite detectar el conflicto", async () => {
  const r = await guardarCon({ status: 200, cuerpo: { ok: true } });
  assert.strictEqual(r.enviado.cuerpo.rev, 7,
    "sin rev en el cuerpo el servidor no puede comparar y rechazaría todo");
  assert.strictEqual(r.enviado.url, "/api/content");
});

test("un guardado normal no molesta al usuario", async () => {
  const r = await guardarCon({ status: 200, cuerpo: { ok: true } });
  assert.deepStrictEqual(r.toasts, []);
  assert.strictEqual(r.recargas, 0);
  assert.strictEqual(r.loadAlls, 0);
});

test("ante un 409 de conflicto avisa y recarga los datos", async () => {
  const r = await guardarCon({
    status: 409, cuerpo: { ok: false, error: "rev_conflict", rev: 42 },
  });
  assert.strictEqual(r.toasts.length, 1, "el usuario tiene que enterarse");
  assert.strictEqual(r.toasts[0].isErr, true);
  assert.strictEqual(r.loadAlls, 1, "hay que traer lo que escribió el otro equipo");
  assert.strictEqual(r.recargas, 0, "recargar la página entera aquí sería excesivo");
});

test("el aviso del conflicto dice qué hacer, no solo que algo falló", async () => {
  const r = await guardarCon({
    status: 409, cuerpo: { ok: false, error: "rev_conflict", rev: 42 },
  });
  const msg = r.toasts[0].msg.toLowerCase();
  // "Error al guardar" no orienta a nadie. Se pierde la última acción, así que
  // el mensaje tiene que pedir explícitamente que se repita.
  assert.ok(/repite/.test(msg),
    `el aviso debe pedir repetir la última acción, y dice: "${r.toasts[0].msg}"`);
  assert.ok(/otro equipo/.test(msg),
    `el aviso debe explicar que fue otro equipo, y dice: "${r.toasts[0].msg}"`);
});

test("una pestaña cacheada de una versión anterior recarga en vez de avisar", async () => {
  const r = await guardarCon({
    status: 409, cuerpo: { ok: false, error: "rev_stale_client" },
  });
  assert.strictEqual(r.recargas, 1, "recargar es lo que trae el admin.html nuevo");
  assert.deepStrictEqual(r.toasts, [],
    "no tiene sentido avisar a alguien cuya página está a punto de recargarse");
});

test("un error de verdad del servidor se avisa y no se confunde con un conflicto", async () => {
  const r = await guardarCon({ status: 500, cuerpo: { ok: false } });
  assert.strictEqual(r.toasts.length, 1);
  assert.strictEqual(r.toasts[0].isErr, true);
  assert.strictEqual(r.loadAlls, 0, "un 500 no significa que otro equipo escribiera");
  assert.strictEqual(r.recargas, 0);
});
