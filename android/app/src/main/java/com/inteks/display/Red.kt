package com.inteks.display

/** La red en la que está el aparato: su IP y el prefijo de la máscara. */
data class RedLocal(val ip: String, val prefijo: Int)

/** Quien sabe pedir una URL. Se sustituye en los tests. */
interface Sondeador {
    fun pedir(url: String, timeoutMs: Int): String?
}
