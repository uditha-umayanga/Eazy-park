# Smart IoT Vehicle Parking System

## Folder Structure
- `backend/server.py` - Python FastAPI Central Server & WebSocket Hub
- `backend/index.html` - Responsive Driver & Admin Simulator Web Application
- `backend/esp32_serial_bridge.py` - USB Serial bridge connecting ESP32 to the Backend
- `esp32_firmware/smart_parking_esp32.ino` - Arduino/ESP32 firmware for IR sensors, PIR sensor & Servo barriers
- `android_app/` - Native Kotlin Jetpack Compose Android Application

## Quick Start (Backend & Web App)
1. Open terminal inside `backend/` folder:
   ```bash
   pip install -r requirements.txt
   python server.py
   ```
2. Open `http://localhost:8000` in your browser (or `http://<YOUR-LAPTOP-IP>:8000` from your phone).
3. Use the **Admin / Sensor Sim** tab to simulate Gate ALPR scans, IR bay sensors, Wrong Slot alerts, Security Loitering alerts, and Exit billing.

## Hardware Connection (ESP32)
1. Upload `esp32_firmware/smart_parking_esp32.ino` to your ESP32 board via Arduino IDE.
2. Update `SERIAL_PORT` in `backend/esp32_serial_bridge.py` (e.g., `COM3`) and run:
   ```bash
   python esp32_serial_bridge.py
   ```

## Android App Setup
1. Create a new **Empty Activity (Jetpack Compose)** project in Android Studio.
2. Add `implementation("com.squareup.okhttp3:okhttp:4.12.0")` to `app/build.gradle.kts`.
3. Replace `MainActivity.kt` and `AndroidManifest.xml` with the files in `android_app/`.
4. Update `serverIp` in `MainActivity.kt` with your laptop's Wi-Fi IP address.
