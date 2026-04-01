package com.btkeyboard.tv

import android.os.Bundle
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.ServerSocket

class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var ipText: TextView
    private lateinit var inputField: EditText
    private var serverRunning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildLayout()
        startServer()
    }

    private fun buildLayout() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xFF1A1A2E.toInt())
            setPadding(80, 60, 80, 60)
        }

        root.addView(TextView(this).apply {
            text = "⌨  BT Keyboard — TV Receiver"
            textSize = 36f; setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 0, 0, 16)
        })

        root.addView(TextView(this).apply {
            text = "Open BT Keyboard on your phone and connect to this IP:"
            textSize = 18f; setTextColor(0xFF888888.toInt())
            setPadding(0, 0, 0, 16)
        })

        ipText = TextView(this).apply {
            text = "Finding IP..."
            textSize = 32f; setTextColor(0xFF00FF88.toInt())
            setPadding(0, 0, 0, 8)
        }
        root.addView(ipText)

        root.addView(TextView(this).apply {
            text = "Port: 9876"
            textSize = 20f; setTextColor(0xFF00FF88.toInt())
            setPadding(0, 0, 0, 32)
        })

        statusText = TextView(this).apply {
            text = "Waiting for connection..."
            textSize = 22f; setTextColor(0xFFFFCC00.toInt())
            setPadding(0, 0, 0, 32)
        }
        root.addView(statusText)

        root.addView(TextView(this).apply {
            text = "Received text:"
            textSize = 14f; setTextColor(0xFF666666.toInt())
            setPadding(0, 0, 0, 8)
        })

        inputField = EditText(this).apply {
            setTextColor(0xFFFFFFFF.toInt()); textSize = 28f
            setBackgroundColor(0xFF22223A.toInt())
            setPadding(24, 24, 24, 24)
            isFocusable = true; minLines = 4
        }
        root.addView(inputField)

        setContentView(root)

        Thread {
            val ip = getLocalIp()
            runOnUiThread { ipText.text = "IP: $ip" }
        }.start()
    }

    private fun startServer() {
        serverRunning = true
        Thread {
            try {
                val server = ServerSocket(9876)
                runOnUiThread { statusText.text = "Waiting for connection..." }

                while (serverRunning) {
                    val client = server.accept()
                    runOnUiThread { statusText.text = "✅ Phone connected!" }

                    val reader = BufferedReader(InputStreamReader(client.getInputStream(), Charsets.UTF_8))
                    var line: String?

                    while (serverRunning) {
                        line = reader.readLine() ?: break
                        try {
                            val json = JSONObject(line)
                            val type = json.optString("type")
                            val value = json.optString("value")

                            runOnUiThread {
                                when (type) {
                                    "unicode", "key" -> {
                                        val pos = inputField.selectionStart.coerceAtLeast(0)
                                        inputField.text.insert(pos, value)
                                    }
                                    "special" -> {
                                        when (value) {
                                            "backspace" -> {
                                                val pos = inputField.selectionStart
                                                if (pos > 0) inputField.text.delete(pos - 1, pos)
                                            }
                                            "enter" -> inputField.text.insert(inputField.selectionStart.coerceAtLeast(0), "\n")
                                            "space" -> inputField.text.insert(inputField.selectionStart.coerceAtLeast(0), " ")
                                        }
                                    }
                                }
                            }
                        } catch (_: Exception) {}
                    }

                    client.close()
                    runOnUiThread { statusText.text = "Disconnected. Waiting..." }
                }
            } catch (e: Exception) {
                runOnUiThread { statusText.text = "Server error: ${e.message}" }
            }
        }.start()
    }

    private fun getLocalIp(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (!addr.isLoopbackAddress && addr is InetAddress && addr.hostAddress.contains('.')) {
                        return addr.hostAddress
                    }
                }
            }
        } catch (_: Exception) {}
        return "Unknown"
    }

    override fun onDestroy() {
        super.onDestroy()
        serverRunning = false
    }
}
