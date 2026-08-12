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
}
