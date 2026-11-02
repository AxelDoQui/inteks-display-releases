// Nombres de PC: acaban siendo subdominios (nombre.inteksdisplay.com), así que solo
// letras minúsculas, números y guiones, y nunca uno que ya tenga otro uso.
export const RESERVADOS = new Set([
  "cuenta", "www", "mail", "api", "admin", "ftp", "smtp", "imap", "pop",
  "autodiscover", "_dmarc", "_domainconnect", "ns1", "ns2",
]);

export function validarNombre(n) {
  if (typeof n !== "string" || !/^[a-z0-9]([a-z0-9-]{0,28}[a-z0-9])?$/.test(n))
    return "El nombre solo lleva minúsculas, números y guiones (de 1 a 30), sin empezar ni acabar en guion";
  if (RESERVADOS.has(n)) return "Ese nombre está reservado";
  return null;
}
