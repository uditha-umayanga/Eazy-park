import time
import socket
import threading
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="EAZYPARK — Smart Parking & Security System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 10-Slot Parking Lot Layout (Zone A: S1-S5 Left, Zone B: S6-S10 Right)
slots_db: Dict[str, dict] = {}
for i in range(1, 11):
    slot_id = f"S{i}"
    side = "left" if i <= 5 else "right"
    row = (i - 1) % 5  # 0..4 (5 rows top to bottom)
    slots_db[slot_id] = {
        "id": slot_id,
        "side": side,
        "row": row,
        "status": "available",
        "reserved_by": None,
        "actual_plate": None,
        "locked": False
    }

active_vehicles: Dict[str, dict] = {}
latest_gate_scan: Optional[dict] = None
alerts_log: List[dict] = []

RATE_PER_MINUTE = 100.0  # LKR 100 per minute

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_state(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def get_state_payload(self):
        return {
            "type": "STATE_UPDATE",
            "slots": slots_db,
            "vehicles": active_vehicles,
            "latest_gate_scan": latest_gate_scan,
            "alerts": alerts_log[-15:]
        }

    async def send_state(self, websocket: WebSocket):
        await websocket.send_json(self.get_state_payload())

    async def broadcast_state(self):
        payload = self.get_state_payload()
        for conn in list(self.active_connections):
            try:
                await conn.send_json(payload)
            except Exception:
                self.disconnect(conn)

    async def broadcast_event(self, payload: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(payload)
            except Exception:
                self.disconnect(conn)

manager = ConnectionManager()

class GateScanEvent(BaseModel):
    plate: str
    vehicle_type: str = "Car"

class ConfirmVehicleRequest(BaseModel):
    plate: str
    vehicle_type: str = "Car"

class SelectSlotRequest(BaseModel):
    plate: str
    slot_id: str

class SlotSensorUpdate(BaseModel):
    slot_id: str
    ir_occupied: bool
    detected_plate: Optional[str] = None

class UnlockRequest(BaseModel):
    plate: str

class LoiteringAlertRequest(BaseModel):
    slot_id: str
    human_loitering: bool = True

def add_alert(level: str, title: str, message: str):
    alert = {
        "id": int(time.time() * 1000),
        "level": level,
        "title": title,
        "message": message,
        "time": datetime.now().strftime("%H:%M:%S")
    }
    alerts_log.append(alert)
    return alert

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/sw.js")
async def serve_service_worker():
    with open("sw.js", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="application/javascript")

@app.get("/logo.png")
async def serve_logo():
    return FileResponse("logo.png")

@app.get("/api/state")
async def get_state():
    return {
        "slots": slots_db,
        "vehicles": active_vehicles,
        "latest_gate_scan": latest_gate_scan,
        "alerts": alerts_log[-15:]
    }

@app.post("/api/gate/entry-scan")
async def gate_entry_scan(event: GateScanEvent):
    global latest_gate_scan
    plate = event.plate.upper().strip()

    if plate in active_vehicles and active_vehicles[plate]["status"] in ["UNLOCKED", "EXITING"]:
        return await gate_exit_scan(event)

    latest_gate_scan = {
        "plate": plate,
        "vehicle_type": event.vehicle_type,
        "timestamp": time.time(),
        "confirmed": False
    }
    await manager.broadcast_state()
    return {"status": "scanned", "data": latest_gate_scan}

@app.post("/api/gate/confirm")
async def confirm_vehicle(req: ConfirmVehicleRequest):
    global latest_gate_scan
    plate = req.plate.upper().strip()
    now = time.time()
    active_vehicles[plate] = {
        "plate": plate,
        "vehicle_type": req.vehicle_type,
        "entry_time": now,
        "entry_time_str": datetime.fromtimestamp(now).strftime("%H:%M:%S"),
        "slot_id": None,
        "status": "ENTERING",
        "locked": False
    }
    if latest_gate_scan and latest_gate_scan["plate"] == plate:
        latest_gate_scan["confirmed"] = True
    await manager.broadcast_state()
    return {"status": "confirmed", "vehicle": active_vehicles[plate]}

@app.post("/api/slots/select")
async def select_slot(req: SelectSlotRequest):
    plate = req.plate.upper().strip()
    slot_id = req.slot_id.upper().strip()

    if slot_id not in slots_db:
        return {"error": f"Invalid slot ID: {slot_id}"}

    # Enforce strict 1 slot per vehicle rule
    existing_slot = None
    for s_id, s in slots_db.items():
        if s["reserved_by"] == plate and s["status"] in ["reserved", "occupied"]:
            existing_slot = s_id
            break

    if existing_slot:
        return {"error": f"Vehicle {plate} already has slot {existing_slot} assigned. Only 1 slot is allowed per vehicle."}

    if slots_db[slot_id]["status"] != "available":
        return {"error": f"Slot {slot_id} is currently {slots_db[slot_id]['status']}"}

    slots_db[slot_id]["status"] = "reserved"
    slots_db[slot_id]["reserved_by"] = plate

    if plate in active_vehicles:
        active_vehicles[plate]["slot_id"] = slot_id
        active_vehicles[plate]["status"] = "NAVIGATING"

    await manager.broadcast_state()
    return {"status": "reserved", "slot": slots_db[slot_id]}

@app.post("/api/sensors/slot-update")
async def update_slot_sensor(update: SlotSensorUpdate):
    slot_id = update.slot_id.upper().strip()
    if slot_id not in slots_db:
        return {"error": "Invalid slot"}

    slot = slots_db[slot_id]

    if update.ir_occupied:
        detected = update.detected_plate.upper().strip() if update.detected_plate else None
        expected = slot["reserved_by"]

        slot["status"] = "occupied"
        slot["actual_plate"] = detected

        if expected and detected and detected != expected:
            alert = add_alert(
                "WARNING",
                f"Wrong Slot Parking at {slot_id}",
                f"Bay {slot_id} was reserved for {expected}, but {detected} parked here!"
            )
            await manager.broadcast_event({"type": "ALERT", "alert": alert})
        elif not expected and detected:
            alert = add_alert(
                "WARNING",
                f"Unreserved Parking at {slot_id}",
                f"Vehicle {detected} occupied {slot_id} without selecting it on the app."
            )
            await manager.broadcast_event({"type": "ALERT", "alert": alert})

        if detected and detected in active_vehicles:
            active_vehicles[detected]["slot_id"] = slot_id
            active_vehicles[detected]["status"] = "PARKED_LOCKED"
            active_vehicles[detected]["locked"] = True
            slot["locked"] = True
    else:
        prev_plate = slot["actual_plate"] or slot["reserved_by"]
        if slot["locked"] and prev_plate in active_vehicles and active_vehicles[prev_plate]["locked"]:
            alert = add_alert(
                "CRITICAL",
                f"THEFT ALERT — Unauthorized Exit from {slot_id}!",
                f"Vehicle {prev_plate} moved out of {slot_id} while SECURITY LOCK was active!"
            )
            await manager.broadcast_event({"type": "ALERT", "alert": alert})

        slot["status"] = "available"
        slot["reserved_by"] = None
        slot["actual_plate"] = None
        slot["locked"] = False

    await manager.broadcast_state()
    return {"status": "updated", "slot": slot}

@app.post("/api/vehicle/unlock")
async def unlock_vehicle(req: UnlockRequest):
    plate = req.plate.upper().strip()
    if plate not in active_vehicles:
        return {"error": "Vehicle not found"}

    active_vehicles[plate]["locked"] = False
    active_vehicles[plate]["status"] = "UNLOCKED"
    slot_id = active_vehicles[plate]["slot_id"]
    if slot_id and slot_id in slots_db:
        slots_db[slot_id]["locked"] = False

    await manager.broadcast_state()
    return {"status": "unlocked", "plate": plate}

@app.post("/api/security/loitering")
async def trigger_loitering(req: LoiteringAlertRequest):
    slot_id = req.slot_id.upper().strip()
    slot = slots_db.get(slot_id, {})
    owner_plate = slot.get("actual_plate") or slot.get("reserved_by") or "Unknown Vehicle"

    if req.human_loitering and slot.get("locked"):
        alert = add_alert(
            "CRITICAL",
            f"Suspicious Loitering Near {slot_id}",
            f"PIR/YOLO detected a person lingering around locked vehicle ({owner_plate}) at {slot_id}."
        )
        await manager.broadcast_event({"type": "ALERT", "alert": alert})
    await manager.broadcast_state()
    return {"status": "processed"}

@app.post("/api/gate/exit-scan")
async def gate_exit_scan(event: GateScanEvent):
    plate = event.plate.upper().strip()
    now = time.time()
    vehicle = active_vehicles.get(plate)

    if not vehicle:
        return {"error": "No active entry record for this vehicle"}

    slot_id = vehicle.get("slot_id")
    if slot_id and slot_id in slots_db:
        slots_db[slot_id]["status"] = "available"
        slots_db[slot_id]["reserved_by"] = None
        slots_db[slot_id]["actual_plate"] = None
        slots_db[slot_id]["locked"] = False

    duration_sec = max(1, int(now - vehicle["entry_time"]))
    billable_minutes = max(1, round(duration_sec / 60, 2))
    total_fee = round(billable_minutes * RATE_PER_MINUTE, 2)

    vehicle["exit_time"] = now
    vehicle["exit_time_str"] = datetime.fromtimestamp(now).strftime("%H:%M:%S")
    vehicle["duration_sec"] = duration_sec
    vehicle["bill"] = total_fee
    vehicle["status"] = "EXITED"

    await manager.broadcast_event({"type": "BILL_GENERATED", "vehicle": vehicle})
    await manager.broadcast_state()
    return {"status": "exited", "receipt": vehicle}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def udp_discovery_server():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind(("0.0.0.0", 8888))
    print("[UDP DISCOVERY] Listening for Android App auto-connect on port 8888...")
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            if data.decode("utf-8").strip() == "DISCOVER_SMART_PARK":
                udp_sock.sendto(b"SMART_PARK_HERE:8000", addr)
        except Exception:
            pass

threading.Thread(target=udp_discovery_server, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)