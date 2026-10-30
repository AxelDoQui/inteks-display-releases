package com.inteks.display

/**
 * Línea de diagnóstico de la pantalla de mantenimiento. Pura, para probarla
 * sin Android. `ultimaOk` en epoch ms (0 = nunca); `ahora` también.
 */
fun textoDiagnostico(
    version: String,
    base: String?,
    pantalla: String?,
    ultimaOk: Long,
    ahora: Long,
): String {
    val servidor = if (base.isNullOrBlank()) "ninguno" else base
    val nombre = if (pantalla.isNullOrBlank()) "sin nombre" else pantalla
    val cuando = if (ultimaOk <= 0L) "nunca" else hace(maxOf(0L, ahora - ultimaOk))
    return "Versión APK $version · Servidor $servidor · Pantalla $nombre · " +
        "Última conexión buena: $cuando"
}

private fun hace(ms: Long): String {
    val min = ms / 60_000L
    return when {
        min < 1 -> "hace un momento"
        min < 60 -> "hace $min min"
        min < 24 * 60 -> "hace ${min / 60} h"
        else -> {
            val d = min / (24 * 60)
            if (d == 1L) "hace 1 día" else "hace $d días"
        }
    }
}
