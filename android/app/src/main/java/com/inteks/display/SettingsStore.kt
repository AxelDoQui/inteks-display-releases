package com.inteks.display

import android.content.Context

/**
 * Lo que la app recuerda entre arranques. Vive FUERA del WebView a propósito:
 * ver el comentario de `extraerNombrePantalla`.
 */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("inteks", Context.MODE_PRIVATE)

    var base: String?
        get() = prefs.getString("base", null)
        set(v) { prefs.edit().putString("base", v).apply() }

    var nombrePantalla: String?
        get() = prefs.getString("pantalla", null)
        set(v) { prefs.edit().putString("pantalla", v).apply() }

    /**
     * Hasta cuándo dejar la caja en paz (`SystemClock.elapsedRealtime`).
     *
     * Lo lee también `LatidoReceiver`, que vive en otro proceso al saltar la
     * alarma: por eso está aquí y no en un campo de la actividad.
     */
    var mantenimientoHasta: Long
        get() = prefs.getLong("mantenimiento", 0L)
        set(v) { prefs.edit().putLong("mantenimiento", v).apply() }

    /** Epoch ms de la última carga buena del reproductor (0 = nunca). */
    var ultimaConexionOk: Long
        get() = prefs.getLong("ultimaConexionOk", 0L)
        set(v) { prefs.edit().putLong("ultimaConexionOk", v).apply() }
}
