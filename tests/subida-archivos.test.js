/**
 * Subida de archivos del panel: progreso real, un fallo no para el resto y el
 * resumen no dice «subido» de lo que el servidor no confirmó.
 *
 * Ejecutar:  node --test tests/subida-archivos.test.js
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ADMIN = path.join(__dirname, "..", "admin.html");
const INICIO = "// ── Subida de archivos";
const FIN = "// ── fin de la subida";

function cargar() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf(INICIO);
  const b = src.indexOf(FIN, a + 1);
  if (a === -1 || b === -1 || b <= a) throw new Error("No se encuentra el bloque de subida en admin.html");
  const ctx = { JSON, Object, Array, Promise, encodeURIComponent, Math, String };
  vm.createContext(ctx);
  vm.runInContext(src.slice(a, b), ctx);
  return ctx;
}

// XHR falso: responde según el nombre del archivo.
function fabricaXHR(respuestas) {
  return () => {
    const x = {
      upload: {}, status: 0, responseText: "", _url: "",
      open(_m, url) { this._url = url; },
      setRequestHeader() {},
      abort() { this.onabort && this.onabort(); },
      send(file) {
        const r = respuestas[file.name] || { status: 200, cuerpo: { ok: true, item: { id: "1_" + file.name, name: file.name } } };
        setImmediate(() => {
          if (r.red) return this.onerror();
          this.upload.onprogress && this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
          this.status = r.status; this.responseText = JSON.stringify(r.cuerpo);
          this.onload();
        });
      },
    };
    return x;
  };
}

test("resumenSubida cuenta subidos y fallidos con el motivo", () => {
  const { resumenSubida } = cargar();
  const r = resumenSubida([
    { ok: true, nombre: "a.png" }, { ok: true, nombre: "b.png" },
    { ok: false, nombre: "c.txt", error: "No es una imagen ni un vídeo" },
  ]);
  assert.strictEqual(r.subidos, 2);
  assert.strictEqual(r.fallidos, 1);
  assert.strictEqual(r.hayError, true);
  assert.match(r.texto, /2 subidos/);
  assert.match(r.texto, /1 falló/);
  assert.match(r.texto, /c\.txt/);
  assert.match(r.texto, /No es una imagen/);
});

test("resumenSubida sin fallos no habla de errores", () => {
  const { resumenSubida } = cargar();
  const r = resumenSubida([{ ok: true, nombre: "a.png" }]);
  assert.strictEqual(r.hayError, false);
  assert.match(r.texto, /1 subido/);
  assert.doesNotMatch(r.texto, /falló/);
});

test("resumenSubida: todo cancelado no es un error", () => {
  const { resumenSubida } = cargar();
  const r = resumenSubida([{ ok: false, nombre: "a.mp4", error: "Cancelado", cancelado: true }]);
  assert.strictEqual(r.hayError, false);
  assert.match(r.texto, /cancel/i);
});

test("subirUno: éxito devuelve el item del servidor", async () => {
  const { subirUno } = cargar();
  const r = await subirUno({ name: "a.png" }, fabricaXHR({}), () => {}, {});
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.item.id, "1_a.png");
});

test("subirUno: rechazo del servidor trae su motivo", async () => {
  const { subirUno } = cargar();
  const xhr = fabricaXHR({ "x.png": { status: 415, cuerpo: { ok: false, error: "No es una imagen ni un vídeo" } } });
  const r = await subirUno({ name: "x.png" }, xhr, () => {}, {});
  assert.strictEqual(r.ok, false);
  assert.match(r.error, /No es una imagen/);
});

test("subirUno: se perdió la red", async () => {
  const { subirUno } = cargar();
  const r = await subirUno({ name: "x.png" }, fabricaXHR({ "x.png": { red: true } }), () => {}, {});
  assert.strictEqual(r.ok, false);
  assert.match(r.error, /conexión/);
});

test("subirUno informa del progreso como fracción", async () => {
  const { subirUno } = cargar();
  const visto = [];
  await subirUno({ name: "a.png" }, fabricaXHR({}), f => visto.push(f), {});
  assert.deepStrictEqual(visto, [0.5]);
});

test("subirUno: ctl.abort cancela y lo marca", async () => {
  const { subirUno } = cargar();
  const ctl = {};
  const xhr = () => {
    const x = { upload: {}, open() {}, setRequestHeader() {}, send() {}, abort() { this.onabort(); } };
    return x;
  };
  const p = subirUno({ name: "a.mp4" }, xhr, () => {}, ctl);
  ctl.abort();
  const r = await p;
  assert.strictEqual(r.cancelado, true);
  assert.strictEqual(r.ok, false);
});

test("subirArchivos: un fallo no detiene los demás y se avisa de cada uno", async () => {
  const { subirArchivos } = cargar();
  const xhr = fabricaXHR({ "b.txt": { status: 415, cuerpo: { ok: false, error: "No es una imagen ni un vídeo" } } });
  const eventos = [];
  const res = await subirArchivos(
    [{ name: "a.png" }, { name: "b.txt" }, { name: "c.png" }], xhr,
    { alEmpezar: (i, t) => eventos.push("E" + i + "/" + t), alProgreso() {},
      alTerminar: (i, r) => eventos.push("T" + i + (r.ok ? "ok" : "mal")), cancelado: () => false });
  assert.deepStrictEqual(Array.from(res, r => r.ok), [true, false, true]);
  assert.deepStrictEqual(eventos, ["E0/3", "T0ok", "E1/3", "T1mal", "E2/3", "T2ok"]);
});

test("subirArchivos: si se cancela, los siguientes quedan cancelados", async () => {
  const { subirArchivos } = cargar();
  let cancelar = false;
  const res = await subirArchivos(
    [{ name: "a.png" }, { name: "b.png" }, { name: "c.png" }], fabricaXHR({}),
    { alEmpezar() {}, alProgreso() {}, alTerminar: () => { cancelar = true; }, cancelado: () => cancelar });
  assert.strictEqual(res.length, 3);
  assert.strictEqual(res[0].ok, true);
  assert.strictEqual(res[1].cancelado, true);
  assert.strictEqual(res[2].cancelado, true);
});

// XHR que cuenta los send y se queda esperando (para abortar a mitad).
function xhrContador(cuenta) {
  return () => ({ upload: {}, open() {}, setRequestHeader() {},
    send() { cuenta.n++; }, abort() { this.onabort(); } });
}

test("subirArchivos: abort a mitad cancela el actual y no envía los demás", async () => {
  const { subirArchivos } = cargar();
  const cuenta = { n: 0 }; const ctl = {}; let cancelar = false;
  const p = subirArchivos([{ name: "a.mp4" }, { name: "b.png" }, { name: "c.png" }], xhrContador(cuenta),
    { ctl, alEmpezar() {}, alProgreso() {}, alTerminar() {}, cancelado: () => cancelar });
  await new Promise(r => setImmediate(r));
  cancelar = true; ctl.abort();
  const res = await p;
  assert.strictEqual(cuenta.n, 1);
  assert.strictEqual(res.length, 3);
  assert.ok(res.every(r => r.cancelado));
});

test("excedeMaximo compara contra MB", () => {
  const { excedeMaximo } = cargar();
  assert.strictEqual(excedeMaximo({ size: 11 * 1024 * 1024 }, 10), true);
  assert.strictEqual(excedeMaximo({ size: 10 * 1024 * 1024 }, 10), false);
  assert.strictEqual(excedeMaximo({ size: 1e12 }, undefined), false);
});

test("subirArchivos: no envía el que pasa del máximo y sigue con el resto", async () => {
  const { subirArchivos } = cargar();
  const cuenta = { n: 0 };
  const base = fabricaXHR({});
  const xhr = () => { const x = base(); const s = x.send.bind(x); x.send = f => { cuenta.n++; s(f); }; return x; };
  const res = await subirArchivos(
    [{ name: "a.png", size: 10 }, { name: "grande.mp4", size: 5 * 1024 * 1024 }, { name: "c.png", size: 10 }], xhr,
    { maxMb: 1, alEmpezar() {}, alProgreso() {}, alTerminar() {}, cancelado: () => false });
  assert.strictEqual(cuenta.n, 2);
  assert.deepStrictEqual(Array.from(res, r => r.ok), [true, false, true]);
  assert.match(res[1].error, /Pasa del máximo de 1 MB por archivo/);
});

test("tipoPorCabecera espeja al servidor", () => {
  const { tipoPorCabecera } = cargar();
  const b = (...v) => { const a = new Uint8Array(Math.max(12, v.length)); a.set(v); return a; };
  const asc = s => Array.from(s, c => c.charCodeAt(0));
  assert.strictEqual(tipoPorCabecera(b(0xff, 0xd8, 0xff, 0xe0)), "image");
  assert.strictEqual(tipoPorCabecera(b(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)), "image");
  assert.strictEqual(tipoPorCabecera(b(...asc("GIF89a"))), "image");
  assert.strictEqual(tipoPorCabecera(b(...asc("GIF87a"))), "image");
  assert.strictEqual(tipoPorCabecera(b(...asc("RIFF"), 0, 0, 0, 0, ...asc("WEBP"))), "image");
  assert.strictEqual(tipoPorCabecera(b(0, 0, 0, 0x18, ...asc("ftypmp42"))), "video");
  assert.strictEqual(tipoPorCabecera(b(0x1a, 0x45, 0xdf, 0xa3)), "video");
  assert.strictEqual(tipoPorCabecera(b(0, 0, 0, 0x18, ...asc("ftypheic"))), null);
  assert.strictEqual(tipoPorCabecera(b(0, 0, 0, 0x18, ...asc("ftypavif"))), null);
  assert.strictEqual(tipoPorCabecera(b(...asc("hola, soy texto"))), null);
});

test("subirArchivos: no envía el que tiene cabecera inválida y sigue con el resto", async () => {
  const { subirArchivos } = cargar();
  const cuenta = { n: 0 };
  const base = fabricaXHR({});
  const xhr = () => { const x = base(); const s = x.send.bind(x); x.send = f => { cuenta.n++; s(f); }; return x; };
  const falso = (name, bytes) => ({ name, size: 10, slice: () => ({ arrayBuffer: async () => Uint8Array.from(bytes).buffer }) });
  const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0];
  const eventos = [];
  const res = await subirArchivos(
    [falso("a.png", png), falso("malo.png", Array.from("texto de prueba", c => c.charCodeAt(0))), falso("c.png", png)], xhr,
    { alEmpezar: i => eventos.push("E" + i), alProgreso() {}, alTerminar: i => eventos.push("T" + i), cancelado: () => false });
  assert.strictEqual(cuenta.n, 2);
  assert.deepStrictEqual(Array.from(res, r => r.ok), [true, false, true]);
  assert.match(res[1].error, /No es una imagen ni un vídeo que se pueda mostrar/);
  assert.deepStrictEqual(eventos, ["E0", "T0", "E1", "T1", "E2", "T2"]);
});
