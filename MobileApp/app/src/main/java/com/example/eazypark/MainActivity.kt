package com.example.eazypark

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import kotlinx.coroutines.*
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this)
        setContentView(webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            useWideViewPort = true
            loadWithOverviewMode = true
        }
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()

        discoverServerAndLoad()
    }

    private fun discoverServerAndLoad() {
        scope.launch {
            Toast.makeText(this@MainActivity, "Searching EAZYPARK Server...", Toast.LENGTH_SHORT).show()
            val serverUrl = withContext(Dispatchers.IO) {
                findServerViaUdp()
            }
            if (serverUrl != null) {
                Toast.makeText(this@MainActivity, "Connected: $serverUrl", Toast.LENGTH_SHORT).show()
                webView.loadUrl(serverUrl)
            } else {
                Toast.makeText(this@MainActivity, "Server not found. Check Wi-Fi!", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun findServerViaUdp(): String? {
        return try {
            val socket = DatagramSocket()
            socket.broadcast = true
            socket.soTimeout = 4000

            val sendData = "DISCOVER_SMART_PARK".toByteArray()
            val sendPacket = DatagramPacket(
                sendData,
                sendData.size,
                InetAddress.getByName("255.255.255.255"),
                8888
            )
            socket.send(sendPacket)

            val recvBuf = ByteArray(1024)
            val recvPacket = DatagramPacket(recvBuf, recvBuf.size)
            socket.receive(recvPacket)

            val response = String(recvPacket.data, 0, recvPacket.length).trim()
            val serverIp = recvPacket.address.hostAddress
            socket.close()

            if (response.startsWith("SMART_PARK_HERE")) {
                "http://$serverIp:8000"
            } else null
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }
}