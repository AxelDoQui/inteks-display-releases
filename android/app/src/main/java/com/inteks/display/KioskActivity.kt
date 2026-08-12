package com.inteks.display

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.util.Log
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
const val TAG = "InTeksKiosco"

class KioskActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var aviso: TextView
    private lateinit var ajustes: SettingsStore
    private val hilo = Handler(Looper.getMainLooper())
    private var intentos = 0
    private var algoPintado = false
    private var errorEnEstaCarga = false
    private var fallosSeguidos = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        despertarPantalla()
        ajustes = SettingsStore(this)
        programarLatido(this)

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
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                Log.i(TAG, "onPageStarted url=$url")
                errorEnEstaCarga = false
            }

            /**
             * OJO: esto tambien salta con la pagina de error del WebView.
             * Llegar aqui NO significa que la carga fuera bien, por eso manda
             * `errorEnEstaCarga` y no el hecho de que se haya terminado.
             */
            override fun onPageFinished(view: WebView?, url: String?) {
                Log.i(TAG, "onPageFinished url=$url progreso=${web.progress}" +
                    " error=$errorEnEstaCarga titulo=${web.title}")
                if (errorEnEstaCarga) { reintentar(); return }
                algoPintado = true
                intentos = 0
                if (web.parent == null) setContentView(web)
                aplicarPantallaCompleta()
                url?.let { u ->
                    extraerNombrePantalla(u)?.let { ajustes.nombrePantalla = it }
                }
            }

            /**
             * Solo importa que falle el MARCO PRINCIPAL.
             *
             * Si lo que falla es un subrecurso -una imagen, el SSE- el player
             * sigue reproduciendo de su cache y no hay que tocar nada: recargar
             * ahi seria tirar a la basura lo unico que mantiene vivo el
             * escaparate cuando el servidor esta caido.
             */
            override fun onReceivedError(
                view: WebView?, req: WebResourceRequest?, err: WebResourceError?
            ) {
                Log.i(TAG, "onReceivedError principal=${req?.isForMainFrame} url=${req?.url}")
                if (req?.isForMainFrame != true) return
                errorEnEstaCarga = true
            }
        }
    }

    /**
     * Enciende la pantalla y la mantiene encendida.
     *
     * KEEP_SCREEN_ON solo IMPIDE que se duerma; no despierta una pantalla que
     * ya esta apagada. Y ese es justo el caso de una tienda tras un corte de
     * luz: la caja tarda cerca de dos minutos en llegar a BOOT_COMPLETED
     * -medido: 118 s en la MXQ-, durante los cuales nada sujeta la pantalla,
     * asi que se duerme. La app arrancaba detras de un display apagado y el
     * escaparate se quedaba negro con todo funcionando perfectamente por
     * dentro: la peor clase de fallo, porque no parece un fallo del programa.
     *
     * TURN_SCREEN_ON pide el encendido al mostrar la ventana, y el wake lock
     * con ACQUIRE_CAUSES_WAKEUP lo fuerza cuando el aparato ya estaba dormido,
     * que TURN_SCREEN_ON solo no siempre consigue en API 25. Se suelta
     * enseguida: a partir de ahi manda KEEP_SCREEN_ON.
     */
    @Suppress("DEPRECATION")
    private fun despertarPantalla() {
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                or WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                or WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD
        )
        try {
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            val wl = pm.newWakeLock(
                PowerManager.FULL_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "InTeks:arranque"
            )
            wl.acquire(3_000L)
        } catch (e: Exception) {
            Log.i(TAG, "no se pudo forzar el encendido: $e")
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
        Log.i(TAG, "arrancar baseGuardada=$base pantalla=${ajustes.nombrePantalla}")
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
        val url = urlDeArranque(base, ajustes.nombrePantalla)
        Log.i(TAG, "cargar url=$url")
        web.loadUrl(url)
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
