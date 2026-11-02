import test from "node:test";
import assert from "node:assert/strict";
import { anadirPc, listarPcs, quitarPc, enlazar } from "../src/pcs.js";
import { crearKv } from "./kv-falso.js";
import { crearCfFalso } from "./cf-falso.js";

const mundo = (opc) => ({ kv: crearKv(), cf: crearCfFalso(opc) });

test("añadir PC devuelve un PIN y deja el PC pendiente", async () => {
  const { kv } = mundo();
  const r = await anadirPc({ nombre: "tienda1", kv });
  assert.equal(r.estado, 200); assert.match(r.cuerpo.pin, /^\d{6}$/);
  assert.equal(JSON.parse(await kv.get("pc:tienda1")).estado, "pendiente");
  assert.equal(await kv.get("pin:" + r.cuerpo.pin), "tienda1");
});
test("añadir: nombre inválido o reservado se rechaza", async () => {
  const { kv } = mundo();
  assert.equal((await anadirPc({ nombre: "Tienda 1", kv })).estado, 400);
  assert.equal((await anadirPc({ nombre: "cuenta", kv })).estado, 400);
});
test("añadir: pendiente se rehace con PIN nuevo (el viejo deja de valer); activo no se repite", async () => {
  const { kv, cf } = mundo();
  const a = await anadirPc({ nombre: "t1", kv });
  const b = await anadirPc({ nombre: "t1", kv });
  assert.equal(b.estado, 200);
  if (a.cuerpo.pin !== b.cuerpo.pin) assert.equal(await kv.get("pin:" + a.cuerpo.pin), null);
  assert.equal((await enlazar({ pin: b.cuerpo.pin, puerto: 80, ip: "1.1.1.1", kv, cf })).estado, 200);
  assert.equal((await anadirPc({ nombre: "t1", kv })).estado, 409);
});
test("canjear PIN: crea túnel, configura, crea DNS y devuelve el token", async () => {
  const { kv, cf } = mundo();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "tienda1", kv });
  const r = await enlazar({ pin, puerto: 9000, ip: "1.1.1.1", kv, cf });
  assert.equal(r.estado, 200);
  assert.deepEqual(r.cuerpo, { ok: true, token: "TOKEN-t1", hostname: "tienda1.inteksdisplay.com" });
  assert.equal(cf.estado.tuneles.get("t1").host, "tienda1.inteksdisplay.com");
  assert.equal(cf.estado.tuneles.get("t1").puerto, 9000);
  const pc = JSON.parse(await kv.get("pc:tienda1"));
  assert.equal(pc.estado, "activo"); assert.equal(pc.pin, null);
});
test("un PIN solo vale una vez", async () => {
  const { kv, cf } = mundo();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  assert.equal((await enlazar({ pin, ip: "1.1.1.1", kv, cf })).estado, 200);
  assert.equal((await enlazar({ pin, ip: "1.1.1.1", kv, cf })).estado, 400);
});
test("PIN caducado, inexistente o mal formado: mismo mensaje genérico", async () => {
  let t = 0; const kv = crearKv(() => t); const cf = crearCfFalso();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv, ahora: () => t });
  t += 601 * 1000;
  const a = await enlazar({ pin, ip: "1.1.1.1", kv, cf, ahora: () => t });
  const b = await enlazar({ pin: "000000", ip: "1.1.1.2", kv, cf, ahora: () => t });
  const c = await enlazar({ pin: "abc", ip: "1.1.1.3", kv, cf, ahora: () => t });
  for (const r of [a, b, c]) { assert.equal(r.estado, 400); assert.equal(r.cuerpo.error, "PIN no válido o caducado"); }
});
test("tras 5 fallos desde la misma IP responde 429, aunque luego acierte", async () => {
  const { kv, cf } = mundo();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  const malo = pin === "999999" ? "999998" : "999999";
  for (let i = 0; i < 5; i++) await enlazar({ pin: malo, ip: "6.6.6.6", kv, cf });
  assert.equal((await enlazar({ pin, ip: "6.6.6.6", kv, cf })).estado, 429);
  assert.equal((await enlazar({ pin, ip: "7.7.7.7", kv, cf })).estado, 200);
});
test("si falla el DNS se deshace el túnel y el PIN sigue valiendo", async () => {
  const kv = crearKv(); const cf = crearCfFalso({ falla: "crearDns" });
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  const r = await enlazar({ pin, ip: "1.1.1.1", kv, cf });
  assert.equal(r.estado, 502);
  assert.equal(cf.estado.tuneles.size, 0);
  assert.equal(JSON.parse(await kv.get("pc:t1")).estado, "pendiente");
  assert.equal(await kv.get("pin:" + pin), "t1");
});
test("si falla el token se deshacen túnel y DNS", async () => {
  const kv = crearKv(); const cf = crearCfFalso({ falla: "tokenTunel" });
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  assert.equal((await enlazar({ pin, ip: "1.1.1.1", kv, cf })).estado, 502);
  assert.equal(cf.estado.tuneles.size, 0); assert.equal(cf.estado.dns.size, 0);
});
test("listar: activos con su estado, pendientes con su PIN", async () => {
  const { kv, cf } = mundo();
  const a = await anadirPc({ nombre: "t1", kv }); await enlazar({ pin: a.cuerpo.pin, ip: "1.1.1.1", kv, cf });
  await anadirPc({ nombre: "t2", kv });
  const { cuerpo } = await listarPcs({ kv, cf });
  const t1 = cuerpo.pcs.find((p) => p.nombre === "t1"), t2 = cuerpo.pcs.find((p) => p.nombre === "t2");
  assert.equal(t1.estado, "activo"); assert.equal(t1.enLinea, true); assert.equal(t1.hostname, "t1.inteksdisplay.com");
  assert.equal(t2.estado, "pendiente"); assert.match(t2.pin, /^\d{6}$/);
});
test("quitar: borra DNS, túnel y la entrada; si Cloudflare falla, no borra la entrada", async () => {
  const kv = crearKv(); const cf = crearCfFalso();
  const a = await anadirPc({ nombre: "t1", kv }); await enlazar({ pin: a.cuerpo.pin, ip: "1.1.1.1", kv, cf });
  const malo = crearCfFalso({ falla: "borrarTunel" });
  assert.equal((await quitarPc({ nombre: "t1", kv, cf: malo })).estado, 502);
  assert.notEqual(await kv.get("pc:t1"), null);
  assert.equal((await quitarPc({ nombre: "t1", kv, cf })).estado, 200);
  assert.equal(await kv.get("pc:t1"), null); assert.equal(cf.estado.tuneles.size, 0); assert.equal(cf.estado.dns.size, 0);
  assert.equal((await quitarPc({ nombre: "t1", kv, cf })).estado, 404);
});
