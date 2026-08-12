package com.inteks.display

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Al encender la caja: lanzar el reproductor y volver a poner la alarma, que
 * las alarmas no sobreviven a un reinicio.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_BOOT_COMPLETED) return
        context.startActivity(Intent(context, KioskActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        })
        programarLatido(context)
    }
}
