package com.inteks.display

import org.junit.Assert.assertEquals
import org.junit.Test

class UrlsTest {

    @Test
    fun `saca el nombre de la url del player`() {
        assertEquals("Escaparate",
            extraerNombrePantalla("http://192.168.0.63/player.html?screen=Escaparate"))
    }

    @Test
    fun `deshace el escapado del nombre con espacios y acentos`() {
        assertEquals("Pantalla Exterior (LG)",
            extraerNombrePantalla("http://192.168.0.63/player.html?screen=Pantalla%20Exterior%20(LG)"))
        assertEquals("Caja Nº2",
            extraerNombrePantalla("http://192.168.0.63/player.html?screen=Caja%20N%C2%BA2"))
    }

    @Test
    fun `las paginas que no son el player no dan nombre`() {
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/pair"))
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/"))
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/player.html?preview=1"))
        assertEquals(null, extraerNombrePantalla("http://192.168.0.63/player.html?screen="))
    }

    @Test
    fun `una url rota no revienta`() {
        assertEquals(null, extraerNombrePantalla(""))
        assertEquals(null, extraerNombrePantalla("no-es-una-url"))
    }

    @Test
    fun `sin nombre guardado se arranca por la raiz y decide la web`() {
        assertEquals("http://192.168.0.63/", urlDeArranque("http://192.168.0.63", null))
    }

    @Test
    fun `con nombre guardado se va directo al player, aunque la ip sea otra`() {
        assertEquals("http://192.168.0.70/player.html?screen=Escaparate",
            urlDeArranque("http://192.168.0.70", "Escaparate"))
    }

    @Test
    fun `el nombre se vuelve a escapar al construir la url`() {
        assertEquals("http://192.168.0.70/player.html?screen=Pantalla+Exterior",
            urlDeArranque("http://192.168.0.70", "Pantalla Exterior"))
    }
}
