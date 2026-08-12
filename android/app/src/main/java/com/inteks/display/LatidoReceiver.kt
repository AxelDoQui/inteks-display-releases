package com.inteks.display

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock

const val LATIDO_MS = 2 * 60 * 1000L

/**
 * Relanza el reproductor si no está delante.
 *
 * Vive en AlarmManager, que es del sistema, no de la app: con 990 MB de RAM el
 * proceso de render del WebView puede morir, y en API 25 no existe
 * `onRenderProcessGone` (llegó en la 26), así que se cae la app entera y no
 * queda nadie dentro para levantarla. Un servicio en segundo plano moriría con
 * ella; la alarma no.
 */
class LatidoReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        context.startActivity(Intent(context, KioskActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            // singleTask + esta bandera: si ya esta delante, no hace nada
            // visible; si no esta, la trae.
            addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        })
        programarLatido(context)
    }
}

fun programarLatido(context: Context) {
    val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
    val pi = PendingIntent.getBroadcast(
        context, 0, Intent(context, LatidoReceiver::class.java),
        PendingIntent.FLAG_UPDATE_CURRENT
    )
    am.setInexactRepeating(
        AlarmManager.ELAPSED_REALTIME,
        SystemClock.elapsedRealtime() + LATIDO_MS,
        LATIDO_MS,
        pi
    )
}
