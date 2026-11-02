/**
 * Tarjeta «Acceso remoto» del panel. admin.html es un HTML monolítico: se extrae el bloque
 * de funciones tal cual está y se ejecuta en un contexto vm con un DOM de mentira.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "admin.html"), "utf8");
const ini = html.indexOf("// ── Acceso remoto (cuenta de InTeks)");
const fin = html.indexOf("async function cargarLgTvs()");
const bloque = html.slice(ini, fin);

function arnes() {
  const els = {};
  const el = (id) => (els[id] ||= { id, style: {}, textContent: "", value: "", disabled: false });
  const llamadas = [];
  const ctx = {
    document: { getElementById: el },
    navigator: {}, setInterval: () => 1, clearInterval: () => {},
    toast: (m, e) => llamadas.push(["toast", m, !!e]),
    confirmar: async () => true,
    fetch: async (u, o) => { llamadas.push(["fetch", u, o && o.body]); return { ok: true, json: async () => ({}) }; },
  };
  vm.createContext(ctx);
  vm.runInContext(bloque, ctx);
  return { ctx, els, llamadas };
}

test("la tarjeta existe y el bloque no usa innerHTML", () => {
  assert.ok(html.includes('id="card-acceso"') && bloque.length > 200);
  assert.ok(!/innerHTML/.test(bloque), "todo lo del servidor va con textContent");
  assert.match(html, /maxlength="6"[^>]*inputmode="numeric"|inputmode="numeric"[^>]*maxlength="6"/);
});

test("sin contraseña de admin avisa y bloquea; sin cloudflared avisa", () => {
  const { ctx, els } = arnes();
  ctx.accesoPintar({ estado: "libre", pasos: [], error: "", disponible: true, password: false, activo: false });
  assert.equal(els["acc-sin-pass"].style.display, "block");
  assert.equal(els["acc-go"].disabled, true);
  ctx.accesoPintar({ estado: "libre", pasos: [], error: "", disponible: false, password: true, activo: false });
  assert.equal(els["acc-no-disp"].style.display, "block");
});

test("activo: enseña la dirección; activando: enseña los pasos; error: el motivo", () => {
  const { ctx, els } = arnes();
  ctx.accesoPintar({ estado: "ok", pasos: [], error: "", disponible: true, password: true, activo: true, hostname: "tienda1.inteksdisplay.com", servicio: true });
  assert.equal(els["acc-url"].textContent, "tienda1.inteksdisplay.com");
  assert.equal(els["acc-activo"].style.display, "block");
  assert.equal(els["acc-form"].style.display, "none");
  ctx.accesoPintar({ estado: "activando", pasos: ["a", "b"], error: "", disponible: true, password: true, activo: false });
  assert.equal(els["acc-pasos"].textContent, "a · b");
  assert.equal(els["acc-go"].disabled, true);
  ctx.accesoPintar({ estado: "error", pasos: [], error: "PIN no válido o caducado", disponible: true, password: true, activo: false });
  assert.match(els["acc-pasos"].textContent, /PIN no válido/);
});

test("activar: un PIN que no son 6 cifras no sale a la red; uno bueno sí", async () => {
  const { ctx, els, llamadas } = arnes();
  els["acc-pin"] = { value: "12a", style: {} };
  await ctx.accesoActivar();
  assert.ok(!llamadas.some((l) => l[0] === "fetch"));
  assert.ok(llamadas.some((l) => l[0] === "toast" && l[2] === true));
  els["acc-pin"].value = "123456";
  await ctx.accesoActivar();
  const f = llamadas.find((l) => l[0] === "fetch" && l[1] === "/api/acceso-remoto/activar");
  assert.deepEqual(JSON.parse(f[2]), { pin: "123456" });
});
