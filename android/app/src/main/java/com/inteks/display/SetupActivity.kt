package com.inteks.display

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Button
import android.widget.EditText

/** Cada cuánto se vuelve a barrer la red desde esta pantalla. */
const val REBARRIDO_SETUP_MS = 15_000L

/**
 * Escribir la dirección a mano. Es el respaldo, no el camino principal.
 *
 * **Sigue barriendo la red de fondo mientras está abierta.** Sin eso, la app
 * tenía una forma de rendirse para siempre, y mordía justo en el peor momento:
 * al volver la luz, la caja arranca en unos dos minutos y el PC de la tienda
 * tarda más —Windows y luego el servidor—, así que el barrido inicial no
 * encontraba nada y el escaparate se quedaba con un formulario que nadie iba a
 * rellenar. Ahora, en cuanto el servidor aparece, esta pantalla continúa sola.
 */
class SetupActivity : Activity() {

    private val hilo = Handler(Looper.getMainLooper())
    private lateinit var ajustes: SettingsStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)
        ajustes = SettingsStore(this)

        val campo = findViewById<EditText>(R.id.direccion)
        findViewById<Button>(R.id.conectar).setOnClickListener {
            val escrito = campo.text.toString().trim().trimEnd('/')
            if (escrito.length > "http://".length) {
                ajustes.base = escrito
                irAlPlayer()
            }
        }
        campo.requestFocus()
    }

    override fun onResume() {
        super.onResume()
        hilo.postDelayed(barrer, REBARRIDO_SETUP_MS)
    }

    override fun onPause() {
        super.onPause()
        hilo.removeCallbacksAndMessages(null)
    }

    private val barrer = object : Runnable {
        override fun run() {
            Thread {
                val red = redLocalDe(this@SetupActivity)
                val encontrada = if (red == null) null
                                 else buscarServidor(red, SondeadorHttp())
                Log.i(TAG, "barrido desde ajustes: $encontrada")
                hilo.post {
                    if (isFinishing) return@post
                    if (encontrada != null) {
                        ajustes.base = encontrada
                        irAlPlayer()
                    } else {
                        hilo.postDelayed(this, REBARRIDO_SETUP_MS)
                    }
                }
            }.start()
        }
    }

    private fun irAlPlayer() {
        hilo.removeCallbacksAndMessages(null)
        startActivity(Intent(this, KioskActivity::class.java))
        finish()
    }

    override fun onDestroy() {
        hilo.removeCallbacksAndMessages(null)
        super.onDestroy()
    }
}
