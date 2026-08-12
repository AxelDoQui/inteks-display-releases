package com.inteks.display

import java.net.URLDecoder
import java.net.URLEncoder

/**
 * El nombre de pantalla que lleva dentro una URL del player, o null.
 *
 * Existe porque `localStorage` y las cookies van por ORIGEN: si el PC cambia de
 * IP, `http://192.168.0.63` y `http://192.168.0.70` son sitios distintos para
 * el navegador y la pantalla perdería su identidad. Guardando el nombre fuera
 * del WebView, un cambio de IP deja de importar.
 */
fun extraerNombrePantalla(url: String): String? {
    val i = url.indexOf("/player.html?")
    if (i < 0) return null
    val consulta = url.substring(i + "/player.html?".length)
    for (par in consulta.split("&")) {
        val trozos = par.split("=", limit = 2)
        if (trozos.size == 2 && trozos[0] == "screen" && trozos[1].isNotEmpty()) {
            return try { URLDecoder.decode(trozos[1], "UTF-8") } catch (e: Exception) { null }
        }
    }
    return null
}

/**
 * Por dónde empezar a cargar. Sin nombre guardado se entra por la raíz y decide
 * `index.html`, que ya sabe enrutar a emparejar o a reproducir.
 */
fun urlDeArranque(base: String, nombrePantalla: String?): String {
    if (nombrePantalla.isNullOrEmpty()) return "$base/"
    val escapado = URLEncoder.encode(nombrePantalla, "UTF-8")
    return "$base/player.html?screen=$escapado"
}
