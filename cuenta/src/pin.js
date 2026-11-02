export const PIN_TTL_S = 600;   // 10 minutos

// Seis cifras sin sesgo: se descartan los valores que repartirían de más los primeros números.
export function generarPin() {
  const a = new Uint32Array(1);
  const limite = 4294967296 - (4294967296 % 1000000);
  let x;
  do { crypto.getRandomValues(a); x = a[0]; } while (x >= limite);
  return String(x % 1000000).padStart(6, "0");
}

export function pinValido(p) { return typeof p === "string" && /^\d{6}$/.test(p); }
