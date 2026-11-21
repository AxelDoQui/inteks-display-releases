package com.inteks.visor

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

/** Dirección del script de Google que sirve la página del visor (la misma que usa la extensión). */
const val URL_SCRIPT =
    "https://script.google.com/macros/s/AKfycbymyc-O56yBNPl7pzvt6bK0Wvz_uUlJ3pVVKVGj_YX3L84FGL2Tga62qxlybV3elHFp/exec"

/**
 * Dos capas: debajo, la publicidad de InTeks Display; encima, el visor del cliente.
 * El visor solo se ve mientras llega imagen Y el mostrador lo tiene activado; si no, se ve la publicidad.
 *
 * Los ajustes (clave de enlace y dirección de InTeks Display) se abren tocando 5 veces
 * la esquina superior izquierda.
 */
class MainActivity : Activity() {

    private val hilo = Handler(Looper.getMainLooper())
    private lateinit var publicidad: WebView
    private lateinit var visor: WebView
    private var tocadas = emptyList<Long>()

    private val prefs get() = getSharedPreferences("visor", Context.MODE_PRIVATE)
    private var clave: String
        get() = prefs.getString("clave", "") ?: ""
        set(v) { prefs.edit().putString("clave", v).apply() }
    private var direccionPublicidad: String
        get() = prefs.getString("publicidad", "") ?: ""
        set(v) { prefs.edit().putString("publicidad", v).apply() }

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
        )
        val raiz = FrameLayout(this).apply { setBackgroundColor(0xFF000000.toInt()) }

        publicidad = crearWeb()
        visor = crearWeb().apply {
            visibility = View.INVISIBLE
            addJavascriptInterface(object {
                @JavascriptInterface
                fun estado(mostrar: Boolean) {
                    hilo.post { ponerVisor(mostrar) }
                }
            }, "VisorApp")
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(v: WebView?, r: WebResourceRequest?, e: WebResourceError?) {
                    if (r?.isForMainFrame == true) {
                        ponerVisor(false)
                        hilo.postDelayed({ cargarVisor() }, 5_000)
                    }
                }
            }
        }
        raiz.addView(publicidad, FrameLayout.LayoutParams(-1, -1))
        raiz.addView(visor, FrameLayout.LayoutParams(-1, -1))

        // Esquina invisible para abrir los ajustes (5 toques seguidos).
        val esquina = View(this)
        val lado = (90 * resources.displayMetrics.density).toInt()
        esquina.setOnClickListener {
            val ahora = System.currentTimeMillis()
            tocadas = (tocadas + ahora).filter { ahora - it < 3_000 }
            if (tocadas.size >= 5) { tocadas = emptyList(); pedirAjustes() }
        }
        raiz.addView(esquina, FrameLayout.LayoutParams(lado, lado))
        setContentView(raiz)
        pantallaCompleta()

        if (clave.isEmpty()) pedirAjustes() else arrancar()
    }

    private fun crearWeb(): WebView = WebView(this).apply {
        setBackgroundColor(0xFF000000.toInt())
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.mediaPlaybackRequiresUserGesture = false
        webViewClient = WebViewClient()
    }

    private fun arrancar() {
        cargarVisor()
        if (direccionPublicidad.isNotEmpty()) publicidad.loadUrl(direccionPublicidad)
        else publicidad.loadData("<body style='background:#000'></body>", "text/html", "utf-8")
    }

    private fun cargarVisor() {
        if (clave.isNotEmpty()) visor.loadUrl("$URL_SCRIPT?cod=$clave")
    }

    private fun ponerVisor(mostrar: Boolean) {
        visor.visibility = if (mostrar) View.VISIBLE else View.INVISIBLE
        if (mostrar) publicidad.onPause() else publicidad.onResume()
    }

    private fun pedirAjustes() {
        val c = EditText(this).apply { hint = "Clave de enlace (la que muestra la extensión)"; setText(clave) }
        val p = EditText(this).apply {
            hint = "Dirección de InTeks Display (opcional)"
            setText(direccionPublicidad)
        }
        val caja = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 24, 48, 0)
            addView(TextView(context).apply { text = "Clave de enlace" })
            addView(c)
            addView(TextView(context).apply { text = "\nPublicidad: dirección del player de InTeks Display, por ejemplo http://192.168.0.63/player.html?screen=Visor" })
            addView(p)
        }
        AlertDialog.Builder(this)
            .setTitle("Visor de cliente")
            .setView(caja)
            .setCancelable(clave.isNotEmpty())
            .setPositiveButton("Guardar") { _, _ ->
                clave = c.text.toString().trim().lowercase()
                direccionPublicidad = p.text.toString().trim()
                arrancar()
                pantallaCompleta()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    @Suppress("DEPRECATION")
    private fun pantallaCompleta() {
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) pantallaCompleta()
    }

    override fun onDestroy() {
        hilo.removeCallbacksAndMessages(null)
        visor.destroy(); publicidad.destroy()
        super.onDestroy()
    }
}
