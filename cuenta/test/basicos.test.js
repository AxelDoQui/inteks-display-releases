import test from "node:test";
import assert from "node:assert/strict";
import { validarNombre, RESERVADOS } from "../src/nombres.js";
import { generarPin, pinValido, PIN_TTL_S } from "../src/pin.js";
import { bloqueado, anotarFallo, MAX_IP, MAX_GLOBAL } from "../src/limite.js";
import { crearKv } from "./kv-falso.js";

test("nombres válidos", () => {
  for (const n of ["tienda1", "a", "mi-tienda", "t-2-b", "a".repeat(30)]) assert.equal(validarNombre(n), null, n);
});
test("nombres inválidos", () => {
  for (const n of ["", "Tienda", "tienda_1", "-a", "a-", "a b", "a.b", "a".repeat(31), "ñu", null, 5, undefined])
    assert.notEqual(validarNombre(n), null, String(n));
});
test("nombres reservados", () => {
  for (const n of ["cuenta", "www", "mail", "api", "admin", "autodiscover"]) assert.ok(RESERVADOS.has(n), n);
  assert.match(validarNombre("cuenta"), /reservado/);
  assert.match(validarNombre("www"), /reservado/);
});
test("PIN: seis cifras, con ceros delante, y distintos", () => {
  const vistos = new Set();
  for (let i = 0; i < 300; i++) { const p = generarPin(); assert.match(p, /^\d{6}$/); vistos.add(p); }
  assert.ok(vistos.size > 250);
  assert.equal(PIN_TTL_S, 600);
});
test("pinValido", () => {
  assert.equal(pinValido("012345"), true);
  for (const p of ["12345", "1234567", "12345a", "", null, 123456]) assert.equal(pinValido(p), false);
});
test("límite por IP: bloquea al llegar al máximo y otra IP no se ve afectada", async () => {
  const kv = crearKv();
  for (let i = 0; i < MAX_IP - 1; i++) { await anotarFallo(kv, "1.1.1.1"); assert.equal(await bloqueado(kv, "1.1.1.1"), false); }
  await anotarFallo(kv, "1.1.1.1");
  assert.equal(await bloqueado(kv, "1.1.1.1"), true);
  assert.equal(await bloqueado(kv, "2.2.2.2"), false);
});
test("límite por IP: caduca a los 10 minutos", async () => {
  let t = 0; const kv = crearKv(() => t);
  for (let i = 0; i < MAX_IP; i++) await anotarFallo(kv, "1.1.1.1");
  assert.equal(await bloqueado(kv, "1.1.1.1"), true);
  t += 601 * 1000;
  assert.equal(await bloqueado(kv, "1.1.1.1"), false);
});
test("límite global: muchas IPs distintas también bloquean", async () => {
  const kv = crearKv();
  for (let i = 0; i < MAX_GLOBAL; i++) await anotarFallo(kv, "9.9.9." + i);
  assert.equal(await bloqueado(kv, "8.8.8.8"), true);
});
