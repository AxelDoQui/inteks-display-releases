# Acceso remoto con cuenta y PIN — Plan de implementación

> **Para agentes:** SUB-SKILL OBLIGATORIA: usa superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos usan casillas `- [ ]`.

**Objetivo:** que un PC con InTeks Display quede accesible en `tienda1.inteksdisplay.com` metiendo un PIN de 6 cifras en su panel, sin comandos ni tocar Cloudflare.

**Arquitectura:** un Cloudflare Worker («InTeks Cuenta», `cuenta.inteksdisplay.com`, tras Cloudflare Access) guarda la llave de API y crea túnel + DNS al canjear un PIN. El `server.py` de cada PC canjea el PIN, instala `cloudflared` como servicio y lo cuenta en una tarjeta del panel. Spec: `docs/superpowers/specs/2026-11-02-acceso-remoto-cuenta-design.md`.

**Tecnologías:** Worker en JavaScript (módulos ES, WebCrypto, KV), `node --test`; Python (stdlib) en `server.py`; HTML/JS vainilla en `admin.html`; Inno Setup.

## Restricciones globales

- Todo en español: textos, comentarios y mensajes de commit.
- `admin.html` usa saltos de línea LF; `player.html` CRLF (no se toca). `installer/setup.iss` sin BOM.
- Los tests Python son scripts sueltos en `tests/` con puertos únicos (8138 para este) y `SIGNALOS_DATA` temporal; los de Node, `node --test tests/*.test.js`. La suite Node debe seguir en verde (333 al empezar).
- Ningún secreto en el repo: ni la llave de API, ni tokens de túnel, ni el correo de Axel en el código (van como secretos/variables del Worker).
- El token del túnel **nunca** se escribe en logs, estado ni respuestas: se redacta como `***`.
- Mensaje de commit termina con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Se publica solo cuando Axel diga «Publica 1.0.67».

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `cuenta/package.json`, `cuenta/wrangler.toml` | proyecto del Worker |
| `cuenta/src/nombres.js` | validar nombres de PC (formato y reservados) |
| `cuenta/src/pin.js` | generar y validar PINs |
| `cuenta/src/limite.js` | límite de intentos por IP y global |
| `cuenta/src/cloudflare.js` | cliente de la API de Cloudflare (túnel, config, DNS) |
| `cuenta/src/pcs.js` | añadir, listar, quitar y canjear PCs (lógica de negocio) |
| `cuenta/src/access.js` | verificar el JWT de Cloudflare Access |
| `cuenta/src/pagina.js` | HTML de la web de la cuenta |
| `cuenta/src/index.js` | rutas del Worker |
| `cuenta/test/*.test.js`, `cuenta/test/kv-falso.js` | pruebas del Worker |
| `server.py` | backend de «Acceso remoto» y IP real del cliente |
| `admin.html` | tarjeta «Acceso remoto» |
| `tests/test_acceso_remoto.py` | prueba del servidor con Worker y `cloudflared` falsos |
| `tools/descargar-cloudflared.ps1` | baja `cloudflared.exe` y comprueba su SHA-256 |
| `installer/setup.iss` | incluye `cloudflared.exe` |

---

### Tarea 1: Worker — nombres, PIN y límite de intentos

**Archivos:**
- Crear: `cuenta/package.json`, `cuenta/wrangler.toml`, `cuenta/src/nombres.js`, `cuenta/src/pin.js`, `cuenta/src/limite.js`, `cuenta/test/kv-falso.js`, `cuenta/test/basicos.test.js`

**Interfaces:**
- Produce: `validarNombre(n) → string|null` (texto del problema o null), `RESERVADOS`; `generarPin() → "000000"…"999999"`, `pinValido(p) → boolean`, `PIN_TTL_S = 600`; `bloqueado(kv, ip) → Promise<boolean>`, `anotarFallo(kv, ip) → Promise<void>`; `crearKv(ahora?) → kv` con `get/put/delete/list`.

- [ ] **Paso 1: proyecto del Worker**

`cuenta/package.json`:
```json
{
  "name": "inteks-cuenta",
  "private": true,
  "type": "module",
  "scripts": { "test": "node --test test/*.test.js" },
  "devDependencies": { "wrangler": "^4.0.0" }
}
```
`cuenta/wrangler.toml`:
```toml
name = "inteks-cuenta"
main = "src/index.js"
compatibility_date = "2026-10-01"

[[kv_namespaces]]
binding = "PCS"
id = "PON_AQUI_EL_ID_DE_KV"

[vars]
DOMINIO = "inteksdisplay.com"
```
(El `id` real lo rellena la Tarea 7 con `wrangler kv namespace create PCS`.)

- [ ] **Paso 2: KV falso en memoria** — `cuenta/test/kv-falso.js`
```js
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
```

- [ ] **Paso 3: escribir las pruebas que fallan** — `cuenta/test/basicos.test.js`
```js
import test from "node:test";
import assert from "node:assert/strict";
import { validarNombre, RESERVADOS } from "../src/nombres.js";
import { generarPin, pinValido, PIN_TTL_S } from "../src/pin.js";
import { bloqueado, anotarFallo, MAX_IP, MAX_GLOBAL } from "../src/limite.js";
import { crearKv } from "./kv-falso.js";

test("nombres válidos", () => {
  for (const n of ["tienda1", "a", "mi-tienda", "t-2-b", "a".repeat(30)]) assert.equal(validarNombre(n), null, n);
});
test("nombres inválidos", () => {
  for (const n of ["", "Tienda", "tienda_1", "-a", "a-", "a b", "a.b", "a".repeat(31), "ñu", null, 5, undefined])
    assert.notEqual(validarNombre(n), null, String(n));
});
test("nombres reservados", () => {
  for (const n of ["cuenta", "www", "mail", "api", "admin", "autodiscover", "_dmarc"]) assert.ok(RESERVADOS.has(n) || validarNombre(n), n);
  assert.match(validarNombre("cuenta"), /reservado/);
  assert.match(validarNombre("www"), /reservado/);
});
test("PIN: seis cifras, con ceros delante, y distintos", () => {
  const vistos = new Set();
  for (let i = 0; i < 300; i++) { const p = generarPin(); assert.match(p, /^\d{6}$/); vistos.add(p); }
  assert.ok(vistos.size > 250);
  assert.equal(PIN_TTL_S, 600);
});
test("pinValido", () => {
  assert.equal(pinValido("012345"), true);
  for (const p of ["12345", "1234567", "12345a", "", null, 123456]) assert.equal(pinValido(p), false);
});
test("límite por IP: bloquea al llegar al máximo y otra IP no se ve afectada", async () => {
  const kv = crearKv();
  for (let i = 0; i < MAX_IP - 1; i++) { await anotarFallo(kv, "1.1.1.1"); assert.equal(await bloqueado(kv, "1.1.1.1"), false); }
  await anotarFallo(kv, "1.1.1.1");
  assert.equal(await bloqueado(kv, "1.1.1.1"), true);
  assert.equal(await bloqueado(kv, "2.2.2.2"), false);
});
test("límite por IP: caduca a los 10 minutos", async () => {
  let t = 0; const kv = crearKv(() => t);
  for (let i = 0; i < MAX_IP; i++) await anotarFallo(kv, "1.1.1.1");
  assert.equal(await bloqueado(kv, "1.1.1.1"), true);
  t += 601 * 1000;
  assert.equal(await bloqueado(kv, "1.1.1.1"), false);
});
test("límite global: muchas IPs distintas también bloquean", async () => {
  const kv = crearKv();
  for (let i = 0; i < MAX_GLOBAL; i++) await anotarFallo(kv, "9.9.9." + i);
  assert.equal(await bloqueado(kv, "8.8.8.8"), true);
});
```

- [ ] **Paso 4: ver que fallan** — `cd cuenta && node --test test/basicos.test.js` → falla por módulos inexistentes.

- [ ] **Paso 5: implementar**

`cuenta/src/nombres.js`:
```js
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
```
`cuenta/src/pin.js`:
```js
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
```
`cuenta/src/limite.js`:
```js
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
```

- [ ] **Paso 6: pasan** — `cd cuenta && node --test test/basicos.test.js` → todos ok.

- [ ] **Paso 7: commit** — `git add cuenta && git commit -m "feat(cuenta): validación de nombres, PIN y límite de intentos"` (con la línea Co-Authored-By).

---

### Tarea 2: Worker — cliente de Cloudflare y lógica de PCs

**Archivos:**
- Crear: `cuenta/src/cloudflare.js`, `cuenta/src/pcs.js`, `cuenta/test/cf-falso.js`, `cuenta/test/pcs.test.js`

**Interfaces:**
- Consume: Tarea 1 (`validarNombre`, `generarPin`, `pinValido`, `PIN_TTL_S`, `bloqueado`, `anotarFallo`).
- Produce: `crearCf({token, cuenta, zona, dominio, fetchFn}) → {dominio, crearTunel(nombre)→{id}, configurarTunel(id, host, puerto), crearDns(sub, id)→{id}, tokenTunel(id)→string, borrarDns(id), borrarTunel(id), estadoTunel(id)→"healthy"|"degraded"|"down"|"inactive"}`; `anadirPc({nombre, kv, ahora})`, `listarPcs({kv, cf, ahora})`, `quitarPc({nombre, kv, cf})`, `enlazar({pin, puerto, ip, kv, cf, ahora})`. Todas devuelven `{estado: <http>, cuerpo: {...}}`.
- KV: `pc:<nombre>` → JSON `{nombre, estado:"pendiente"|"activo", pin, pinExpira, tunelId, dnsId, creado, activadoEn}`; `pin:<pin>` → nombre (TTL 600).

- [ ] **Paso 1: CF falso** — `cuenta/test/cf-falso.js`
```js
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
```

- [ ] **Paso 2: pruebas que fallan** — `cuenta/test/pcs.test.js`
```js
import test from "node:test";
import assert from "node:assert/strict";
import { anadirPc, listarPcs, quitarPc, enlazar } from "../src/pcs.js";
import { crearKv } from "./kv-falso.js";
import { crearCfFalso } from "./cf-falso.js";

const mundo = (opc) => ({ kv: crearKv(), cf: crearCfFalso(opc) });

test("añadir PC devuelve un PIN y deja el PC pendiente", async () => {
  const { kv } = mundo();
  const r = await anadirPc({ nombre: "tienda1", kv });
  assert.equal(r.estado, 200); assert.match(r.cuerpo.pin, /^\d{6}$/);
  assert.equal(JSON.parse(await kv.get("pc:tienda1")).estado, "pendiente");
  assert.equal(await kv.get("pin:" + r.cuerpo.pin), "tienda1");
});
test("añadir: nombre inválido o reservado se rechaza", async () => {
  const { kv } = mundo();
  assert.equal((await anadirPc({ nombre: "Tienda 1", kv })).estado, 400);
  assert.equal((await anadirPc({ nombre: "cuenta", kv })).estado, 400);
});
test("añadir: un PC ya activo no se puede repetir; uno pendiente se rehace con PIN nuevo", async () => {
  const { kv, cf } = mundo();
  const a = await anadirPc({ nombre: "t1", kv });
  const b = await anadirPc({ nombre: "t1", kv });
  assert.equal(b.estado, 200); assert.equal(await kv.get("pin:" + a.cuerpo.pin) === null || a.cuerpo.pin === b.cuerpo.pin, true);
  await enlazar({ pin: b.cuerpo.pin, puerto: 80, ip: "1.1.1.1", kv, cf });
  assert.equal((await anadirPc({ nombre: "t1", kv })).estado, 409);
});
test("canjear PIN: crea túnel, configura, crea DNS y devuelve el token", async () => {
  const { kv, cf } = mundo();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "tienda1", kv });
  const r = await enlazar({ pin, puerto: 9000, ip: "1.1.1.1", kv, cf });
  assert.equal(r.estado, 200);
  assert.deepEqual(r.cuerpo, { ok: true, token: "TOKEN-t1", hostname: "tienda1.inteksdisplay.com" });
  assert.equal(cf.estado.tuneles.get("t1").host, "tienda1.inteksdisplay.com");
  assert.equal(cf.estado.tuneles.get("t1").puerto, 9000);
  const pc = JSON.parse(await kv.get("pc:tienda1"));
  assert.equal(pc.estado, "activo"); assert.equal(pc.pin, null);
});
test("un PIN solo vale una vez", async () => {
  const { kv, cf } = mundo();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  assert.equal((await enlazar({ pin, ip: "1.1.1.1", kv, cf })).estado, 200);
  assert.equal((await enlazar({ pin, ip: "1.1.1.1", kv, cf })).estado, 400);
});
test("PIN caducado, inexistente o mal formado: mismo mensaje genérico", async () => {
  let t = 0; const kv = crearKv(() => t); const cf = crearCfFalso();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv, ahora: () => t });
  t += 601 * 1000;
  const a = await enlazar({ pin, ip: "1.1.1.1", kv, cf, ahora: () => t });
  const b = await enlazar({ pin: "000000", ip: "1.1.1.2", kv, cf, ahora: () => t });
  const c = await enlazar({ pin: "abc", ip: "1.1.1.3", kv, cf, ahora: () => t });
  for (const r of [a, b, c]) { assert.equal(r.estado, 400); assert.equal(r.cuerpo.error, "PIN no válido o caducado"); }
});
test("tras 5 fallos desde la misma IP responde 429, aunque luego acierte", async () => {
  const { kv, cf } = mundo();
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  for (let i = 0; i < 5; i++) await enlazar({ pin: "999999", ip: "6.6.6.6", kv, cf });
  assert.equal((await enlazar({ pin, ip: "6.6.6.6", kv, cf })).estado, 429);
  assert.equal((await enlazar({ pin, ip: "7.7.7.7", kv, cf })).estado, 200);
});
test("si falla el DNS se deshace el túnel y el PIN sigue valiendo", async () => {
  const kv = crearKv(); let cf = crearCfFalso({ falla: "crearDns" });
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  const r = await enlazar({ pin, ip: "1.1.1.1", kv, cf });
  assert.equal(r.estado, 502);
  assert.equal(cf.estado.tuneles.size, 0);
  assert.equal(JSON.parse(await kv.get("pc:t1")).estado, "pendiente");
  assert.equal(await kv.get("pin:" + pin), "t1");
});
test("si falla el token se deshacen túnel y DNS", async () => {
  const kv = crearKv(); const cf = crearCfFalso({ falla: "tokenTunel" });
  const { cuerpo: { pin } } = await anadirPc({ nombre: "t1", kv });
  assert.equal((await enlazar({ pin, ip: "1.1.1.1", kv, cf })).estado, 502);
  assert.equal(cf.estado.tuneles.size, 0); assert.equal(cf.estado.dns.size, 0);
});
test("listar: activos con su estado, pendientes con su PIN", async () => {
  const { kv, cf } = mundo();
  const a = await anadirPc({ nombre: "t1", kv }); await enlazar({ pin: a.cuerpo.pin, ip: "1.1.1.1", kv, cf });
  await anadirPc({ nombre: "t2", kv });
  const { cuerpo } = await listarPcs({ kv, cf });
  const t1 = cuerpo.pcs.find((p) => p.nombre === "t1"), t2 = cuerpo.pcs.find((p) => p.nombre === "t2");
  assert.equal(t1.estado, "activo"); assert.equal(t1.enLinea, true); assert.equal(t1.hostname, "t1.inteksdisplay.com");
  assert.equal(t2.estado, "pendiente"); assert.match(t2.pin, /^\d{6}$/);
});
test("quitar: borra DNS, túnel y la entrada; si Cloudflare falla, no borra la entrada", async () => {
  const kv = crearKv(); let cf = crearCfFalso();
  const a = await anadirPc({ nombre: "t1", kv }); await enlazar({ pin: a.cuerpo.pin, ip: "1.1.1.1", kv, cf });
  const malo = crearCfFalso({ falla: "borrarTunel" });
  assert.equal((await quitarPc({ nombre: "t1", kv, cf: malo })).estado, 502);
  assert.notEqual(await kv.get("pc:t1"), null);
  assert.equal((await quitarPc({ nombre: "t1", kv, cf })).estado, 200);
  assert.equal(await kv.get("pc:t1"), null); assert.equal(cf.estado.tuneles.size, 0); assert.equal(cf.estado.dns.size, 0);
  assert.equal((await quitarPc({ nombre: "t1", kv, cf })).estado, 404);
});
```

- [ ] **Paso 3: ver que fallan** — `cd cuenta && node --test test/pcs.test.js`.

- [ ] **Paso 4: implementar** `cuenta/src/cloudflare.js`
```js
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
```
`cuenta/src/pcs.js`
```js
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
    const pc = JSON.parse(await kv.get(name) || "null");
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
```
Nota: el KV real no soporta `list` con consistencia inmediata, pero para unas decenas de PCs es suficiente.

- [ ] **Paso 5: pasan** — `cd cuenta && node --test test/*.test.js`.
- [ ] **Paso 6: commit** — `feat(cuenta): cliente de Cloudflare y lógica de PCs (añadir, canjear PIN, listar, quitar)`.

---

### Tarea 3: Worker — Access, rutas y página de la cuenta

**Archivos:**
- Crear: `cuenta/src/access.js`, `cuenta/src/pagina.js`, `cuenta/src/index.js`, `cuenta/test/access.test.js`, `cuenta/test/rutas.test.js`

**Interfaces:**
- Consume: Tarea 2 (`anadirPc`, `listarPcs`, `quitarPc`, `enlazar`, `crearCf`).
- Produce: `verificarJwt(jwt, {equipo, aud, correo, jwks, ahora}) → Promise<boolean>`; `manejar(request, env, deps) → Response` (default export del Worker usa `manejar`).
- Entorno del Worker: `PCS` (KV), `DOMINIO`, `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_ZONE_ID`, `ACCESS_EQUIPO` (ej. `axel.cloudflareaccess.com`), `ACCESS_AUD`, `ACCESS_CORREO`.

- [ ] **Paso 1: pruebas de Access** — `cuenta/test/access.test.js`
```js
import test from "node:test";
import assert from "node:assert/strict";
import { verificarJwt } from "../src/access.js";

const b64u = (b) => Buffer.from(b).toString("base64url");
async function firmar(payload, { kid = "k1", clave } = {}) {
  const cab = b64u(JSON.stringify({ alg: "RS256", kid, typ: "JWT" })), cuerpo = b64u(JSON.stringify(payload));
  const firma = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", clave.privateKey, new TextEncoder().encode(cab + "." + cuerpo));
  return `${cab}.${cuerpo}.${b64u(Buffer.from(firma))}`;
}
async function par() { return crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]); }
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
```

- [ ] **Paso 2: implementar** `cuenta/src/access.js`
```js
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
```

- [ ] **Paso 3: pruebas de rutas** — `cuenta/test/rutas.test.js`
```js
import test from "node:test";
import assert from "node:assert/strict";
import { manejar } from "../src/index.js";
import { crearKv } from "./kv-falso.js";
import { crearCfFalso } from "./cf-falso.js";

const env = { PCS: crearKv(), DOMINIO: "inteksdisplay.com", ACCESS_EQUIPO: "e", ACCESS_AUD: "a", ACCESS_CORREO: "x@y.z" };
const deps = (acceso) => ({ cf: crearCfFalso(), acceso: async () => acceso });
const pet = (ruta, metodo = "GET", cuerpo, ip = "5.5.5.5") =>
  new Request("https://cuenta.inteksdisplay.com" + ruta, { method: metodo, headers: { "CF-Connecting-IP": ip, "Content-Type": "application/json" }, body: cuerpo ? JSON.stringify(cuerpo) : undefined });

test("la web y la API de la cuenta exigen Access: sin él, 403", async () => {
  for (const [r, m] of [["/", "GET"], ["/api/pcs", "GET"], ["/api/pcs", "POST"], ["/api/pcs/t1", "DELETE"]])
    assert.equal((await manejar(pet(r, m, m === "POST" ? { nombre: "t1" } : undefined), env, deps(false))).status, 403, r);
});
test("con Access: la página es HTML y la lista responde", async () => {
  const d = deps(true);
  const home = await manejar(pet("/"), env, d);
  assert.equal(home.status, 200); assert.match(home.headers.get("content-type"), /text\/html/);
  const lista = await manejar(pet("/api/pcs"), env, d); assert.equal(lista.status, 200);
  assert.deepEqual((await lista.json()).pcs, []);
});
test("flujo completo: añadir → canjear (sin Access) → listar → quitar", async () => {
  const d = deps(true);
  const alta = await (await manejar(pet("/api/pcs", "POST", { nombre: "tienda1" }), env, d)).json();
  const canje = await manejar(pet("/api/enlazar", "POST", { pin: alta.pin, puerto: 80 }), env, deps(false));   // público: no necesita Access
  assert.equal(canje.status, 200); assert.equal((await canje.json()).hostname, "tienda1.inteksdisplay.com");
  const lista = await (await manejar(pet("/api/pcs"), env, d)).json();
  assert.equal(lista.pcs[0].estado, "activo");
  assert.equal((await manejar(pet("/api/pcs/tienda1", "DELETE"), env, d)).status, 200);
});
test("/api/enlazar: cuerpo roto → 400; método GET → 405; ruta desconocida → 404", async () => {
  const roto = new Request("https://x/api/enlazar", { method: "POST", body: "no es json", headers: { "CF-Connecting-IP": "9.9.9.9" } });
  assert.equal((await manejar(roto, env, deps(false))).status, 400);
  assert.equal((await manejar(pet("/api/enlazar"), env, deps(false))).status, 405);
  assert.equal((await manejar(pet("/nada"), env, deps(true))).status, 404);
});
```

- [ ] **Paso 4: implementar** `cuenta/src/index.js`
```js
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
```
`cuenta/src/pagina.js` (una sola página, sin librerías; todo el contenido dinámico se inserta con `textContent`, nunca con `innerHTML`):
```js
export const PAGINA = `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>InTeks Cuenta</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--tx:#e8eaf0;--mut:#9aa3b2;--ac:#4f8cff;--ok:#2ecc71;--mal:#ff5d5d;--bd:#2a2f3a}
@media (prefers-color-scheme:light){:root{--bg:#f4f6fa;--card:#fff;--tx:#161a22;--mut:#5b6575;--bd:#dde2ea}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}p.s{color:var(--mut);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;margin-bottom:16px}
input,button{font:inherit;border-radius:8px;border:1px solid var(--bd);padding:9px 12px;background:var(--bg);color:var(--tx)}
button{background:var(--ac);border-color:var(--ac);color:#fff;cursor:pointer}button.g{background:none;color:var(--tx);border-color:var(--bd)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pc{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-top:1px solid var(--bd);flex-wrap:wrap}
.pc:first-child{border-top:0}.pin{font:600 26px/1 ui-monospace,monospace;letter-spacing:4px}.mut{color:var(--mut);font-size:13px}
.on{color:var(--ok)}.off{color:var(--mal)}
</style></head><body><main>
<h1>InTeks Cuenta</h1><p class="s">Tus PCs con acceso remoto.</p>
<div class="card"><div class="row"><input id="n" placeholder="nombre (tienda1)" maxlength="30" autocomplete="off">
<button id="add">Añadir PC</button></div><p class="mut" id="msg"></p></div>
<div class="card" id="lista"></div>
<script>
const $=(i)=>document.getElementById(i);
const msg=(t,e)=>{$("msg").textContent=t;$("msg").style.color=e?"var(--mal)":"var(--mut)"};
async function cargar(){
  const r=await fetch("/api/pcs");const d=await r.json();const l=$("lista");l.textContent="";
  if(!d.pcs||!d.pcs.length){l.textContent="Aún no hay ningún PC.";return}
  for(const p of d.pcs){
    const f=document.createElement("div");f.className="pc";const a=document.createElement("div");
    const t=document.createElement("strong");t.textContent=p.nombre;a.appendChild(t);
    const s=document.createElement("div");s.className="mut";
    if(p.estado==="activo"){s.textContent=p.hostname+" · ";const e=document.createElement("span");
      e.className=p.enLinea?"on":"off";e.textContent=p.enLinea===null?"estado desconocido":p.enLinea?"en línea":"sin conexión";s.appendChild(e)}
    else{s.textContent=p.pin?"Pendiente de enlazar. PIN válido unos minutos:":"PIN caducado";if(p.pin){const n=document.createElement("div");n.className="pin";n.textContent=p.pin;a.appendChild(s);a.appendChild(n)}}
    if(!a.contains(s))a.appendChild(s);
    const b=document.createElement("button");b.className="g";b.textContent="Quitar";
    b.onclick=async()=>{if(!confirm("¿Quitar "+p.nombre+"? Su dirección dejará de funcionar."))return;
      const x=await fetch("/api/pcs/"+encodeURIComponent(p.nombre),{method:"DELETE"});const j=await x.json();msg(j.ok?"Quitado.":j.error,!j.ok);cargar()};
    f.appendChild(a);f.appendChild(b);l.appendChild(f)}
}
$("add").onclick=async()=>{const nombre=$("n").value.trim().toLowerCase();
  const r=await fetch("/api/pcs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nombre})});
  const d=await r.json();if(!d.ok){msg(d.error,true);return}msg("Listo: escribe el PIN en el panel del PC (Ajustes → Acceso remoto).");$("n").value="";cargar()};
cargar();setInterval(cargar,15000);
</script></main></body></html>`;
```

- [ ] **Paso 5: pasan** — `cd cuenta && node --test test/*.test.js`.
- [ ] **Paso 6: commit** — `feat(cuenta): Access, rutas y página de la cuenta`.

---

### Tarea 4: Servidor — IP real del cliente y backend de «Acceso remoto»

**Archivos:**
- Modificar: `server.py` (junto al bloque de LG, ~l.723-800; endpoints junto a `/api/lg-instalar`, ~l.2220 y ~l.3305; `login_*` ~l.2602)
- Crear: `tests/test_acceso_remoto.py`

**Interfaces:**
- Consume: `admin_has_password()`, `load_json`, `save_json`, `require_auth`, `jresp`, `PORT`, `DATA_DIR`, `APP_DIR`.
- Produce: `GET /api/acceso-remoto` → `{disponible, password, activo, hostname, servicio, estado, pasos[], error}`; `POST /api/acceso-remoto/activar {pin}` → 200 `{ok:true}` / 400 `{ok:false,error}` / 409 si ya hay una en marcha; `POST /api/acceso-remoto/desactivar` → 200.
- Variables de entorno de prueba: `SIGNALOS_CUENTA_URL` (Worker falso), `SIGNALOS_CLOUDFLARED` (ejecutable falso).

- [ ] **Paso 1: escribir la prueba que falla** — `tests/test_acceso_remoto.py` (puerto 8138; patrón de `test_lg_instalar.py`)

Contenido: un servidor HTTP falso en el puerto 8139 que hace de Worker (`POST /api/enlazar` → con PIN `123456` responde `{ok:true, token:"TOKENFALSO<64 letras>", hostname:"tienda1.inteksdisplay.com"}` y registra el cuerpo que recibió; con cualquier otro PIN, 400 `{"ok":false,"error":"PIN no válido o caducado"}`), y un `cloudflared` falso `falso-cloudflared.cmd`:
```bat
@echo off
echo %* >> "%~dp0llamadas.txt"
echo salida: %*
exit /b 0
```
Casos (cada uno con `check(ok, texto)` como el resto de tests):
1. `GET /api/acceso-remoto` sin sesión → 401.
2. Con token y **sin contraseña de admin** (el `admin.json` de prueba no tiene `pwd_hash`): `activar {pin:"123456"}` → 400 con «contraseña del administrador», y el Worker falso no recibió nada.
3. Con contraseña (crear `pwd_hash` llamando a `/api/set-password` con el token): PIN `12345` y `abcdef` → 400 «6 cifras».
4. PIN `654321` (el Worker lo rechaza) → el estado final es `error` con «PIN no válido o caducado»; `llamadas.txt` no existe (no se instaló nada).
5. PIN `123456` → `estado` pasa a `ok`; `hostname` = `tienda1.inteksdisplay.com`; `llamadas.txt` contiene `service uninstall` y `service install TOKENFALSO…`; el Worker falso recibió `puerto` = `PORT` del servidor.
6. Ni el estado devuelto por la API ni `acceso-remoto.json` contienen el token (`"TOKENFALSO" not in respuesta`).
7. Segunda activación mientras `estado == "activando"` (usar un `cloudflared` falso con `timeout /t 3` para el caso) → 409.
8. `desactivar` → `llamadas.txt` ganó `service uninstall`, `activo == False` y el archivo `acceso-remoto.json` ya no existe.
9. Un token con signos raros devuelto por el Worker falso (`"a; calc"`) → estado `error`, no se ejecuta nada.
10. Login por el túnel: una petición a `/api/login` con cabecera `CF-Connecting-IP: 203.0.113.7` y conexión desde 127.0.0.1 se limita **por esa IP**: 5 contraseñas malas desde `203.0.113.7` bloquean a esa IP (429), pero un intento desde `203.0.113.8` sigue respondiendo 401 (no 429).

- [ ] **Paso 2: ver que falla** — `python tests/test_acceso_remoto.py` (falla por rutas inexistentes).

- [ ] **Paso 3: IP real del cliente.** Añadir junto a `login_bloqueado` (`server.py` ~l.829) y usarlo en `/api/login` en lugar de `self.client_address[0]`:
```python
def ip_cliente(self):
    """IP desde la que viene de verdad la petición. Las que llegan por el túnel de
    Cloudflare salen de 127.0.0.1 (cloudflared corre aquí): sin esto, todo internet
    compartiría el mismo contador de intentos de login y uno solo bloquearía al resto.
    La cabecera solo se cree si la conexión es local; desde otro equipo se ignora."""
    directa = self.client_address[0]
    if directa in ("127.0.0.1", "::1"):
        real = (self.headers.get("CF-Connecting-IP") or "").strip()
        if real and len(real) <= 45 and re.fullmatch(r"[0-9a-fA-F:.]+", real):
            return real
    return directa
```
(método de `Handler`; la línea `ip = self.client_address[0]` de `/api/login` pasa a `ip = self.ip_cliente()`).

- [ ] **Paso 4: backend del acceso remoto**, tras `lg_instalar_iniciar` (~l.800):
```python
# ── Acceso remoto: enlazar este PC con la cuenta de InTeks y dejarlo accesible desde
# internet en su propia dirección (tienda1.inteksdisplay.com).
# El usuario saca un PIN en su cuenta y lo escribe en el panel. Aquí se canjea con el
# Worker de la cuenta, que crea el túnel y la dirección y devuelve SOLO el token de ese
# túnel; con él se instala cloudflared como servicio de Windows. El token no se guarda
# ni se muestra en ningún sitio: lo guarda el propio servicio.
ACCESO_FILE = os.path.join(DATA_DIR, "acceso-remoto.json")
CUENTA_URL = os.environ.get("SIGNALOS_CUENTA_URL", "https://cuenta.inteksdisplay.com").rstrip("/")
_acc = {"estado": "libre", "pasos": [], "error": ""}     # libre | activando | ok | error
_acc_lock = threading.Lock()

def acceso_cloudflared():
    ruta = os.environ.get("SIGNALOS_CLOUDFLARED")
    if ruta:
        return ruta if os.path.isfile(ruta) else None
    p = os.path.join(APP_DIR, "cloudflared.exe")
    return p if os.path.isfile(p) else None

def acceso_servicio_activo():
    if os.environ.get("SIGNALOS_CLOUDFLARED"):
        return True                                       # en las pruebas no hay servicio real
    try:
        r = subprocess.run(["sc.exe", "query", "cloudflared"], capture_output=True, text=True,
                           timeout=15, creationflags=0x08000000)
        return "RUNNING" in r.stdout
    except Exception:
        return False

def acceso_estado():
    f = load_json(ACCESO_FILE)
    f = f if isinstance(f, dict) else {}
    with _acc_lock:
        e = {"estado": _acc["estado"], "pasos": list(_acc["pasos"]), "error": _acc["error"]}
    e.update(disponible=acceso_cloudflared() is not None, password=admin_has_password(),
             activo=bool(f.get("hostname")), hostname=f.get("hostname", ""),
             servicio=acceso_servicio_activo() if f.get("hostname") else False)
    return e

def _acceso_cf(exe, *args, timeout=120):
    return subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=0x08000000)

def acceso_activar(pin, puerto):
    """Lanza la activación en segundo plano. (True, "") o (False, motivo)."""
    if not re.fullmatch(r"\d{6}", pin or ""):
        return False, "El PIN son 6 cifras"
    if not admin_has_password():
        return False, "Antes de activarlo, crea la contraseña del administrador (Seguridad y acceso): si no, el panel quedaría abierto a internet"
    exe = acceso_cloudflared()
    if not exe:
        return False, "Esta instalación no trae cloudflared. Reinstala InTeks Display con la última versión."
    if sys.platform != "win32" and not os.environ.get("SIGNALOS_CLOUDFLARED"):
        return False, "El acceso remoto solo existe en Windows"
    with _acc_lock:
        if _acc["estado"] == "activando":
            return False, "Ya hay una activación en marcha"
        _acc.update(estado="activando", pasos=[], error="")

    def paso(t):
        with _acc_lock:
            _acc["pasos"] = (_acc["pasos"] + [t])[-20:]

    def correr():
        token = ""
        try:
            paso("Comprobando el PIN con tu cuenta…")
            req = urllib.request.Request(CUENTA_URL + "/api/enlazar",
                data=json.dumps({"pin": pin, "puerto": puerto}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "InTeksDisplay"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r)
            except urllib.error.HTTPError as e:
                d = json.loads(e.read() or b"{}")
                raise ValueError(d.get("error") or ("La cuenta respondió " + str(e.code)))
            token, host = str(d.get("token", "")), str(d.get("hostname", ""))
            if not re.fullmatch(r"[A-Za-z0-9_\-=.]{20,2000}", token) or not re.fullmatch(r"[a-z0-9.\-]{3,120}", host):
                raise ValueError("La cuenta devolvió una respuesta que no se puede usar")
            paso("Instalando el servicio de conexión…")
            try: _acceso_cf(exe, "service", "uninstall", timeout=60)      # por si había otro túnel
            except Exception: pass
            r = _acceso_cf(exe, "service", "install", token)
            if r.returncode != 0:
                raise ValueError("No se pudo instalar el servicio (hacen falta permisos de administrador)")
            paso("Comprobando que arranca…")
            for _ in range(20):
                if acceso_servicio_activo(): break
                time.sleep(1)
            else:
                raise ValueError("El servicio se instaló pero no arrancó")
            save_json(ACCESO_FILE, {"hostname": host, "activado_en": time.time()})
            paso("Listo: " + host)
            with _acc_lock: _acc["estado"] = "ok"
        except Exception as e:
            msg = str(e).replace(token, "***") if token else str(e)
            with _acc_lock: _acc.update(estado="error", error=msg[:300])

    threading.Thread(target=correr, daemon=True).start()
    return True, ""

def acceso_desactivar():
    exe = acceso_cloudflared()
    if exe:
        try: _acceso_cf(exe, "service", "uninstall", timeout=60)
        except Exception: pass
    try: os.remove(ACCESO_FILE)
    except OSError: pass
    with _acc_lock: _acc.update(estado="libre", pasos=[], error="")
```
Endpoints (mismo estilo que `/api/lg-instalar`): `GET /api/acceso-remoto` con `self.require_auth()` y `acceso_estado()`; `POST /api/acceso-remoto/activar` llama a `acceso_activar(str(d.get("pin","")).strip(), PORT)` y responde `409` si el motivo contiene «en marcha», si no `400`; `POST /api/acceso-remoto/desactivar` llama a `acceso_desactivar()` y responde `ok()`. Si los `POST` de LG pasan por una comprobación de sesión general, estos también; la prueba 1 lo confirma. Añadir `"acceso-remoto.json"` a la tupla `ESTADO` (l.160) para que entre en las copias de estado que ya haga el servidor, y `acceso-remoto.json` a `.gitignore`.

- [ ] **Paso 5: pasa** — `python tests/test_acceso_remoto.py` → «TODO OK». Además `python tests/test_lg_instalar.py` y `node --test tests/*.test.js` siguen en verde.
- [ ] **Paso 6: commit** — `feat: backend de acceso remoto (canjear PIN, instalar cloudflared) e IP real tras el túnel`.

---

### Tarea 5: Panel — tarjeta «Acceso remoto»

**Archivos:**
- Modificar: `admin.html` (tarjeta nueva justo después de `#card-lg`, ~l.1124; JS junto a `instalarLg`, ~l.5039; `loadSettings` ~l.5513 llama a `accesoCargar()`)
- Crear: `tests/acceso-remoto-panel.test.js`

**Interfaces:**
- Consume: `GET/POST /api/acceso-remoto…` (Tarea 4), `toast(msg, isErr)`.
- Produce: funciones globales `accesoCargar()`, `accesoActivar()`, `accesoDesactivar()`, `accesoCopiar()`.

- [ ] **Paso 1: prueba que falla** — `tests/acceso-remoto-panel.test.js` (Node, lee `admin.html` como texto, como otras pruebas del panel): comprueba que existen `id="card-acceso"`, `id="acc-pin"` con `maxlength="6"` e `inputmode="numeric"`, que `accesoActivar`, `accesoDesactivar`, `accesoCargar` y `accesoCopiar` están definidas, que se llama a `/api/acceso-remoto/activar` y `/api/acceso-remoto/desactivar`, y que el texto «cuenta.inteksdisplay.com» aparece en la ayuda.

- [ ] **Paso 2: la tarjeta** (HTML, tras `#card-lg`):
```html
  <div class="card" id="card-acceso">
    <div class="card-title"><i class="fa-solid fa-globe"></i> Acceso remoto</div>
    <p style="font-size:12px;color:var(--muted);margin-bottom:10px">Entra al panel desde cualquier sitio, con una dirección tuya. Saca un PIN en <strong style="color:var(--text)">cuenta.inteksdisplay.com</strong> (Añadir PC), escríbelo aquí y listo.</p>
    <div id="acc-sin-pass" style="display:none;font-size:12px;color:var(--warn,#e0a030);margin-bottom:10px">Antes crea la contraseña del administrador (más abajo, en Seguridad y acceso): si no, el panel quedaría abierto a internet.</div>
    <div id="acc-form" style="display:none">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input class="finput" id="acc-pin" maxlength="6" inputmode="numeric" autocomplete="off" placeholder="PIN de 6 cifras" style="max-width:170px;letter-spacing:3px;font-family:monospace">
        <button class="btn btn-accent" id="acc-go" onclick="accesoActivar()"><i class="fa-solid fa-link"></i> Activar acceso remoto</button>
      </div>
    </div>
    <div id="acc-pasos" style="display:none;font-size:12px;color:var(--muted);margin-top:10px"></div>
    <div id="acc-activo" style="display:none">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input class="finput" id="acc-url" readonly style="flex:1;min-width:220px;font-family:monospace;font-size:12px">
        <button class="btn btn-sm" onclick="accesoCopiar()" title="Copiar"><i class="fa-solid fa-copy"></i></button>
        <button class="btn btn-ghost btn-sm" onclick="accesoDesactivar()"><i class="fa-solid fa-link-slash"></i> Desconectar</button>
      </div>
      <p id="acc-aviso" style="font-size:12px;color:var(--muted);margin-top:8px"></p>
    </div>
  </div>
```
- [ ] **Paso 3: el JS** (junto a `instalarLg`). Todo texto dinámico con `textContent`:
```js
let accTimer=null;
async function accesoCargar(){
  let e=null;
  try{ const r=await fetch("/api/acceso-remoto",{cache:"no-store"}); if(r.ok) e=await r.json(); }catch(x){}
  const card=document.getElementById("card-acceso"); if(!card||!e) return;
  const activando=e.estado==="activando";
  document.getElementById("acc-sin-pass").style.display=(!e.password&&!e.activo)?"block":"none";
  document.getElementById("acc-form").style.display=(!e.activo&&!activando&&e.password&&e.disponible)?"block":"none";
  document.getElementById("acc-activo").style.display=e.activo?"block":"none";
  const pasos=document.getElementById("acc-pasos");
  const lineas=[...(e.pasos||[])]; if(e.estado==="error") lineas.push("⚠ "+e.error);
  pasos.style.display=lineas.length&&!e.activo?"block":"none"; pasos.textContent=lineas.join("\n"); pasos.style.whiteSpace="pre-line";
  if(e.activo){
    document.getElementById("acc-url").value="https://"+e.hostname+"/";
    document.getElementById("acc-aviso").textContent=e.servicio?"Conectado. Si apagas este PC, la dirección deja de funcionar.":"El servicio de conexión no está en marcha. Pulsa Desconectar y vuelve a activar con un PIN nuevo.";
  }
  clearTimeout(accTimer); if(activando) accTimer=setTimeout(accesoCargar,1500);
}
async function accesoActivar(){
  const pin=document.getElementById("acc-pin").value.trim();
  if(!/^\d{6}$/.test(pin)){ toast("El PIN son 6 cifras",true); return; }
  const btn=document.getElementById("acc-go"); btn.disabled=true;
  try{
    const r=await fetch("/api/acceso-remoto/activar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pin})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok){ toast(d.error||"No se pudo activar",true); return; }
    document.getElementById("acc-pin").value="";
  }catch(x){ toast("No se pudo contactar con el servidor",true); return; }
  finally{ btn.disabled=false; }
  accesoCargar();
}
async function accesoDesactivar(){
  if(!confirm("¿Desconectar este PC? La dirección de internet dejará de funcionar (podrás volver a activarla con un PIN nuevo).")) return;
  try{ await fetch("/api/acceso-remoto/desactivar",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); }catch(x){}
  accesoCargar();
}
function accesoCopiar(){
  const i=document.getElementById("acc-url"); i.select();
  try{ navigator.clipboard.writeText(i.value); toast("Dirección copiada"); }catch(x){ document.execCommand("copy"); }
}
```
y en `loadSettings()` añadir `accesoCargar();` al final.

- [ ] **Paso 4: pasa** — `node --test tests/acceso-remoto-panel.test.js` y toda la suite Node.
- [ ] **Paso 5: commit** — `feat(panel): tarjeta Acceso remoto`.

---

### Tarea 6: Instalador y documentación

**Archivos:**
- Crear: `tools/descargar-cloudflared.ps1`
- Modificar: `installer/setup.iss` (sección `[Files]`), `build_installer.ps1`, `.gitignore` (`vendor/cloudflared/`), `CHANGELOG.md`, `MANUAL.md`, `GUIA-CLOUDFLARE.md` (nota que apunta a esta función)
- Test: `tests/acceso-remoto-instalador.test.js`

- [ ] **Paso 1: prueba que falla** — `tests/acceso-remoto-instalador.test.js`: lee `installer/setup.iss` y comprueba que hay una línea `Source: "..\vendor\cloudflared\cloudflared.exe"; DestDir: "{app}"; Flags: ignoreversion`, y lee `tools/descargar-cloudflared.ps1` y comprueba que contiene un hash SHA-256 de 64 hexadecimales y la URL `github.com/cloudflare/cloudflared/releases/download/`.

- [ ] **Paso 2: script de descarga** — `tools/descargar-cloudflared.ps1`: descarga `cloudflared-windows-amd64.exe` de la versión fijada (`$version`) a `vendor\cloudflared\cloudflared.exe`, calcula su SHA-256 y **aborta** si no coincide con `$hashEsperado`. Para fijar los valores: bajar una vez la versión instalada hoy (2026.10.7), calcular `Get-FileHash` y escribir ambos valores en el script (el hash se verifica contra la página de la release en GitHub antes de fijarlo). Si el archivo ya existe y el hash coincide, no vuelve a bajar.
- [ ] **Paso 3:** `build_installer.ps1` llama a ese script antes de compilar; `setup.iss` añade la línea del Paso 1 en `[Files]`.
- [ ] **Paso 4: documentación.** `CHANGELOG.md` entrada «1.0.67 — Acceso remoto con cuenta y PIN»; `MANUAL.md` sección «Acceso remoto» (para qué sirve, cómo sacar el PIN, qué pasa si apagas el PC, que cada PC tiene su dirección); una línea al principio de `GUIA-CLOUDFLARE.md` indicando que la app lo hace sola.
- [ ] **Paso 5: pasa** — `node --test tests/*.test.js`.
- [ ] **Paso 6: commit** — `feat(instalador): incluye cloudflared con su hash; docs del acceso remoto`.

---

### Tarea 7: Despliegue del Worker y prueba de punta a punta (con Axel)

No es código: son pasos reales contra Cloudflare. Los que piden credenciales los hace Axel.

- [ ] **Paso 1: KV y despliegue.** `cd cuenta && npm install && npx wrangler login` (**Axel** aprueba el inicio de sesión en el navegador) → `npx wrangler kv namespace create PCS` y poner el `id` en `wrangler.toml` → `npx wrangler deploy`.
- [ ] **Paso 2: dominio del Worker.** Añadir la ruta personalizada `cuenta.inteksdisplay.com` (Workers → inteks-cuenta → Dominios y rutas), de forma que el DNS lo cree Cloudflare.
- [ ] **Paso 3: llave de API con permisos mínimos.** Desde el navegador (Claude, sin mostrarla): Perfil → Tokens de API → crear: *Account · Cloudflare Tunnel · Edit* y *Zone · DNS · Edit* solo para `inteksdisplay.com`. Se mete como secreto con `wrangler secret put CF_API_TOKEN` pasando el valor por el portapapeles/entrada estándar, sin escribirlo en pantalla ni en archivos. Mismo procedimiento para `CF_ACCOUNT_ID`, `CF_ZONE_ID` (datos no secretos, pero van como secretos para no tocar el repo).
- [ ] **Paso 4: Access.** Zero Trust → Access → Aplicaciones → Autoalojada: `cuenta.inteksdisplay.com`, política «Permitir» solo el correo de Axel, método «código de un solo uso». Copiar el *AUD tag* y el dominio del equipo; `wrangler secret put ACCESS_AUD`, `ACCESS_EQUIPO`, `ACCESS_CORREO`. **Excepción:** en la aplicación de Access, una política *Bypass* solo para la ruta `cuenta.inteksdisplay.com/api/enlazar`, porque la llama el servidor de cada PC sin navegador. (El Worker ya exige el JWT de Access en todo lo demás.)
- [ ] **Paso 5: comprobaciones desde fuera.** `https://cuenta.inteksdisplay.com/` sin sesión pide el código por correo; `POST /api/enlazar` con un PIN cualquiera responde 400 «PIN no válido o caducado» y, tras 5, 429; `GET /api/pcs` sin sesión responde 403 o la pantalla de Access.
- [ ] **Paso 6: prueba real en este PC.** Desinstalar el servicio `cloudflared` actual (el del túnel manual «InTeks Display») y borrar ese túnel y su ruta `panel.` desde Cloudflare. En la cuenta: «Añadir PC» → `prueba` → PIN. En el panel de este PC (versión nueva ya instalada): Ajustes → Acceso remoto → PIN → Activar. Esperado: «Conectado: https://prueba.inteksdisplay.com/»; `https://prueba.inteksdisplay.com/admin.html` pide la contraseña; en la cuenta el PC sale «en línea»; «Quitar PC» lo borra y la dirección deja de resolver.
- [ ] **Paso 7: publicar.** Cuando Axel diga «Publica 1.0.67»: `tools\subir-version.ps1 1.0.67`, fecha del CHANGELOG, suite Node y Python, commit, `build_installer.ps1`, APK, `preparar-entrega.ps1`, `publicar-version.ps1`, y comprobar `version.json`.

---

## Autorrevisión frente a la spec

- **Una sola cuenta, sin registro:** Tareas 2–3 (un único correo en Access). ✔
- **Dirección elegida al sacar el PIN:** `anadirPc` + página (Tareas 2–3). ✔
- **Cloudflare Access con código por correo y JWT comprobado de verdad:** Tarea 3 (`access.js`) y Tarea 7 (política). ✔
- **Un túnel por PC:** `enlazar` crea un túnel por nombre; «Antes de instalar, desinstala el servicio previo» en Tarea 4. ✔
- **Límite de intentos por IP y global, mensaje genérico, un solo uso, 10 min:** Tareas 1–2. ✔ (La comparación del PIN es una búsqueda por clave en KV; no hay comparación carácter a carácter que filtre tiempos.)
- **Rollback si falla un paso:** Tarea 2 (pruebas DNS y token). ✔
- **No activar sin contraseña de admin, token nunca visible:** Tarea 4 (pruebas 2, 6, 9). ✔
- **Tarjeta en el panel con pasos y desconectar:** Tarea 5. ✔
- **`cloudflared` dentro del instalador con hash:** Tarea 6. ✔
- **Añadido sobre la spec, necesario para que sea seguro:** `ip_cliente()` (Tarea 4): tras el túnel todo llega desde 127.0.0.1 y el bloqueo de login compartiría contador entre todo internet; el Worker también recibe el `puerto` del servidor para no asumir el 80.
