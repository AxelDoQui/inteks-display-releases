package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReintentosTest {

    @Test
    fun `dobla desde dos segundos`() {
        assertEquals(2_000L, esperaMs(0))
        assertEquals(4_000L, esperaMs(1))
        assertEquals(8_000L, esperaMs(2))
        assertEquals(16_000L, esperaMs(3))
        assertEquals(32_000L, esperaMs(4))
    }

    @Test
    fun `se queda en un minuto y no sigue creciendo`() {
        assertEquals(60_000L, esperaMs(5))
        assertEquals(60_000L, esperaMs(6))
        assertEquals(60_000L, esperaMs(50))
    }

    @Test
    fun `nunca se rinde ni devuelve una espera absurda`() {
        assertEquals(60_000L, esperaMs(100_000))
        assertTrue(esperaMs(Int.MAX_VALUE) == 60_000L)
    }

    @Test
    fun `un intento negativo se trata como el primero`() {
        assertEquals(2_000L, esperaMs(-1))
    }
}
