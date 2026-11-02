// Comprueba de verdad el JWT que Cloudflare Access pone en cada petición: firma RS256
// con las claves públicas de tu equipo, emisor, audiencia, caducidad y correo. Mirar
// solo que la cabecera exista no vale: si Access se desactivara, cualquiera la fabricaría.
const deB64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

export async function verificarJwt(jwt, { equipo, aud, correo, jwks, ahora = () => Math.floor(Date.now() / 1000) }) {
  try {
    const partes = String(jwt || "").split(".");
    if (partes.length !== 3) return false;
    const cab = JSON.parse(new TextDecoder().decode(deB64u(partes[0])));
    if (cab.alg !== "RS256") return false;
    const jwk = (jwks.keys || []).find((k) => k.kid === cab.kid);
    if (!jwk) return false;
    const clave = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const firmaOk = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", clave, deB64u(partes[2]),
      new TextEncoder().encode(partes[0] + "." + partes[1]));
    if (!firmaOk) return false;
    const p = JSON.parse(new TextDecoder().decode(deB64u(partes[1])));
    const audOk = Array.isArray(p.aud) ? p.aud.includes(aud) : p.aud === aud;
    return p.iss === "https://" + equipo && audOk && p.exp > ahora()
      && String(p.email || "").toLowerCase() === String(correo || "").toLowerCase();
  } catch { return false; }
}

let _cache = { t: 0, jwks: null };
export async function jwksDe(equipo, fetchFn = fetch, ahoraMs = Date.now()) {
  if (_cache.jwks && ahoraMs - _cache.t < 3600_000) return _cache.jwks;
  const r = await fetchFn(`https://${equipo}/cdn-cgi/access/certs`);
  if (!r.ok) throw new Error("sin claves de Access");
  _cache = { t: ahoraMs, jwks: await r.json() };
  return _cache.jwks;
}
