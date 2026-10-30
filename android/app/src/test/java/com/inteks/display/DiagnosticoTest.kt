package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DiagnosticoTest {
    private val min = 60_000L

    @Test
    fun `texto completo con conexion reciente`() {
        val t = textoDiagnostico("1.0.49", "http://192.168.0.5:8080", "Tienda 1", 1_000_000L, 1_000_000L + 3 * min)
        assertEquals(
            "Versión APK 1.0.49 · Servidor http://192.168.0.5:8080 · Pantalla Tienda 1 · Última conexión buena: hace 3 min",
            t
        )
    }

    @Test
    fun `nunca conectada`() {
        assertTrue(textoDiagnostico("1.0.49", "http://x", "P", 0L, 5_000L).endsWith("Última conexión buena: nunca"))
    }

    @Test
    fun `base y pantalla nulos`() {
        val t = textoDiagnostico("1.0.49", null, null, 0L, 5_000L)
        assertTrue(t.contains("Servidor ninguno"))
        assertTrue(t.contains("sin nombre"))
    }

    @Test
    fun `menos de un minuto`() {
        assertTrue(textoDiagnostico("1", "b", "p", 1000L, 1000L + 20_000L).endsWith("hace un momento"))
    }

    @Test
    fun `horas y dias`() {
        assertTrue(textoDiagnostico("1", "b", "p", 1000L, 1000L + 125 * min).endsWith("hace 2 h"))
        assertTrue(textoDiagnostico("1", "b", "p", 1000L, 1000L + 3 * 24 * 60 * min).endsWith("hace 3 días"))
        assertTrue(textoDiagnostico("1", "b", "p", 1000L, 1000L + 24 * 60 * min).endsWith("hace 1 día"))
    }

    @Test
    fun `ahora anterior a la ultima conexion no sale negativo`() {
        val t = textoDiagnostico("1", "b", "p", 10_000L, 5_000L)
        assertTrue(t.endsWith("hace un momento"))
        assertTrue(!t.contains("-"))
    }
}
