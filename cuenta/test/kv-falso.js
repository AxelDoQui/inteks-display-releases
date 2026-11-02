// KV de mentira para las pruebas: mismas llamadas que el real (get, put con
// expirationTtl, delete, list con prefijo) y reloj inyectable.
export function crearKv(ahora = () => Date.now()) {
  const datos = new Map();
  const vivo = (e) => e && (e.exp === null || e.exp > ahora());
  return {
    async get(k) { const e = datos.get(k); return vivo(e) ? e.v : null; },
    async put(k, v, opc = {}) {
      datos.set(k, { v: String(v), exp: opc.expirationTtl ? ahora() + opc.expirationTtl * 1000 : null });
    },
    async delete(k) { datos.delete(k); },
    async list({ prefix = "" } = {}) {
      const keys = [];
      for (const [name, e] of datos) if (name.startsWith(prefix) && vivo(e)) keys.push({ name });
      return { keys };
    },
  };
}
