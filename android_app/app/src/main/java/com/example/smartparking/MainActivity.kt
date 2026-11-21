package com.example.smartparking

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException

data class ParkingSlot(
    val id: String,
    val status: String,
    val reservedBy: String?,
    val actualPlate: String?,
    val locked: Boolean
)

class MainActivity : ComponentActivity() {
    private val serverIp = "192.168.1.100:8000"
    private val client = OkHttpClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                SmartParkingScreen()
            }
        }
    }

    @Composable
    fun SmartParkingScreen() {
        var slots by remember { mutableStateOf<Map<String, ParkingSlot>>(emptyMap()) }
        var detectedPlate by remember { mutableStateOf("") }
        var detectedType by remember { mutableStateOf("Car") }
        var confirmedPlate by remember { mutableStateOf<String?>(null) }
        var selectedSlot by remember { mutableStateOf<String?>(null) }
        var isUnlocked by remember { mutableStateOf(false) }
        var alertBanner by remember { mutableStateOf<String?>(null) }
        var billSummary by remember { mutableStateOf<String?>(null) }

        LaunchedEffect(Unit) {
            val request = Request.Builder().url("ws://$serverIp/ws").build()
            client.newWebSocket(request, object : WebSocketListener() {
                override fun onMessage(webSocket: WebSocket, text: String) {
                    val json = JSONObject(text)
                    when (json.optString("type")) {
                        "STATE_UPDATE" -> {
                            val slotsObj = json.optJSONObject("slots")
                            if (slotsObj != null) {
                                val updated = mutableMapOf<String, ParkingSlot>()
                                for (key in slotsObj.keys()) {
                                    val s = slotsObj.getJSONObject(key)
                                    updated[key] = ParkingSlot(
                                        id = s.getString("id"),
                                        status = s.getString("status"),
                                        reservedBy = s.optString("reserved_by").takeIf { it != "null" },
                                        actualPlate = s.optString("actual_plate").takeIf { it != "null" },
                                        locked = s.optBoolean("locked", false)
                                    )
                                }
                                slots = updated
                            }
                            val scan = json.optJSONObject("latest_gate_scan")
                            if (scan != null && !scan.optBoolean("confirmed", false)) {
                                detectedPlate = scan.getString("plate")
                                detectedType = scan.getString("vehicle_type")
                            }
                        }
                        "ALERT" -> {
                            val alert = json.getJSONObject("alert")
                            alertBanner = "${alert.getString("title")}: ${alert.getString("message")}"
                        }
                        "BILL_GENERATED" -> {
                            val v = json.getJSONObject("vehicle")
                            if (v.getString("plate") == confirmedPlate) {
                                billSummary = "Vehicle: ${v.getString("plate")}\n" +
                                        "Duration: ${v.getInt("duration_sec")} secs\n" +
                                        "Total Bill: LKR ${v.getDouble("bill")}"
                            }
                        }
                    }
                }
            })
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF070B14))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "SMART PARK AI (8 BAYS)",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF38BDF8)
            )

            alertBanner?.let { msg ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF7F1D1D)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = "🚨 $msg", color = Color.White, fontSize = 12.sp, modifier = Modifier.weight(1f))
                        TextButton(onClick = { alertBanner = null }) {
                            Text("OK", color = Color.Yellow)
                        }
                    }
                }
            }

            billSummary?.let { bill ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF064E3B)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text("PARKING RECEIPT", fontWeight = FontWeight.Bold, color = Color(0xFF6EE7B7))
                        Text(bill, color = Color.White, fontSize = 13.sp)
                    }
                }
            }

            if (confirmedPlate == null) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Entry Gate Camera Detection", color = Color.Gray, fontSize = 12.sp)
                        Spacer(modifier = Modifier.height(6.dp))
                        OutlinedTextField(
                            value = detectedPlate,
                            onValueChange = { detectedPlate = it },
                            label = { Text("Vehicle Plate Number") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Text("Vehicle Type: $detectedType", color = Color(0xFF38BDF8), modifier = Modifier.padding(top = 6.dp))
                        Spacer(modifier = Modifier.height(10.dp))
                        Button(
                            onClick = {
                                if (detectedPlate.isNotBlank()) {
                                    val body = JSONObject()
                                        .put("plate", detectedPlate)
                                        .put("vehicle_type", detectedType)
                                    postJson("/api/gate/confirm", body)
                                    confirmedPlate = detectedPlate.uppercase()
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
                        ) {
                            Text("Confirm Vehicle & Open Gate", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            } else {
                Text("Select Bay (${confirmedPlate}):", color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)

                // Row 1: S1 - S4
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                    listOf("S1", "S2", "S3", "S4").forEach { id ->
                        SlotButton(id, slots[id], selectedSlot == id) {
                            postJson("/api/slots/select", JSONObject().put("plate", confirmedPlate).put("slot_id", id))
                            selectedSlot = id
                        }
                    }
                }
                // Row 2: S5 - S8
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                    listOf("S5", "S6", "S7", "S8").forEach { id ->
                        SlotButton(id, slots[id], selectedSlot == id) {
                            postJson("/api/slots/select", JSONObject().put("plate", confirmedPlate).put("slot_id", id))
                            selectedSlot = id
                        }
                    }
                }

                // Dual-Zone Map Canvas
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF111827)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(230.dp)
                ) {
                    Canvas(modifier = Modifier.fillMaxSize().padding(12.dp)) {
                        val centerX = size.width / 2f
                        drawLine(color = Color.Gray, start = Offset(centerX, 10f), end = Offset(centerX, size.height - 10f), strokeWidth = 6f)

                        val allIds = listOf("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8")
                        allIds.forEachIndexed { idx, id ->
                            val isLeft = idx < 4
                            val row = idx % 4
                            val yPos = 15f + (row * 125f)
                            val xPos = if (isLeft) 20f else size.width - 200f

                            val slot = slots[id]
                            val isMine = selectedSlot == id
                            val bayColor = when {
                                isMine -> Color(0xFF3B82F6)
                                slot?.status == "occupied" -> Color(0xFFEF4444)
                                slot?.status == "reserved" -> Color(0xFFF59E0B)
                                else -> Color(0xFF10B981)
                            }
                            drawRect(color = bayColor, topLeft = Offset(xPos, yPos), size = Size(180f, 90f))

                            if (isMine) {
                                val navColor = if (isUnlocked) Color(0xFFA855F7) else Color(0xFF22D3EE)
                                val startY = if (isUnlocked) size.height - 10f else 10f
                                val targetX = if (isLeft) xPos + 185f else xPos - 5f
                                drawLine(color = navColor, start = Offset(centerX, startY), end = Offset(centerX, yPos + 45f), strokeWidth = 10f)
                                drawLine(color = navColor, start = Offset(centerX, yPos + 45f), end = Offset(targetX, yPos + 45f), strokeWidth = 10f)
                            }
                        }
                    }
                }

                if (selectedSlot != null) {
                    Button(
                        onClick = {
                            postJson("/api/vehicle/unlock", JSONObject().put("plate", confirmedPlate))
                            isUnlocked = true
                        },
                        enabled = !isUnlocked,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF7C3AED))
                    ) {
                        Text(
                            text = if (isUnlocked) "UNLOCKED - FOLLOW PURPLE PATH" else "🔓 UNLOCK VEHICLE TO RETRIEVE",
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }

    @Composable
    fun RowScope.SlotButton(id: String, slot: ParkingSlot?, isMine: Boolean, onClick: () -> Unit) {
        val isAvailable = slot?.status == "available"
        Button(
            onClick = onClick,
            enabled = isAvailable,
            modifier = Modifier.weight(1f),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = when {
                    isMine -> Color(0xFF2563EB)
                    isAvailable -> Color(0xFF059669)
                    else -> Color(0xFFDC2626)
                }
            )
        ) {
            Text(id, fontWeight = FontWeight.Bold, fontSize = 12.sp)
        }
    }

    private fun postJson(endpoint: String, jsonBody: JSONObject) {
        val mediaType = "application/json; charset=utf-8".toMediaType()
        val body = jsonBody.toString().toRequestBody(mediaType)
        val request = Request.Builder().url("http://$serverIp$endpoint").post(body).build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) { e.printStackTrace() }
            override fun onResponse(call: Call, response: Response) { response.close() }
        })
    }
}
