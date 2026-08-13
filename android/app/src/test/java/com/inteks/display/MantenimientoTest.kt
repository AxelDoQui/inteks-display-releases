package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MantenimientoTest {

    @Test
    fun `cinco pulsaciones seguidas abren la salida`() {
        val p = listOf(1000L, 1300L, 1600L, 1900L, 2200L)
        assertTrue(esSalidaDeMantenimiento(p, 2200L))
    }

    @Test
    fun `cuatro no bastan`() {
        val p = listOf(1000L, 1300L, 1600L, 1900L)
        assertTrue(!esSalidaDeMantenimiento(p, 1900L))
    }

    @Test
    fun `cinco pulsaciones repartidas en el tiempo no cuentan`() {
        // Una cada dos segundos es alguien navegando, no pidiendo salir.
        val p = listOf(0L, 2000L, 4000L, 6000L, 8000L)
        assertTrue(!esSalidaDeMantenimiento(p, 8000L))
    }

    @Test
    fun `solo cuentan las de la ventana, no las viejas`() {
        // Dos pulsaciones antiguas y tres recientes no suman cinco.
        val p = listOf(0L, 500L, 10_000L, 10_300L, 10_600L)
        assertTrue(!esSalidaDeMantenimiento(p, 10_600L))
    }

    @Test
    fun `sin pulsaciones no revienta`() {
        assertTrue(!esSalidaDeMantenimiento(emptyList(), 1000L))
    }

    @Test
    fun `la lista se recorta y no crece sin limite`() {
        var p = emptyList<Long>()
        for (i in 0 until 50) p = registrarPulsacion(p, i * 100L)
        assertTrue("la lista no puede crecer indefinidamente", p.size <= PULSACIONES_SALIDA)
    }

    @Test
    fun `registrar guarda la ultima pulsacion`() {
        val p = registrarPulsacion(listOf(100L, 200L), 300L)
        assertEquals(300L, p.last())
    }
}
