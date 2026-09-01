package com.inteks.display

/** Qué hacer cuando el barrido termina sin encontrar servidor. */
enum class SinServidor {
    /** Quedarse en «Buscando…» y volver a intentarlo. No se rinde nunca. */
    SEGUIR_ESPERANDO,

    /** Abrir la pantalla para escribir la dirección a mano. */
    PEDIR_DIRECCION
}

/**
 * La decisión que se tomaba mal tras un corte de luz.
 *
 * Pedir la dirección solo tiene sentido si hay ALGUIEN DELANTE, y eso solo
 * pasa cuando la caja se está instalando. En cualquier otro momento el
 * formulario acaba puesto en un escaparate, a la vista de la calle, donde
 * nadie lo va a rellenar: el manual promete que «no hay que escribir ninguna
 * dirección con el mando».
 *
 * Que ya haya una dirección guardada demuestra que esta caja estuvo
 * funcionando alguna vez, así que lo que falta no es el dato — es que el
 * ordenador de la tienda termine de arrancar. Puede tardar minutos; una
 * pantalla de escaparate tiene todo el tiempo del mundo para esperarlo.
 */
fun queHacerSinServidor(algoPintado: Boolean, baseGuardada: String?): SinServidor =
    if (algoPintado || !baseGuardada.isNullOrEmpty()) {
        SinServidor.SEGUIR_ESPERANDO
    } else {
        SinServidor.PEDIR_DIRECCION
    }

/**
 * ¿Está alguien pidiendo escribir la dirección a mano?
 *
 * Existe porque el arreglo de arriba cierra la única puerta que había al
 * formulario: si una caja ya instalada nunca lo abre sola, una que se mude a
 * una red donde el barrido no llega —solo se barren redes /24 o menores— se
 * quedaría buscando para siempre sin manera de configurarla salvo con ADB.
 *
 * La condición es «hay una persona delante», y una pulsación del mando es la
 * prueba: un escaparate desatendido no pulsa teclas. Solo vale mientras la
 * pantalla de búsqueda está puesta; con el reproductor en marcha, OK es suyo.
 */
fun esPeticionDeDireccion(codigoTecla: Int, algoPintado: Boolean): Boolean {
    if (algoPintado) return false
    return codigoTecla == android.view.KeyEvent.KEYCODE_DPAD_CENTER ||
        codigoTecla == android.view.KeyEvent.KEYCODE_ENTER
}

/** Espera entre intentos cuando no hay servidor y no hay nada pintado. */
const val ESPERA_SIN_NADA_MS = 15_000L

/**
 * Cuánto esperar antes de volver a intentarlo, sin servidor a la vista.
 *
 * No es la misma prisa en los dos casos. Con el escaparate en marcha la
 * tienda ya está servida desde la caché y barrer la subred cada poco son 508
 * peticiones por vuelta sin ninguna urgencia. Con la pantalla en gris —el
 * arranque tras un corte de luz— cada segundo de espera es un segundo de
 * escaparate vacío, así que se reintenta al ritmo que tenía la pantalla de
 * ajustes, que es la que este camino sustituye.
 */
fun esperaSinServidorMs(algoPintado: Boolean): Long =
    if (algoPintado) ESPERA_MAXIMA_MS else ESPERA_SIN_NADA_MS
