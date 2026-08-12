# Bot de Telegram que responde — diseño

> Estado: **implementado en la 1.0.19** (2026-08-12). Las cuatro preguntas
> abiertas de «Qué queda por decidir» se cerraron ese mismo día — ver las
> respuestas al final del documento. Código en `_bot_loop()`,
> `construir_estado()` y `_responder_mensaje()` en `server.py`; tests en
> `tests/test_bot_estado.py`.

## El problema

Hoy Telegram es de una sola dirección: el servidor empuja avisos
(`enviar_telegram()`, pantalla caída, pantalla que vuelve, tasas viejas, disco
lleno). Para saber cualquier otra cosa —desde cuándo está caída una pantalla,
cuándo se actualizaron las tasas— hay que abrir el panel, y el panel está en la
tienda.

Lo que se pidió: poder **preguntarle al bot** desde el móvil.

## Decidido con el usuario

| Decisión | Elegido | Por qué |
|---|---|---|
| Qué avisa | **Nada nuevo.** Se descartó avisar de cambios de tasas | Lo pidió y lo retiró en la misma conversación. Los avisos que existen se quedan como están |
| Cómo se pregunta | **Un solo `/estado`** que lo cuenta todo | Con dos pantallas y dos tableros cabe en un mensaje. En el móvil es un toque, sin recordar comandos |
| Qué puede hacer | **Solo informar** | Un chat no puede ser una llave: nada de reiniciar el servidor ni de dar el PIN de emparejamiento |
| Cómo recibe los mensajes | **`getUpdates` con espera larga**, desde el servidor | Sin abrir puertos ni depender de tener dominio. Mismo modelo de solo-salidas que ya usa para enviar |

### Por qué no las otras dos vías

**Webhook** (Telegram llama al servidor): cero tráfico en reposo y respuesta
instantánea, pero exige URL pública con HTTPS. Solo funcionaría en
instalaciones con el túnel de Cloudflare, que no es el caso normal de una
tienda. Descartado.

**Mirar una vez por minuto** aprovechando el vigilante que ya existe: lo más
sencillo, sin hilo nuevo, pero preguntas «¿está viva la caja?» y tardas hasta
un minuto en saberlo. Un bot que tarda un minuto parece roto y se deja de usar.

## Forma de la solución

Un hilo demonio, hermano del vigilante de avisos, que llama a `getUpdates` con
`timeout=25` en bucle. Solo arranca si hay `telegram_token` configurado, y
relee la configuración en cada vuelta, como hace `enviar_telegram()`.

**Contenido de `/estado`**: por cada pantalla, si está en línea o desde cuándo
no lo está (`screens.json`, `last_seen`); por cada tablero de divisas, cuándo
se actualizó y si está fuera de plazo (`updated_at`, la misma regla que usa
`tasasCaducadas`). Sin inventar datos nuevos: todo esto ya existe.

**Lo que ninguna versión de esto puede resolver:** si el PC de la tienda está
apagado o sin internet, el bot no contesta — y «no contesta» es justo lo que
pasaría cuando más quieres preguntarle. Para eso están los avisos que se
empujan, que sí salen antes de que el equipo muera. Conviene decirlo en el
manual para no vender lo que no es.

## Riesgos conocidos

- **Reconexión.** Es el mismo terreno donde vivía la fuga del SSE: una espera
  larga contra un servidor remoto, en el WiFi de una tienda. Espera creciente
  entre reintentos, sin excepciones que suban, y nada que pueda tumbar el
  servidor. Un aviso que falla es un aviso; el escaparate es el negocio.
- **Mensajes atrasados.** Telegram guarda lo no leído 24 h. Tras un reinicio,
  el bot no debe contestar a un `/estado` de ayer: al arrancar se descarta el
  pendiente (`getUpdates` con `offset=-1`) en vez de procesarlo.
- **Quién pregunta.** Solo se responde al `telegram_chat_id` configurado; a
  cualquier otro, silencio. Un bot es público: quien sepa su nombre puede
  escribirle.

## Cómo se prueba

`tests/test_avisos.py` ya levanta un **Telegram de mentira** en local
(`FalsoTelegram`, puerto 8196) y apunta `srv.TELEGRAM_API` ahí. La misma receta
sirve para `getUpdates`: el falso devuelve mensajes preparados y se comprueba
qué contesta el servidor. Sin internet y sin mandarle nada a nadie.

## Qué quedaba por decidir (cerrado 2026-08-12)

1. **Cada cuánto se relee la configuración** — en cada vuelta del bucle,
   igual que `enviar_telegram()`. Sin token o chat configurado, el hilo no
   llama a Telegram: duerme 5 s y vuelve a mirar. Si el token cambia (se
   activa el bot, o se reemplaza), la vuelta siguiente lo detecta y repite el
   descarte de pendientes con `offset=-1` antes de seguir. No hace falta
   reiniciar el servidor para que un cambio en el panel se note.
2. **Formato del mensaje** — bloques cortos con emoji por estado (`✅`/`❌` en
   pantallas, `✅`/`⚠` en tableros), nombre de la instalación arriba y
   versión + disco al pie. Ver `construir_estado()`. No se validó a mano en
   un móvil real, solo por texto — si el mensaje se ve mal en pantallas
   pequeñas o listas largas, es lo primero a revisar.
3. **Qué contesta a lo que no entiende** — una línea de ayuda («No entendí.
   Escribe /estado…»), solo al chat autorizado. Silencio total a cualquier
   otro chat, tal y como estaba decidido para el acceso.
4. **Disco y versión** — sí, van en el mensaje, reutilizando `estado_disco()`
   y `APP_VERSION` (los mismos que ya calcula `/api/info`).
