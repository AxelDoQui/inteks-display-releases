package com.inteks.display

const val ESPERA_MINIMA_MS = 2_000L
const val ESPERA_MAXIMA_MS = 60_000L

/**
 * Cuánto esperar antes del siguiente intento: 2, 4, 8, 16, 32, 60, 60…
 *
 * No se rinde nunca. Una pantalla de escaparate tiene todo el tiempo del mundo;
 * lo que no puede es quedarse muerta esperando a que alguien la toque, porque
 * no hay nadie que la vaya a tocar.
 */
fun esperaMs(intento: Int): Long {
    if (intento <= 0) return ESPERA_MINIMA_MS
    if (intento >= 5) return ESPERA_MAXIMA_MS
    return ESPERA_MINIMA_MS shl intento
}
