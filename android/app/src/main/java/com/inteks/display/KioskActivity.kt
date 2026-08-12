package com.inteks.display

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView

const val VIGILANCIA_MS = 60_000L
const val FALLOS_ANTES_DE_REBARRER = 3

class KioskActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var aviso: TextView
    private lateinit var ajustes: SettingsStore
    private val hilo = Handler(Looper.getMainLooper())
    private var intentos = 0
    private var algoPintado = false
    private var fallosSeguidos = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        ajustes = SettingsStore(this)

        aviso = TextView(this).apply {
            text = getString(R.string.buscando)
            setBackgroundColor(0xFF07182B.toInt())
            setTextColor(0xFF7A8CA3.toInt())
            textSize = 18f
            gravity = Gravity.CENTER
        }
        web = WebView(this)
        configurarWebView()
        setContentView(aviso)

        arrancar()
        hilo.postDelayed(vigilante, VIGILANCIA_MS)
    }

    private fun configurarWebView() {
        web.settings.apply {
            javaScriptEnabled = true
            // Sin esto la pantalla pierde su identidad en cada reinicio:
            // el bloque de identidad de index.html usa localStorage.
            domStorageEnabled = true
            // Sin esto los videos se quedan en el primer fotograma esperando
            // un clic que nadie va a dar.
            mediaPlaybackRequiresUserGesture = false
        }
        web.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                algoPintado = true
                intentos = 0
                if (web.parent == null) setContentView(web)
                aplicarPantallaCompleta()
                url?.let { u ->
                    extraerNombrePantalla(u)?.let { ajustes.nombrePantalla = it }
                }
            }

            override fun onReceivedError(
                view: WebView?, req: WebResourceRequest?, err: WebResourceError?
            ) {
                // Si YA hay algo pintado no se toca nada: el player sigue
                // reproduciendo de su cache y taparlo empeoraria el producto.
                if (algoPintado) return
                reintentar()
            }
        }
    }

    /**
     * Pantalla completa inmersiva.
     *
     * Usa `systemUiVisibility`, que el compilador marca como obsoleto, y es a
     * proposito: su reemplazo, `WindowInsetsController`, es de API 30, y la
     * caja de la tienda es API 25. Cambiarlo por lo "moderno" dejaria las
     * barras del sistema encima del escaparate.
     */
    @Suppress("DEPRECATION")
    private fun aplicarPantallaCompleta() {
        web.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_FULLSCREEN
                or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )
    }

    private fun arrancar() {
        val base = ajustes.base
        if (base != null) { cargar(base); return }
        buscarYCargar()
    }

    private fun buscarYCargar() {
        Thread {
            val red = redLocalDe(this)
            val encontrada = if (red == null) null else buscarServidor(red, SondeadorHttp())
            hilo.post {
                if (encontrada != null) {
                    ajustes.base = encontrada
                    cargar(encontrada)
                } else {
                    startActivity(Intent(this, SetupActivity::class.java))
                    finish()
                }
            }
        }.start()
    }

    private fun cargar(base: String) {
        web.loadUrl(urlDeArranque(base, ajustes.nombrePantalla))
    }

    private fun reintentar() {
        val espera = esperaMs(intentos)
        intentos++
        // Cada 5 fallos seguidos se vuelve a barrer: puede que el PC haya
        // cambiado de IP.
        if (intentos % 5 == 0) { ajustes.base = null; buscarYCargar(); return }
        hilo.postDelayed({ ajustes.base?.let { cargar(it) } ?: buscarYCargar() }, espera)
    }

    /**
     * Pregunta por /api/info cada minuto.
     *
     * Hace falta ademas de los reintentos: si el servidor se muda MIENTRAS el
     * player va bien desde su cache, no hay ningun error de carga que dispare
     * el rebarrido, y la pantalla se quedaria con contenido viejo para siempre.
     */
    private val vigilante = object : Runnable {
        override fun run() {
            val base = ajustes.base
            if (base == null) { hilo.postDelayed(this, VIGILANCIA_MS); return }
            Thread {
                val vivo = esRespuestaDeInTeks(
                    SondeadorHttp().pedir("$base/api/info", TIMEOUT_SONDA_MS))
                hilo.post {
                    if (vivo) {
                        fallosSeguidos = 0
                    } else if (++fallosSeguidos >= FALLOS_ANTES_DE_REBARRER) {
                        fallosSeguidos = 0
                        ajustes.base = null
                        buscarYCargar()
                    }
                    hilo.postDelayed(this, VIGILANCIA_MS)
                }
            }.start()
        }
    }

    override fun onResume() {
        super.onResume()
        aplicarPantallaCompleta()
    }

    override fun onDestroy() {
        hilo.removeCallbacksAndMessages(null)
        super.onDestroy()
    }
}
