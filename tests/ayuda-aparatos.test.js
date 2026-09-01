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

const FAMILIAS = [
  "Tablet o móvil",
  "Televisor con su propio navegador",
  "Caja Android TV",
  "Amazon Fire TV Stick",
  "Mini PC"
];

test("hay una tarjeta por familia de aparato", () => {
  const h = ayuda();
  const faltan = FAMILIAS.filter(f => !h.includes(f));
  assert.deepStrictEqual(faltan, [],
    "Faltan tarjetas de aparato en la ayuda:\n  " + faltan.join("\n  "));
});

/**
 * Del Fire TV Stick NO hay ninguna comprobacion. Fire OS es Android y admite
 * instalar APKs de lado, asi que la app deberia funcionar — pero «deberia» no
 * es «funciona», y la app declara leanback y apunta a API 28.
 *
 * Prometer lo que nadie ha visto manda a alguien a una tienda con un aparato
 * que no arranca. Cuando alguien lo pruebe de verdad, se quita el aviso Y se
 * quita este test, en el mismo commit.
 */
test("el Fire TV Stick sigue marcado como no probado", () => {
  const h = ayuda();
  const i = h.indexOf("Amazon Fire TV Stick");
  assert.ok(i >= 0, "no está la tarjeta del Fire TV Stick");
  const tarjeta = h.slice(i, i + 2000).toLowerCase();
  assert.ok(tarjeta.includes("no lo hemos probado"),
    "La tarjeta del Fire TV Stick ha perdido el aviso de que no está probado.\n" +
    "Si es que ya se probó, quita también este test. Si no, devuélvelo.");
});

const SINTOMAS = [
  "Faltan trozos por los bordes",
  "No llena la pantalla",
  "No carga en la caja Android",
  "No responde al tacto",
  "Desde otro aparato no entra"
];

test("la ayuda cubre los fallos que ya han pasado en tienda", () => {
  const h = ayuda();
  const faltan = SINTOMAS.filter(s => !h.includes(s));
  assert.deepStrictEqual(faltan, [],
    "Faltan sintomas en la tarjeta de diagnostico:\n  " + faltan.join("\n  "));
});
