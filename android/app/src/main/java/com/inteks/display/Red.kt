package com.inteks.display

import android.content.Context
import android.net.ConnectivityManager
import java.net.HttpURLConnection
import java.net.URL

/** La red en la que está el aparato: su IP y el prefijo de la máscara. */
data class RedLocal(val ip: String, val prefijo: Int)

/** Quien sabe pedir una URL. Se sustituye en los tests. */
interface Sondeador {
    fun pedir(url: String, timeoutMs: Int): String?
}

/** Sondeador de verdad, con HttpURLConnection. Sin dependencias externas. */
class SondeadorHttp : Sondeador {
    override fun pedir(url: String, timeoutMs: Int): String? {
        var con: HttpURLConnection? = null
        return try {
            con = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                requestMethod = "GET"
                instanceFollowRedirects = false
            }
            if (con.responseCode != 200) {
                null
            } else {
                // Se leen como mucho 4 KB: /api/info son ~300 bytes, y en la red
                // puede haber un servidor sirviendo un video en el mismo puerto.
                val buf = CharArray(4096)
                con.inputStream.bufferedReader().use { r ->
                    val n = r.read(buf)
                    if (n <= 0) "" else String(buf, 0, n)
                }
            }
        } catch (e: Exception) {
            null
        } finally {
            con?.disconnect()
        }
    }
}

/** La IP y el prefijo de máscara del aparato, o null si no hay red. */
fun redLocalDe(context: Context): RedLocal? {
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    for (red in cm.allNetworks) {
        val props = cm.getLinkProperties(red) ?: continue
        for (dir in props.linkAddresses) {
            val ip = dir.address.hostAddress ?: continue
            if (ip.contains(":")) continue          // IPv6, no se barre
            if (ip.startsWith("127.")) continue     // loopback
            return RedLocal(ip, dir.prefixLength)
        }
    }
    return null
}
