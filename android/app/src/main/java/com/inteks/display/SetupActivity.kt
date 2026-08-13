package com.inteks.display

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText

class SetupActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)

        val campo = findViewById<EditText>(R.id.direccion)
        findViewById<Button>(R.id.conectar).setOnClickListener {
            val escrito = campo.text.toString().trim().trimEnd('/')
            if (escrito.length > "http://".length) {
                SettingsStore(this).base = escrito
                startActivity(Intent(this, KioskActivity::class.java))
                finish()
            }
        }
        campo.requestFocus()
    }
}
