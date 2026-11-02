// Cloudflare de mentira: apunta lo que se crea y puede fallar en un paso a propósito.
export function crearCfFalso({ falla = null } = {}) {
  const e = { tuneles: new Map(), dns: new Map(), n: 0, llamadas: [] };
  const paso = (nombre) => { e.llamadas.push(nombre); if (falla === nombre) throw new Error("Cloudflare: fallo simulado en " + nombre); };
  return {
    estado: e, dominio: "inteksdisplay.com",
    async crearTunel(nombre) { paso("crearTunel"); const id = "t" + (++e.n); e.tuneles.set(id, { nombre, status: "healthy" }); return { id }; },
    async configurarTunel(id, host, puerto) { paso("configurarTunel"); e.tuneles.get(id).host = host; e.tuneles.get(id).puerto = puerto; },
    async crearDns(sub, id) { paso("crearDns"); const did = "d" + (++e.n); e.dns.set(did, { sub, id }); return { id: did }; },
    async tokenTunel(id) { paso("tokenTunel"); return "TOKEN-" + id; },
    async borrarDns(id) { paso("borrarDns"); e.dns.delete(id); },
    async borrarTunel(id) { paso("borrarTunel"); e.tuneles.delete(id); },
    async estadoTunel(id) { paso("estadoTunel"); return e.tuneles.get(id)?.status || "inactive"; },
  };
}
