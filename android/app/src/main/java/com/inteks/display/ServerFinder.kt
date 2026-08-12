package com.inteks.display

/**
 * Direcciones a sondear dentro de la subred del aparato.
 *
 * Solo se barren redes de /24 o más pequeñas. Una /16 son 65.534 direcciones:
 * tardaría minutos y molestaría a la red de la tienda, así que se prefiere
 * pedirle la dirección al usuario.
 */
fun direccionesDeLaSubred(red: RedLocal): List<String> {
    if (red.prefijo < 24 || red.prefijo > 30) return emptyList()

    val partes = red.ip.split(".")
    if (partes.size != 4) return emptyList()
    val octetos = partes.map { it.toIntOrNull() ?: return emptyList() }
    if (octetos.any { it < 0 || it > 255 }) return emptyList()

    val ipNum = (octetos[0].toLong() shl 24) or (octetos[1].toLong() shl 16) or
                (octetos[2].toLong() shl 8) or octetos[3].toLong()
    val mascara = (0xFFFFFFFFL shl (32 - red.prefijo)) and 0xFFFFFFFFL
    val base = ipNum and mascara
    val difusion = base or (mascara.inv() and 0xFFFFFFFFL)

    return ((base + 1) until difusion).map { n ->
        "${(n shr 24) and 0xFF}.${(n shr 16) and 0xFF}.${(n shr 8) and 0xFF}.${n and 0xFF}"
    }
}
