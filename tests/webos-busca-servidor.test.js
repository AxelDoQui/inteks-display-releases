/**
 * La mini-app del LG no se queda esperando una IP vieja: recuerda la última que funcionó y,
 * si ninguna responde, busca el servidor en la misma red. Además tiene que conservar la línea
 * `var SERVIDOR = "...";` que tools/instalar-lg.ps1 reescribe con una expresión regular.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "webos", "index.html"), "utf8");
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];

test("conserva la línea que reescribe el instalador", () => {
  assert.match(html, /var SERVIDOR = "[^"]*";/);
  const ps = fs.readFileSync(path.join(__dirname, "..", "tools", "instalar-lg.ps1"), "utf8");
  assert.ok(ps.includes("var SERVIDOR"));
});

function cargar(respuestas) {
  const abiertas = [];
  const almacen = {};
  class XHR {
    open(_m, u) { this.u = u; }
    send() {
      const base = this.u.replace(/api\/auth-status.*/, "");
      setTimeout(() => {
        if (respuestas[base]) { this.responseText = '{"has_password": true}'; this.onload(); }
        else if (respuestas[base] === false) { this.responseText = "<html>router</html>"; this.onload(); }
        else this.onerror();
      }, 0);
    }
    abort() {}
  }
  const els = {};
  const el = (id) => els[id] || (els[id] = { textContent: "", value: "", style: {}, focus() {} });
  const ctx = {
    XMLHttpRequest: XHR, setTimeout, clearTimeout, JSON, Math, Date, String, RegExp,
    document: { getElementById: el },
    localStorage: { getItem: (k) => almacen[k] || null, setItem: (k, v) => { almacen[k] = v; }, removeItem: (k) => { delete almacen[k]; } },
    location: { replace: (u) => abiertas.push(u) },
  };
  vm.createContext(ctx);
  // Todo menos la llamada final a arrancar(), para controlarla desde el test.
  vm.runInContext(js.replace(/\narrancar\(\);\s*$/, "\n"), ctx);
  return { ctx, abiertas, almacen, els };
}

const esperar = (f) => new Promise((ok, ko) => {
  const t0 = Date.now();
  (function p() {
    if (f()) return ok();
    if (Date.now() - t0 > 3000) return ko(new Error("tiempo agotado"));
    setTimeout(p, 5);
  })();
});

test("si la IP guardada ya no existe, lo encuentra en la misma red y lo recuerda", async () => {
  const h = cargar({ "http://192.168.0.115/": true });
  h.ctx.arrancar();
  await esperar(() => h.abiertas.length);
  assert.deepEqual(h.abiertas, ["http://192.168.0.115/"]);
  assert.equal(h.almacen.inteks_servidor, "http://192.168.0.115/");
});

test("con la última IP buena recordada, va directo", async () => {
  const h = cargar({ "http://10.0.0.7/": true });
  h.almacen.inteks_servidor = "http://10.0.0.7/";
  h.ctx.arrancar();
  await esperar(() => h.abiertas.length);
  assert.deepEqual(h.abiertas, ["http://10.0.0.7/"]);
});

test("el router (contesta sin ser el servidor) no se confunde con él", async () => {
  const h = cargar({ "http://192.168.0.1/": false, "http://192.168.0.115/": true });
  h.ctx.arrancar();
  await esperar(() => h.abiertas.length);
  assert.deepEqual(h.abiertas, ["http://192.168.0.115/"]);
});

test("un enlace escrito a mano se guarda completo (ruta y código) y se abre tal cual", () => {
  const h = cargar({});
  h.ctx.mostrarEditor();
  h.els.en.value = "  midominio.com/visor?c=1234 ";
  h.els.ok.onclick();
  assert.equal(h.almacen.inteks_enlace, "http://midominio.com/visor?c=1234");
  assert.deepEqual(h.abiertas, ["http://midominio.com/visor?c=1234"]);
});

test("con enlace guardado no busca el servidor: abre ese enlace tras unos segundos", async () => {
  const h = cargar({ "http://192.168.0.115/": true });
  h.almacen.inteks_enlace = "https://ejemplo.es/tienda?c=9";
  h.ctx.PLAZO_ENLACE = 100;
  h.ctx.arrancar();
  assert.deepEqual(h.abiertas, []);   // primero deja tiempo para cambiarlo
  await esperar(() => h.abiertas.length);
  assert.deepEqual(h.abiertas, ["https://ejemplo.es/tienda?c=9"]);
});

test("«Cambiar enlace» detiene la apertura y «Automático» vuelve a buscar el servidor", async () => {
  const h = cargar({ "http://192.168.0.115/": true });
  h.almacen.inteks_enlace = "https://ejemplo.es/tienda?c=9";
  h.ctx.PLAZO_ENLACE = 100;
  h.ctx.arrancar();
  h.els.bc.onclick();
  await new Promise((r) => setTimeout(r, 400));
  assert.deepEqual(h.abiertas, []);
  h.els.au.onclick();
  assert.equal(h.almacen.inteks_enlace, undefined);
  await esperar(() => h.abiertas.length);
  assert.deepEqual(h.abiertas, ["http://192.168.0.115/"]);
});
