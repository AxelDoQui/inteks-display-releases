import test from "node:test";
import assert from "node:assert/strict";
import { manejar } from "../src/index.js";
import { crearKv } from "./kv-falso.js";
import { crearCfFalso } from "./cf-falso.js";

const env = { PCS: crearKv(), DOMINIO: "inteksdisplay.com", ACCESS_EQUIPO: "e", ACCESS_AUD: "a", ACCESS_CORREO: "x@y.z" };
const deps = (acceso) => ({ cf: crearCfFalso(), acceso: async () => acceso });
const pet = (ruta, metodo = "GET", cuerpo, ip = "5.5.5.5") =>
  new Request("https://cuenta.inteksdisplay.com" + ruta, {
    method: metodo, headers: { "CF-Connecting-IP": ip, "Content-Type": "application/json" },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });

test("la web y la API de la cuenta exigen Access: sin él, 403", async () => {
  for (const [r, m] of [["/", "GET"], ["/api/pcs", "GET"], ["/api/pcs", "POST"], ["/api/pcs/t1", "DELETE"]])
    assert.equal((await manejar(pet(r, m, m === "POST" ? { nombre: "t1" } : undefined), env, deps(false))).status, 403, r);
});
test("con Access: la página es HTML y la lista responde", async () => {
  const d = deps(true);
  const home = await manejar(pet("/"), env, d);
  assert.equal(home.status, 200); assert.match(home.headers.get("content-type"), /text\/html/);
  const lista = await manejar(pet("/api/pcs"), env, d); assert.equal(lista.status, 200);
  assert.deepEqual((await lista.json()).pcs, []);
});
test("flujo completo: añadir → canjear (sin Access) → listar → quitar", async () => {
  const cf = crearCfFalso();
  const conAcceso = { cf, acceso: async () => true }, sinAcceso = { cf, acceso: async () => false };
  const alta = await (await manejar(pet("/api/pcs", "POST", { nombre: "tienda1" }), env, conAcceso)).json();
  const canje = await manejar(pet("/api/enlazar", "POST", { pin: alta.pin, puerto: 80 }), env, sinAcceso);   // público
  assert.equal(canje.status, 200); assert.equal((await canje.json()).hostname, "tienda1.inteksdisplay.com");
  const lista = await (await manejar(pet("/api/pcs"), env, conAcceso)).json();
  assert.equal(lista.pcs[0].estado, "activo");
  assert.equal((await manejar(pet("/api/pcs/tienda1", "DELETE"), env, conAcceso)).status, 200);
});
test("/api/enlazar: cuerpo roto → 400; método GET → 405; ruta desconocida → 404", async () => {
  const roto = new Request("https://x/api/enlazar", { method: "POST", body: "no es json", headers: { "CF-Connecting-IP": "9.9.9.9" } });
  assert.equal((await manejar(roto, env, deps(false))).status, 400);
  assert.equal((await manejar(pet("/api/enlazar"), env, deps(false))).status, 405);
  assert.equal((await manejar(pet("/nada"), env, deps(true))).status, 404);
});
