export const MAX_IP = 5, VENTANA_IP_S = 600;          // 5 fallos por IP en 10 minutos
export const MAX_GLOBAL = 30, VENTANA_GLOBAL_S = 3600; // 30 fallos entre todos en 1 hora

async function leer(kv, k) { const v = await kv.get(k); return v ? parseInt(v, 10) || 0 : 0; }

export async function bloqueado(kv, ip) {
  return (await leer(kv, "rl:ip:" + ip)) >= MAX_IP || (await leer(kv, "rl:global")) >= MAX_GLOBAL;
}

export async function anotarFallo(kv, ip) {
  for (const [k, ttl] of [["rl:ip:" + ip, VENTANA_IP_S], ["rl:global", VENTANA_GLOBAL_S]]) {
    await kv.put(k, String((await leer(kv, k)) + 1), { expirationTtl: ttl });
  }
}
