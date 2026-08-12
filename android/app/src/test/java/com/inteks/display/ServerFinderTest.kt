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
}
