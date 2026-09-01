package com.inteks.display

import android.view.KeyEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Qué hace la app cuando arranca y no encuentra el servidor.
 *
 * El caso que da nombre a este archivo es el corte de luz: la caja vuelve en
 * dos minutos, el ordenador de la tienda tarda más, y lo que se ve entretanto
 * está en un escaparate a la vista de la calle.
 */
class ArranqueTest {

    @Test
    fun `tras un corte de luz una caja ya instalada NO pide la direccion`() {
        // Nada pintado todavía -acaba de arrancar- pero esta caja ya sabe
        // dónde vive el servidor: lo que falta es que el ordenador termine
        // de arrancar, no que nadie le diga la dirección.
        assertEquals(
            SinServidor.SEGUIR_ESPERANDO,
            queHacerSinServidor(algoPintado = false, baseGuardada = "http://192.168.0.63")
        )
    }

    @Test
    fun `una caja recien instalada si pide la direccion`() {
        // Nunca ha visto un servidor y no hay escaparate que estropear: aquí
        // sí hay alguien delante con el mando, que es quien la está montando.
        assertEquals(
            SinServidor.PEDIR_DIRECCION,
            queHacerSinServidor(algoPintado = false, baseGuardada = null)
        )
    }

    @Test
    fun `con el escaparate en marcha nunca se pide la direccion`() {
        // El player sigue reproduciendo de su caché aunque el servidor esté
        // caído. Cambiar eso por un formulario sería tirar lo único que
        // funciona.
        assertEquals(
            SinServidor.SEGUIR_ESPERANDO,
            queHacerSinServidor(algoPintado = true, baseGuardada = "http://192.168.0.63")
        )
        assertEquals(
            SinServidor.SEGUIR_ESPERANDO,
            queHacerSinServidor(algoPintado = true, baseGuardada = null)
        )
    }

    @Test
    fun `una base guardada vacia cuenta como no tener ninguna`() {
        // Defensa: si algo dejó la clave escrita pero vacía, no puede
        // convertirse en una caja que se queda esperando para siempre sin
        // manera de configurarla.
        assertEquals(
            SinServidor.PEDIR_DIRECCION,
            queHacerSinServidor(algoPintado = false, baseGuardada = "")
        )
    }

    @Test
    fun `pulsar OK mientras busca abre el formulario de direccion`() {
        // La puerta de entrada manual: alguien con el mando delante de una
        // caja que no encuentra el servidor. Un escaparate desatendido no
        // pulsa teclas, asi que esto no puede dispararse solo.
        assertTrue(esPeticionDeDireccion(KeyEvent.KEYCODE_DPAD_CENTER, algoPintado = false))
        assertTrue(esPeticionDeDireccion(KeyEvent.KEYCODE_ENTER, algoPintado = false))
    }

    @Test
    fun `con el escaparate en marcha la tecla OK no abre nada`() {
        // Si ya se esta reproduciendo, OK es del reproductor: abrir aqui el
        // formulario seria tirar el escaparate por un roce del mando.
        assertFalse(esPeticionDeDireccion(KeyEvent.KEYCODE_DPAD_CENTER, algoPintado = true))
    }

    @Test
    fun `otras teclas del mando no abren el formulario`() {
        assertFalse(esPeticionDeDireccion(KeyEvent.KEYCODE_DPAD_DOWN, algoPintado = false))
        assertFalse(esPeticionDeDireccion(KeyEvent.KEYCODE_VOLUME_UP, algoPintado = false))
        assertFalse(esPeticionDeDireccion(KeyEvent.KEYCODE_BACK, algoPintado = false))
    }

    @Test
    fun `sin nada en pantalla se reintenta pronto`() {
        // Arrancando tras un corte de luz no hay nada que perder y todo que
        // ganar: cuanto antes se enganche al PC, menos rato pasa el
        // escaparate en gris. Es la cadencia que tenia la pantalla de
        // ajustes, que es la que esto sustituye.
        assertEquals(15_000L, esperaSinServidorMs(algoPintado = false))
    }

    @Test
    fun `con el escaparate en marcha se reintenta sin prisa`() {
        // Aqui la tienda ya esta servida desde la cache: barrer la subred
        // cada quince segundos serian 508 peticiones por minuto a la red del
        // local sin ninguna urgencia detras.
        assertEquals(60_000L, esperaSinServidorMs(algoPintado = true))
    }
}
