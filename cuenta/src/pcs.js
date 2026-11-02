import { validarNombre } from "./nombres.js";
import { generarPin, pinValido, PIN_TTL_S } from "./pin.js";
import { bloqueado, anotarFallo } from "./limite.js";

const R = (estado, cuerpo) => ({ estado, cuerpo });
const leerPc = async (kv, n) => { const v = await kv.get("pc:" + n); return v ? JSON.parse(v) : null; };

async function pinLibre(kv) {
  for (let i = 0; i < 20; i++) { const p = generarPin(); if (!(await kv.get("pin:" + p))) return p; }
  throw new Error("no se pudo generar un PIN libre");
}

export async function anadirPc({ nombre, kv, ahora = () => Date.now() }) {
  const mal = validarNombre(nombre);
  if (mal) return R(400, { ok: false, error: mal });
  const previo = await leerPc(kv, nombre);
  if (previo && previo.estado === "activo") return R(409, { ok: false, error: "Ya hay un PC con ese nombre" });
  if (previo && previo.pin) await kv.delete("pin:" + previo.pin);     // el PIN anterior deja de valer
  const pin = await pinLibre(kv);
  const pc = { nombre, estado: "pendiente", pin, pinExpira: ahora() + PIN_TTL_S * 1000, creado: ahora() };
  await kv.put("pc:" + nombre, JSON.stringify(pc));
  await kv.put("pin:" + pin, nombre, { expirationTtl: PIN_TTL_S });
  return R(200, { ok: true, nombre, pin, expiraEnS: PIN_TTL_S });
}

export async function listarPcs({ kv, cf, ahora = () => Date.now() }) {
  const { keys } = await kv.list({ prefix: "pc:" });
  const pcs = [];
  for (const { name } of keys) {
    const pc = JSON.parse((await kv.get(name)) || "null");
    if (!pc) continue;
    const fila = { nombre: pc.nombre, estado: pc.estado, creado: pc.creado };
    if (pc.estado === "activo") {
      fila.hostname = `${pc.nombre}.${cf.dominio}`;
      try { fila.enLinea = (await cf.estadoTunel(pc.tunelId)) === "healthy"; } catch { fila.enLinea = null; }
    } else {
      fila.pin = pc.pinExpira > ahora() ? pc.pin : null;
      fila.pinExpira = pc.pinExpira;
    }
    pcs.push(fila);
  }
  pcs.sort((a, b) => a.nombre.localeCompare(b.nombre));
  return R(200, { ok: true, dominio: cf.dominio, pcs });
}

export async function quitarPc({ nombre, kv, cf }) {
  const pc = await leerPc(kv, nombre);
  if (!pc) return R(404, { ok: false, error: "No existe ese PC" });
  try {
    if (pc.dnsId) await cf.borrarDns(pc.dnsId);
    if (pc.tunelId) await cf.borrarTunel(pc.tunelId);
  } catch (e) {
    return R(502, { ok: false, error: "Cloudflare no dejó borrarlo. Inténtalo de nuevo." });
  }
  if (pc.pin) await kv.delete("pin:" + pc.pin);
  await kv.delete("pc:" + nombre);
  return R(200, { ok: true });
}

export async function enlazar({ pin, puerto, ip, kv, cf, ahora = () => Date.now() }) {
  if (await bloqueado(kv, ip)) return R(429, { ok: false, error: "Demasiados intentos. Espera un rato." });
  const generico = R(400, { ok: false, error: "PIN no válido o caducado" });
  if (!pinValido(pin)) { await anotarFallo(kv, ip); return generico; }
  const nombre = await kv.get("pin:" + pin);
  const pc = nombre ? await leerPc(kv, nombre) : null;
  if (!pc || pc.estado !== "pendiente" || pc.pin !== pin || pc.pinExpira < ahora()) {
    await anotarFallo(kv, ip); return generico;
  }
  const p = Number.isInteger(puerto) && puerto >= 1 && puerto <= 65535 ? puerto : 80;
  const host = `${nombre}.${cf.dominio}`;
  let tunel = null, dns = null;
  try {
    tunel = await cf.crearTunel("inteks-" + nombre);
    await cf.configurarTunel(tunel.id, host, p);
    dns = await cf.crearDns(nombre, tunel.id);
    const token = await cf.tokenTunel(tunel.id);
    await kv.put("pc:" + nombre, JSON.stringify({ ...pc, estado: "activo", pin: null, pinExpira: null, tunelId: tunel.id, dnsId: dns.id, activadoEn: ahora() }));
    await kv.delete("pin:" + pin);
    return R(200, { ok: true, token, hostname: host });
  } catch (e) {
    if (dns) await cf.borrarDns(dns.id).catch(() => {});
    if (tunel) await cf.borrarTunel(tunel.id).catch(() => {});
    return R(502, { ok: false, error: "No se pudo crear el acceso. Inténtalo de nuevo." });
  }
}
