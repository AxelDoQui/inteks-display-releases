import { crearCf } from "./cloudflare.js";
import { verificarJwt, jwksDe } from "./access.js";
import { anadirPc, listarPcs, quitarPc, enlazar } from "./pcs.js";
import { PAGINA } from "./pagina.js";

const json = (estado, cuerpo) => new Response(JSON.stringify(cuerpo), {
  status: estado, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

export async function manejar(request, env, deps = {}) {
  const url = new URL(request.url);
  const cf = deps.cf || crearCf({ token: env.CF_API_TOKEN, cuenta: env.CF_ACCOUNT_ID, zona: env.CF_ZONE_ID, dominio: env.DOMINIO });
  const acceso = deps.acceso || (async (req) => verificarJwt(req.headers.get("Cf-Access-Jwt-Assertion"),
    { equipo: env.ACCESS_EQUIPO, aud: env.ACCESS_AUD, correo: env.ACCESS_CORREO, jwks: await jwksDe(env.ACCESS_EQUIPO) }));
  const ip = request.headers.get("CF-Connecting-IP") || "desconocida";

  // Único endpoint público: lo llama el servidor de cada PC con un PIN.
  if (url.pathname === "/api/enlazar") {
    if (request.method !== "POST") return json(405, { ok: false, error: "Método no permitido" });
    let d; try { d = await request.json(); } catch { return json(400, { ok: false, error: "Petición no válida" }); }
    const r = await enlazar({ pin: d && d.pin, puerto: d && d.puerto, ip, kv: env.PCS, cf });
    return json(r.estado, r.cuerpo);
  }

  // Todo lo demás, solo con Access.
  if (!(await acceso(request))) return json(403, { ok: false, error: "Sin acceso" });
  if (url.pathname === "/" && request.method === "GET")
    return new Response(PAGINA, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
  if (url.pathname === "/api/pcs" && request.method === "GET") { const r = await listarPcs({ kv: env.PCS, cf }); return json(r.estado, r.cuerpo); }
  if (url.pathname === "/api/pcs" && request.method === "POST") {
    let d; try { d = await request.json(); } catch { return json(400, { ok: false, error: "Petición no válida" }); }
    const r = await anadirPc({ nombre: d && d.nombre, kv: env.PCS }); return json(r.estado, r.cuerpo);
  }
  const m = url.pathname.match(/^\/api\/pcs\/([a-z0-9-]+)$/);
  if (m && request.method === "DELETE") { const r = await quitarPc({ nombre: m[1], kv: env.PCS, cf }); return json(r.estado, r.cuerpo); }
  return json(404, { ok: false, error: "No existe" });
}

export default { fetch: (request, env) => manejar(request, env) };
