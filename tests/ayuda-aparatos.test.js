/**
 * La ayuda del panel no puede mentir.
 *
 * La tarjeta «Conectar pantallas» describia un flujo de desarrollo de una
 * version temprana: `python server.py`, el puerto 8080 y escribir la URL a mano
 * en cada tablet. Hoy el servidor lo arranca la tarea programada, el puerto es
 * el 80 y las pantallas se emparejan por PIN. Quien siguiera esa tarjeta no
 * conectaba nada.
 *
 * Una ayuda equivocada es peor que ninguna: manda a alguien a una tienda a
 * seguir pasos que no funcionan. Este test la vigila.
 *
 * Ejecutar:  npm test
 */
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const ADMIN = path.join(__dirname, "..", "admin.html");

/** El HTML de la pagina de Ayuda, de su apertura al siguiente bloque. */
function ayuda() {
  const src = fs.readFileSync(ADMIN, "utf8");
  const a = src.indexOf('<div class="page" id="page-help">');
  assert.ok(a >= 0, "no se encuentra page-help en admin.html");
  const candidatos = [
    src.indexOf('<div class="page"', a + 10),
    src.indexOf('<div class="modal-bd"', a + 10)
  ].filter(i => i > 0);
  const b = candidatos.length ? Math.min(...candidatos) : src.length;
  return src.slice(a, b);
}

test("la ayuda no manda ejecutar python ni usar el puerto 8080", () => {
  const h = ayuda();
  const caducadas = [
    ["python server.py", "el servidor lo arranca la tarea programada"],
    [":8080",            "el puerto es el 80, con 9000 de reserva"]
  ];
  const fallos = caducadas
    .filter(([txt]) => h.includes(txt))
    .map(([txt, por]) => `«${txt}» — ${por}`);
  assert.deepStrictEqual(fallos, [],
    "La ayuda vuelve a dar instrucciones que no funcionan:\n  " + fallos.join("\n  "));
});

test("la ayuda explica el emparejamiento por PIN, que es el flujo real", () => {
  const h = ayuda().toLowerCase();
  assert.ok(h.includes("pin"), "la ayuda no menciona el PIN de emparejamiento");
});
