# La ayuda del panel, por familia de aparato

> 2026-09-01. Sale de un encargo: «hay que poner en la ayuda toda la info
> necesaria para varios modelos de TV y para cuando se usa un Amazon Stick o una
> cajita Android TV».

## El problema

**La página de Ayuda no menciona ningún aparato.** Tiene tres tarjetas —conectar
pantallas, la extensión de Chrome y los módulos— y ninguna dice con qué
reproducir ni cómo dejarlo montado. Todo lo que sabemos de aparatos vive en
`MANUAL.md`, que es un archivo del repositorio y no está donde se necesita: al
lado del panel, con una pantalla fallando delante.

**Y la tarjeta que hay engaña.** «Conectar pantallas» describe un flujo de
desarrollo de una versión temprana:

| Dice hoy | La realidad |
|---|---|
| «Ejecuta `python server.py` en el portátil» | Lo arranca la tarea programada; en una tienda nadie ejecuta Python |
| `http://IP:8080/player.html?screen=…` | El puerto es **80**, con **9000** de reserva (`config.json`) |
| Abrir Chrome en cada tablet con su URL a mano | Hoy se **empareja por PIN** desde `/pair` |

Eso es peor que la ausencia de información: quien la siga hoy no conecta nada.
Se arregla en el mismo movimiento.

## Decisiones tomadas

1. **Por familias de aparato, no por modelo.** No se escriben pasos
   modelo a modelo que nadie haya comprobado. Lo que entra es lo verificado.
2. **El panel manda; el manual resume.** La Ayuda pasa a ser el texto largo y
   bueno. `MANUAL.md` → *Con qué reproducir* queda como resumen corto que
   remite a ella. **Una sola copia larga**, porque no hay paso de compilación
   con el que generar una de la otra y dos textos escritos a mano se separan —
   como ya pasó con las divisas y con `CURRENCY_DB`.
3. **Estructura: una tarjeta por familia**, dentro de la página de Ayuda que ya
   existe. No se añade entrada al menú lateral, que ya tiene quince.

4. **Plegables con `<details>`/`<summary>`, todas cerradas al abrir.** Esto es
   un **patrón nuevo** en `admin.html` —hoy hay 24 `class="card"` y ninguna se
   pliega; los `toggle*` que existen son JS a medida para otras cosas— y se
   introduce a propósito, por dos razones:

   - **Cero JavaScript.** `<details>` es nativo desde Chrome 12. Un acordeón a
     mano serían funciones nuevas en un archivo de 226 KB para algo que el
     navegador ya hace.
   - **Se consulta desde el móvil.** Seis familias abiertas de golpe son un
     muro de scroll en un teléfono, que es justo donde se lee esto: de pie,
     delante de la pantalla que falla.

   El `<summary>` se estiliza para que parezca un `card-title` y no rompa la
   línea visual del resto del panel.

## Contenido: las cinco familias

Cada afirmación de abajo tiene origen comprobado en este proyecto. **Nada que no
esté en esta tabla se escribe como hecho.**

| Tarjeta | Qué cuenta | De dónde sale |
|---|---|---|
| **Tablet o móvil** | Lo más fácil. Navegador, emparejar por PIN, nada que instalar | El flujo real de `pair.html` y `/api/pair` |
| **Smart TV con navegador propio** | Sirve para empezar y para una pantalla que se apaga de noche. **Aviso:** un LG con webOS cerraba el navegador solo cada ~2 minutos; se descartaron protector de pantalla, ahorro de energía, HDMI-CEC/SimpLink y el propio programa —se probó con la versión corregida y siguió—. **No tiene arreglo por código: se cambia el aparato** | Caso de campo cerrado el 2026-08-11, en *Gotchas de despliegue* |
| **Caja Android TV** | La recomendada para escaparate. Dos caminos: la app de InTeks (encuentra el servidor sola, arranca al encender, enciende el televisor; **5×ATRÁS** para mantenimiento, **OK** en «Buscando…» para escribir la dirección) o Fully Kiosk (~7 €) con *Keep Screen On*, *Start on Boot*, *Kiosk Mode* y el salvapantallas **desactivado** | La app (1.0.26–1.0.32) y `MANUAL.md` |
| **Amazon Fire TV Stick** | Es Android por debajo, se instala igual y le aplican las mismas pegas. **Se dice explícitamente que no está probado** | Ver «Lo que no se promete» |
| **Mini PC** | Chrome en modo kiosco. El más caro y el más previsible | — |

### Tarjeta transversal: «Si algo se ve mal»

| Síntoma | Qué decir | Origen |
|---|---|---|
| Faltan trozos por los bordes | Subir el **margen de seguridad** de esa pantalla (0–5 %, en la ventana de Playlist) | 1.0.33 |
| No llena la pantalla, o la letra sale diminuta | Actualizar a la **1.0.33**: las cajas con navegador antiguo se saltaban medio centenar de reglas de estilo | 1.0.33 |
| El enlace no carga en una caja Android | Usar **la IP**, nunca `signage.local`: Android no resuelve mDNS; iOS y macOS sí | *Gotchas de despliegue* |
| La pantalla no responde al tacto | Las cajas que declaran `leanback` **no tienen táctil**. No es un fallo | Medido en la MXQ |
| Una tablet o TV no entra desde otro aparato | Cortafuegos: la regla la crea el instalador desde la 1.0.14, y va con **perfil «Cualquiera»**, no «Privado» | *Gotchas de despliegue* |

## Lo que no se promete

**Del Fire TV Stick no hay ni una comprobación.** Fire OS es Android y admite
instalar APKs de lado, así que la app *debería* funcionar — pero «debería» no es
«funciona»: la app declara `leanback` y apunta a API 28, y Fire OS puede
comportarse distinto. **La tarjeta lo dirá tal cual: «no lo hemos probado
todavía».**

Una ayuda que promete lo que nadie ha visto es peor que una incompleta: el que
se fía se planta en la tienda con un aparato que no arranca. Si algún día hay un
Fire Stick delante, se prueba y esa nota se cae.

## Fuera de alcance

- No se escriben pasos modelo a modelo (Samsung Tizen, LG webOS, Sony…).
- No se toca el player ni el servidor: esto es solo la página de Ayuda de
  `admin.html` y el recorte de `MANUAL.md`.
- No se añade entrada al menú lateral.

## Verificación

1. `npm test` en verde — no debería verse afectado, pero `admin.html` se toca y
   varios tests extraen bloques suyos.
2. **Renderizar la página de Ayuda y leerla**, con el arnés de siempre: el
   `<style>` real más el markup, servido y fotografiado. Un muro de texto que
   no cabe o unas tarjetas plegables que no pliegan no los caza ningún test.
3. Comprobar a 560 px de ancho, que es el punto de corte del móvil: la ayuda se
   consulta con el teléfono en la mano, delante de la pantalla que falla.
