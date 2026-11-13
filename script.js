/* ---------- Simple helpers ---------- */
const $ = id => document.getElementById(id);
function toast(msg, ms = 3000) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), ms);
}

/* ---------- Navigation ---------- */
document.querySelectorAll("nav button").forEach(btn => btn.onclick = () => {
  document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  $(btn.dataset.go).classList.add("active");
});

/* ---------- Parking slots (simulated IoT sensors) ---------- */
// Prototype: 10 slots (2 rows x 5). In the real system each slot has a sensor;
// the ESP32 gateway pushes its status to the server and this page reads it.
const ROWS = ["A", "B"], COLS = 5;
const slots = [];
ROWS.forEach((r, ri) => {
  for (let c = 1; c <= COLS; c++) {
    const id = r + c;
    const reserved = (ri === 0 && c === 1); // example: A1 reserved for disabled parking
    slots.push({ id, status: reserved ? "reserved" : (Math.random() < 0.55 ? "occupied" : "free"), bookedBy: null });
  }
});
let selectedId = null;
let bookedSlot = null; // id of the slot this user has booked (e.g. "A3")

function renderMap() {
  const map = $("map"); map.innerHTML = "";
  ROWS.forEach((r, ri) => {
    const row = document.createElement("div");
    row.className = "row";
    slots.filter(s => s.id[0] === r).forEach(s => {
      const d = document.createElement("div");
      d.className = "slot " + s.status + (s.id === selectedId ? " selected" : "");
      d.textContent = s.id;
      d.title = s.id + " - " + s.status;
      d.onclick = () => selectSlot(s.id);
      row.appendChild(d);
    });
    map.appendChild(row);
    if (ri === 0) { const lane = document.createElement("div"); lane.className = "lane"; map.appendChild(lane); }
  });
  const free = slots.filter(s => s.status === "free").length;
  const occ = slots.filter(s => s.status === "occupied").length;
  $("freeCount").textContent = free;
  $("occCount").textContent = occ;
  $("totalCount").textContent = slots.length;
  $("updated").textContent = "Last updated: " + new Date().toLocaleTimeString();
}

function selectSlot(id) {
  selectedId = id;
  const s = slots.find(x => x.id === id);
  const label = { free: "🟢 Empty - you can park here", occupied: "🔴 Occupied", reserved: "🟡 Reserved" }[s.status];
  $("slotInfo").textContent = "Slot " + id + ": " + label;
  updateBookingButtons(s);
  renderMap();
}

function updateBookingButtons(s) {
  const bookBtn = $("bookBtn"), cancelBtn = $("cancelBookBtn");
  bookBtn.style.display = "none";
  cancelBtn.style.display = "none";
  if (bookedSlot === s.id) { cancelBtn.style.display = "block"; return; }
  if (!bookedSlot && s.status === "free") {
    bookBtn.style.display = "block";
    bookBtn.textContent = user ? "Book slot " + s.id : "Register to book slot " + s.id;
  }
}

// Simulate sensors changing every few seconds (booked and reserved slots are left alone)
setInterval(() => {
  const candidates = slots.filter(s => s.status !== "reserved");
  if (candidates.length === 0) return;
  const s = candidates[Math.floor(Math.random() * candidates.length)];
  s.status = s.status === "free" ? "occupied" : "free";
  renderMap();
}, 5000);
renderMap();

/* ---------- Registration flow ---------- */
let pendingPhone = "", pendingCode = "", user = null;

function show(id, visible) { $(id).style.display = visible ? "block" : "none"; }

function normalizePhone(p) { return p.replace(/[\s-]/g, ""); }

$("sendOtpBtn").onclick = () => {
  const phone = normalizePhone($("phone").value);
  if (!/^\+?\d{9,15}$/.test(phone)) { toast("Please enter a valid mobile number."); return; }
  pendingPhone = phone;
  pendingCode = String(Math.floor(100000 + Math.random() * 900000));
  // REAL SYSTEM: call your SMS gateway here (e.g. Twilio / local SMS provider) with pendingCode.
  $("otpHint").textContent = "Code sent to " + phone + ". (Demo code: " + pendingCode + ")";
  show("stepPhone", false); show("stepOtp", true);
  toast("Verification code sent by SMS");
};

$("resendBtn").onclick = () => {
  pendingCode = String(Math.floor(100000 + Math.random() * 900000));
  $("otpHint").textContent = "New code sent to " + pendingPhone + ". (Demo code: " + pendingCode + ")";
  toast("New code sent");
};

$("verifyOtpBtn").onclick = () => {
  if ($("otp").value.trim() === pendingCode) {
    user = { phone: pendingPhone, verified: true, vehicle: null, monitoring: false };
    show("stepOtp", false); show("stepVehicle", true);
    toast("Phone verified ✔");
  } else {
    toast("Wrong code. Please try again.");
  }
};

$("saveVehicleBtn").onclick = async () => {
  const v = $("vehicle").value.trim().toUpperCase().replace(/\s+/g, " ");
  if (v.length < 4) { toast("Please enter a valid vehicle number."); return; }
  user.vehicle = v; user.monitoring = true;
  if ("Notification" in window && Notification.permission === "default") {
    try { await Notification.requestPermission(); } catch (e) {}
  }
  show("stepVehicle", false); show("profile", true);
  renderProfile();
  toast("Vehicle registered. Anti-theft monitoring is ON.");
};

function renderProfile() {
  $("pPhone").textContent = user.phone;
  $("pVehicle").textContent = user.vehicle;
  $("pMonitor").innerHTML = user.monitoring ? '<span class="ok">Active</span>' : '<span class="bad">Off</span>';
  $("pAlertTo").textContent = user.phone;
  $("pBooking").textContent = bookedSlot || "None";
}

$("logoutBtn").onclick = () => {
  releaseBooking();
  user = null; pendingPhone = ""; pendingCode = "";
  $("phone").value = ""; $("otp").value = ""; $("vehicle").value = "";
  show("profile", false); show("stepPhone", true);
  $("alarmAccount").classList.remove("show");
  const s = slots.find(x => x.id === selectedId);
  if (s) updateBookingButtons(s);
};

/* ---------- Slot booking ---------- */
function goToAccount() {
  document.querySelector('nav button[data-go="account"]').click();
}

function releaseBooking() {
  const s = slots.find(x => x.id === bookedSlot);
  if (s) { s.status = "free"; s.bookedBy = null; }
  bookedSlot = null;
  if ($("pBooking")) $("pBooking").textContent = "None";
}

$("bookBtn").onclick = () => {
  if (!user || !user.verified) { toast("Please register your phone first."); goToAccount(); return; }
  if (!user.vehicle) { toast("Please add your vehicle number first."); goToAccount(); return; }
  if (bookedSlot) { toast("You already have slot " + bookedSlot + " booked."); return; }
  const s = slots.find(x => x.id === selectedId);
  if (!s || s.status !== "free") { toast("Sorry, this slot is no longer free."); return; }
  s.status = "reserved"; s.bookedBy = user.phone; bookedSlot = s.id;
  $("slotInfo").textContent = "✅ Slot " + s.id + " booked for " + user.vehicle + ". Please park in this slot when you arrive.";
  $("pBooking").textContent = bookedSlot;
  updateBookingButtons(s);
  renderMap();
  toast("Slot " + s.id + " booked");
};

$("cancelBookBtn").onclick = () => {
  const id = bookedSlot;
  releaseBooking();
  $("slotInfo").textContent = "Booking cancelled. Slot " + id + " is free again.";
  const s = slots.find(x => x.id === selectedId);
  if (s) updateBookingButtons(s);
  renderMap();
  toast("Booking cancelled");
};

/* ---------- Security / tamper alarm ---------- */
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    for (let i = 0; i < 3; i++) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
      g.gain.value = 0.2; o.start(ctx.currentTime + i * 0.4); o.stop(ctx.currentTime + i * 0.4 + 0.25);
    }
  } catch (e) {}
}

function raiseAlarm(vehicle) {
  const msg = "⚠️ SECURITY ALERT: Tampering detected on vehicle " + vehicle +
              " at " + new Date().toLocaleTimeString() + ". Security has been notified.";
  ["alarmHome", "alarmAccount"].forEach(id => { const a = $(id); a.textContent = msg; a.classList.add("show"); });
  beep();
  if ("vibrate" in navigator) navigator.vibrate([400, 200, 400, 200, 400]);
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("Eazy Park - Security Alarm", { body: "Tampering detected on " + vehicle });
  }
  // REAL SYSTEM: the server pushes this event to the user by SMS / push notification.
  toast("SMS alert sent to " + user.phone);
}

$("simTamperBtn").onclick = () => {
  if (!user || !user.monitoring) { toast("Register your vehicle first."); return; }
  raiseAlarm(user.vehicle);
};

// Clicking an alarm banner dismisses it
["alarmHome", "alarmAccount"].forEach(id => $(id).onclick = () => $(id).classList.remove("show"));