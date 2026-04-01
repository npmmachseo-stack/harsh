package com.btkeyboard.sender

import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.KeyEvent
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStream
import java.net.Socket

class MainActivity : AppCompatActivity() {

    private lateinit var vibrator: Vibrator
    private lateinit var statusText: TextView
    private lateinit var ipField: EditText
    private lateinit var connectBtn: Button
    private lateinit var inputField: EditText
    private lateinit var disconnectBtn: Button

    private var socket: Socket? = null
    private var outputStream: OutputStream? = null
    private var connected = false
    private var lastSentLength = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        vibrator = getSystemService(Vibrator::class.java)
        buildLayout()
    }

    private fun buildLayout() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xFF1A1A2E.toInt())
            setPadding(48, 64, 48, 48)
        }

        root.addView(TextView(this).apply {
            text = "⌨  BT Keyboard"
            textSize = 32f
            setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 0, 0, 8)
        })

        root.addView(TextView(this).apply {
            text = "Type on your phone → appears on PC/TV"
            textSize = 14f
            setTextColor(0xFF888888.toInt())
            setPadding(0, 0, 0, 32)
        })

        statusText = TextView(this).apply {
            text = "Enter your PC's IP address and tap Connect"
            textSize = 16f
            setTextColor(0xFF00FF88.toInt())
            setPadding(0, 0, 0, 24)
        }
        root.addView(statusText)

        root.addView(TextView(this).apply {
            text = "PC/TV IP Address:"
            textSize = 13f
            setTextColor(0xFF666666.toInt())
            setPadding(0, 0, 0, 8)
        })

        ipField = EditText(this).apply {
            hint = "192.168.1.100"
            setHintTextColor(0xFF444444.toInt())
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 20f
            setBackgroundColor(0xFF22223A.toInt())
            setPadding(24, 20, 24, 20)
            inputType = InputType.TYPE_CLASS_TEXT
            isSingleLine = true
        }
        root.addView(ipField)

        connectBtn = Button(this).apply {
            text = "Connect"
            textSize = 18f
            setTextColor(0xFFFFFFFF.toInt())
            setBackgroundColor(0xFF6A4ACA.toInt())
            setPadding(0, 20, 0, 20)
            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.setMargins(0, 24, 0, 0)
            layoutParams = lp
            setOnClickListener { doConnect() }
        }
        root.addView(connectBtn)

        disconnectBtn = Button(this).apply {
            text = "Disconnect"
            textSize = 16f
            setTextColor(0xFFFFFFFF.toInt())
            setBackgroundColor(0xFFCA4A4A.toInt())
            setPadding(0, 16, 0, 16)
            visibility = View.GONE
            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.setMargins(0, 12, 0, 0)
            layoutParams = lp
            setOnClickListener { doDisconnect() }
        }
        root.addView(disconnectBtn)

        root.addView(TextView(this).apply {
            text = "Type in any language below:"
            textSize = 13f
            setTextColor(0xFF666666.toInt())
            setPadding(0, 32, 0, 8)
        })

        inputField = EditText(this).apply {
            hint = "Start typing here..."
            setHintTextColor(0xFF444444.toInt())
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 22f
            setBackgroundColor(0xFF22223A.toInt())
            setPadding(24, 24, 24, 24)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            minLines = 4
            visibility = View.GONE

            addTextChangedListener(object : TextWatcher {
                private var internal = false
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
                override fun afterTextChanged(s: Editable?) {
                    if (internal) return
                    val text = s?.toString() ?: return
                    val len = text.length
                    if (len > lastSentLength) {
                        val newText = text.substring(lastSentLength)
                        var i = 0
                        while (i < newText.length) {
                            val cp = Character.codePointAt(newText, i)
                            val ch = String(Character.toChars(cp))
                            sendJson("unicode", ch)
                            i += Character.charCount(cp)
                        }
                    } else if (len < lastSentLength) {
                        val deleted = lastSentLength - len
                        for (j in 0 until deleted) {
                            sendJson("special", "backspace")
                        }
                    }
                    lastSentLength = len
                    if (len > 500) {
                        internal = true
                        s?.clear()
                        lastSentLength = 0
                        internal = false
                    }
                }
            })

            setOnKeyListener { _, keyCode, event ->
                if (event.action == KeyEvent.ACTION_DOWN) {
                    when (keyCode) {
                        KeyEvent.KEYCODE_ENTER -> { sendJson("special", "enter"); true }
                        KeyEvent.KEYCODE_DEL -> {
                            if (text.isEmpty()) { sendJson("special", "backspace"); true } else false
                        }
                        else -> false
                    }
                } else false
            }
        }
        root.addView(inputField)

        val quickRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            visibility = View.GONE
            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.setMargins(0, 12, 0, 0)
            layoutParams = lp
            tag = "quickRow"
        }
        for ((label, key) in listOf(
            "Tab" to "tab", "Esc" to "escape",
            "←" to "left", "→" to "right", "↑" to "up", "↓" to "down"
        )) {
            quickRow.addView(Button(this).apply {
                text = label; textSize = 13f
                setTextColor(0xFFE0E0E0.toInt())
                setBackgroundColor(0xFF2D2D44.toInt())
                isAllCaps = false
                layoutParams = LinearLayout.LayoutParams(0, 90, 1f).apply { setMargins(4, 0, 4, 0) }
                setOnClickListener {
                    vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
                    sendJson("special", key)
                }
            })
        }
        root.addView(quickRow)

        setContentView(root)
    }

    private fun doConnect() {
        val ip = ipField.text.toString().trim()
        if (ip.isEmpty()) {
            Toast.makeText(this, "Enter an IP address", Toast.LENGTH_SHORT).show()
            return
        }

        statusText.text = "Connecting to $ip..."
        connectBtn.isEnabled = false

        Thread {
            try {
                socket = Socket(ip, 9876)
                socket?.tcpNoDelay = true
                outputStream = socket?.getOutputStream()
                connected = true

                runOnUiThread {
                    statusText.text = "✅ Connected to $ip"
                    statusText.setTextColor(0xFF00FF88.toInt())
                    connectBtn.visibility = View.GONE
                    ipField.visibility = View.GONE
                    disconnectBtn.visibility = View.VISIBLE
                    inputField.visibility = View.VISIBLE
                    val quickRow = findViewWithTag<View>("quickRow") as? LinearLayout
                    quickRow?.visibility = View.VISIBLE
                    inputField.requestFocus()
                }
            } catch (e: Exception) {
                runOnUiThread {
                    statusText.text = "❌ Cannot connect to $ip"
                    statusText.setTextColor(0xFFFF4444.toInt())
                    connectBtn.isEnabled = true
                    Toast.makeText(this, "Connection failed.\nIs the PC receiver running?\nAre both on same WiFi?", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun doDisconnect() {
        connected = false
        try {
            outputStream?.close()
            socket?.close()
        } catch (_: Exception) {}
        socket = null
        outputStream = null
        lastSentLength = 0

        statusText.text = "Disconnected"
        statusText.setTextColor(0xFFFF8800.toInt())
        connectBtn.visibility = View.VISIBLE
        connectBtn.isEnabled = true
        ipField.visibility = View.VISIBLE
        disconnectBtn.visibility = View.GONE
        inputField.visibility = View.GONE
        inputField.text.clear()
        val quickRow = findViewWithTag<View>("quickRow") as? LinearLayout
        quickRow?.visibility = View.GONE
    }

    private fun sendJson(type: String, value: String, modifiers: List<String> = emptyList()) {
        if (!connected || outputStream == null) return
        val json = JSONObject().apply {
            put("type", type)
            put("value", value)
            if (modifiers.isNotEmpty()) put("modifiers", JSONArray(modifiers))
            put("timestamp", System.currentTimeMillis())
        }
        Thread {
            try {
                val msg = json.toString() + "\n"
                outputStream?.write(msg.toByteArray(Charsets.UTF_8))
                outputStream?.flush()
            } catch (e: Exception) {
                runOnUiThread { doDisconnect() }
            }
        }.start()
    }

    override fun onDestroy() {
        super.onDestroy()
        doDisconnect()
    }

    private fun <T : View> findViewWithTag(tag: String): T? {
        return window.decorView.findViewWithTag(tag)
    }
}
