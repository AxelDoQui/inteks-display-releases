package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerFinderTest {

    @Test
    fun `una 24 da 254 direcciones sin la de red ni la de difusion`() {
        val d = direccionesDeLaSubred(RedLocal("192.168.0.64", 24))
        assertEquals(254, d.size)
        assertEquals("192.168.0.1", d.first())
        assertEquals("192.168.0.254", d.last())
        assertTrue(!d.contains("192.168.0.0"))
        assertTrue(!d.contains("192.168.0.255"))
    }

    @Test
    fun `la propia direccion se incluye, que el servidor podria ser este aparato`() {
        val d = direccionesDeLaSubred(RedLocal("192.168.0.64", 24))
        assertTrue(d.contains("192.168.0.64"))
    }

    @Test
    fun `una red mas grande que 24 no se barre`() {
        assertEquals(0, direccionesDeLaSubred(RedLocal("10.0.0.5", 16)).size)
        assertEquals(0, direccionesDeLaSubred(RedLocal("10.0.0.5", 8)).size)
    }

    @Test
    fun `una 25 se barre entera, que es mas pequena que una 24`() {
        val d = direccionesDeLaSubred(RedLocal("192.168.0.130", 25))
        assertEquals(126, d.size)
        assertEquals("192.168.0.129", d.first())
        assertEquals("192.168.0.254", d.last())
    }

    @Test
    fun `una ip que no es ipv4 no revienta, devuelve vacio`() {
        assertEquals(0, direccionesDeLaSubred(RedLocal("no-es-una-ip", 24)).size)
        assertEquals(0, direccionesDeLaSubred(RedLocal("", 24)).size)
    }

    @Test
    fun `una respuesta real de api info se reconoce`() {
        val real = """{"version": "1.0.25", "port": 80, "ip": "192.168.0.63",
            "mdns_host": "signage.local", "mdns_name": "signage",
            "player_url": "http://192.168.0.63/player.html"}"""
        assertTrue(esRespuestaDeInTeks(real))
    }

    @Test
    fun `otro servidor web de la red no cuela`() {
        assertTrue(!esRespuestaDeInTeks("<html><body>Router</body></html>"))
        assertTrue(!esRespuestaDeInTeks("""{"status":"ok"}"""))
        assertTrue(!esRespuestaDeInTeks("""{"version":"1.0.0"}"""))
    }

    @Test
    fun `una respuesta vacia o rota no revienta`() {
        assertTrue(!esRespuestaDeInTeks(null))
        assertTrue(!esRespuestaDeInTeks(""))
        assertTrue(!esRespuestaDeInTeks("{"))
    }

    private val respuestaBuena = """{"mdns_name":"signage","player_url":"http://x/player.html"}"""

    @Test
    fun `encuentra el servidor y devuelve su url base`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? =
                if (url == "http://192.168.0.63/api/info") respuestaBuena else null
        }
        assertEquals("http://192.168.0.63", buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `si esta en el 9000 la url base lleva el puerto`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? =
                if (url == "http://192.168.0.70:9000/api/info") respuestaBuena else null
        }
        assertEquals("http://192.168.0.70:9000", buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `si no contesta nadie devuelve null`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? = null
        }
        assertEquals(null, buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `un impostor que contesta pero no es InTeks no se elige`() {
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? = "<html>router</html>"
        }
        assertEquals(null, buscarServidor(RedLocal("192.168.0.64", 24), sondeador))
    }

    @Test
    fun `en una red que no se puede barrer no se sondea nada`() {
        var llamadas = 0
        val sondeador = object : Sondeador {
            override fun pedir(url: String, timeoutMs: Int): String? { llamadas++; return null }
        }
        assertEquals(null, buscarServidor(RedLocal("10.0.0.5", 16), sondeador))
        assertEquals(0, llamadas)
    }
}
