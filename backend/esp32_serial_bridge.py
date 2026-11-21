import serial
import json
import time
import requests

SERIAL_PORT = "COM3"  # Update to your ESP32 COM port
BAUD_RATE = 115200
BACKEND_URL = "http://localhost:8000"

ALL_SLOTS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

def main():
    print(f"Connecting to ESP32 on {SERIAL_PORT}...")
    esp32 = serial.Serial(port=SERIAL_PORT, baudrate=BAUD_RATE, timeout=1)
    time.sleep(2)
    print("Connected! Listening for 8-Bay IR & PIR sensor updates...")

    prev_slots = {s: False for s in ALL_SLOTS}
    prev_pir = False

    while True:
        if esp32.in_waiting > 0:
            try:
                line = esp32.readline().decode("utf-8").strip()
                data = json.loads(line)

                for slot_id in ALL_SLOTS:
                    if slot_id in data:
                        occupied = bool(data[slot_id])
                        if occupied != prev_slots[slot_id]:
                            prev_slots[slot_id] = occupied
                            requests.post(f"{BACKEND_URL}/api/sensors/slot-update", json={
                                "slot_id": slot_id,
                                "ir_occupied": occupied
                            })
                            print(f"Updated {slot_id} -> Occupied: {occupied}")

                if "pir" in data:
                    pir_triggered = bool(data["pir"])
                    if pir_triggered and not prev_pir:
                        requests.post(f"{BACKEND_URL}/api/security/loitering", json={
                            "slot_id": "S1",
                            "human_loitering": True
                        })
                        print("PIR Alert Sent!")
                    prev_pir = pir_triggered

            except Exception:
                pass

if __name__ == "__main__":
    main()
