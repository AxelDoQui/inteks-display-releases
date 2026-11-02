// Cliente mínimo de la API de Cloudflare. fetchFn se inyecta para poder probarlo.
export function crearCf({ token, cuenta, zona, dominio, fetchFn = fetch }) {
  const base = "https://api.cloudflare.com/client/v4";
  async function llamar(metodo, ruta, cuerpo) {
    const r = await fetchFn(base + ruta, {
      method: metodo,
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.success === false) {
      const msg = (j.errors && j.errors[0] && j.errors[0].message) || "HTTP " + r.status;
      throw new Error("Cloudflare: " + msg);
    }
    return j.result;
  }
  const T = `/accounts/${cuenta}/cfd_tunnel`;
  return {
    dominio,
    crearTunel: (nombre) => llamar("POST", T, { name: nombre, config_src: "cloudflare" }),
    configurarTunel: (id, host, puerto = 80) => llamar("PUT", `${T}/${id}/configurations`, {
      config: { ingress: [{ hostname: host, service: `http://localhost:${puerto}` }, { service: "http_status:404" }] },
    }),
    tokenTunel: (id) => llamar("GET", `${T}/${id}/token`),
    crearDns: (sub, id) => llamar("POST", `/zones/${zona}/dns_records`, {
      type: "CNAME", name: `${sub}.${dominio}`, content: `${id}.cfargotunnel.com`, proxied: true,
    }),
    borrarDns: (id) => llamar("DELETE", `/zones/${zona}/dns_records/${id}`),
    async borrarTunel(id) {
      // Un túnel con conexiones vivas no se puede borrar: primero se cierran.
      await llamar("DELETE", `${T}/${id}/connections`).catch(() => {});
      return llamar("DELETE", `${T}/${id}`);
    },
    async estadoTunel(id) { return (await llamar("GET", `${T}/${id}`)).status; },
  };
}
