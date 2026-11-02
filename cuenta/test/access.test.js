import test from "node:test";
import assert from "node:assert/strict";
import { verificarJwt } from "../src/access.js";

const b64u = (b) => Buffer.from(b).toString("base64url");
async function firmar(payload, { kid = "k1", clave } = {}) {
  const cab = b64u(JSON.stringify({ alg: "RS256", kid, typ: "JWT" })), cuerpo = b64u(JSON.stringify(payload));
  const firma = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", clave.privateKey, new TextEncoder().encode(cab + "." + cuerpo));
  return `${cab}.${cuerpo}.${b64u(Buffer.from(firma))}`;
}
async function par() {
  return crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
}
const AHORA = 1_800_000_000;
const base = { iss: "https://axel.cloudflareaccess.com", aud: ["AUD1"], email: "Axel@Example.com", exp: AHORA + 600 };
const opc = (jwks) => ({ equipo: "axel.cloudflareaccess.com", aud: "AUD1", correo: "axel@example.com", jwks, ahora: () => AHORA });

test("acepta un JWT bien firmado, de su equipo, su aud y su correo", async () => {
  const k = await par(); const jwk = { ...(await crypto.subtle.exportKey("jwk", k.publicKey)), kid: "k1" };
  assert.equal(await verificarJwt(await firmar(base, { clave: k }), opc({ keys: [jwk] })), true);
});
test("rechaza firma ajena, aud distinta, correo distinto, caducado, iss distinto y basura", async () => {
  const k = await par(), otra = await par();
  const jwk = { ...(await crypto.subtle.exportKey("jwk", k.publicKey)), kid: "k1" }; const jwks = { keys: [jwk] };
  assert.equal(await verificarJwt(await firmar(base, { clave: otra }), opc(jwks)), false);
  assert.equal(await verificarJwt(await firmar({ ...base, aud: ["X"] }, { clave: k }), opc(jwks)), false);
  assert.equal(await verificarJwt(await firmar({ ...base, email: "otro@x.com" }, { clave: k }), opc(jwks)), false);
  assert.equal(await verificarJwt(await firmar({ ...base, exp: AHORA - 1 }, { clave: k }), opc(jwks)), false);
  assert.equal(await verificarJwt(await firmar({ ...base, iss: "https://evil.cloudflareaccess.com" }, { clave: k }), opc(jwks)), false);
  assert.equal(await verificarJwt(await firmar(base, { kid: "no-existe", clave: k }), opc(jwks)), false);
  for (const j of ["", "a.b", "a.b.c", null, undefined]) assert.equal(await verificarJwt(j, opc(jwks)), false);
});
