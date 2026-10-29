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

test("subirArchivos: si se cancela, no empieza los siguientes", async () => {
  const { subirArchivos } = cargar();
  let cancelar = false;
  const res = await subirArchivos(
    [{ name: "a.png" }, { name: "b.png" }, { name: "c.png" }], fabricaXHR({}),
    { alEmpezar() {}, alProgreso() {}, alTerminar: () => { cancelar = true; }, cancelado: () => cancelar });
  assert.strictEqual(res.length, 1);
});
