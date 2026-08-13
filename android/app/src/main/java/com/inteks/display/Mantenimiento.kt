package com.inteks.display

/** Pulsaciones de ATRAS seguidas que abren la salida de mantenimiento. */
const val PULSACIONES_SALIDA = 5

/** En cuánto tiempo tienen que caber esas pulsaciones. */
const val VENTANA_PULSACIONES_MS = 3_000L

/** Cuánto se queda la app apartada tras pedir salir. */
const val MANTENIMIENTO_MS = 5 * 60 * 1000L

/**
 * Anota una pulsación y devuelve la lista recortada.
 *
 * Se recorta a las últimas `PULSACIONES_SALIDA` para que una pantalla que lleve
 * meses encendida no acumule una lista infinita de pulsaciones.
 */
fun registrarPulsacion(previas: List<Long>, ahora: Long): List<Long> =
    (previas + ahora).takeLast(PULSACIONES_SALIDA)

/**
 * ¿Está el usuario pidiendo salir?
 *
 * Cinco pulsaciones de ATRAS en menos de tres segundos. La tecla ATRAS no hace
 * nada en el kiosco, así que no hay forma de disparar esto sin querer: una
 * pulsación suelta, o cinco repartidas mientras alguien trastea, no cuentan.
 */
fun esSalidaDeMantenimiento(pulsaciones: List<Long>, ahora: Long): Boolean {
    if (pulsaciones.size < PULSACIONES_SALIDA) return false
    val recientes = pulsaciones.filter { ahora - it <= VENTANA_PULSACIONES_MS }
    return recientes.size >= PULSACIONES_SALIDA
}
