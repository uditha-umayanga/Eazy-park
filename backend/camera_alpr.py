import cv2
import easyocr
import requests
import re
import time

BACKEND_URL = "http://localhost:8000"
CAMERA_INDEX = 0  # 0 = Laptop Built-in Cam, 1 = External USB Webcam

print("Loading ALPR OCR Model...")
reader = easyocr.Reader(['en'], gpu=False)
cap = cv2.VideoCapture(CAMERA_INDEX)

last_sent_plate = ""
last_sent_time = 0

print("Entry Gate Camera Active! Show a number plate (1-line or 2-line)...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    small_frame = cv2.resize(frame, (640, 480))
    results = reader.readtext(small_frame)

    letters_part = ""
    numbers_part = ""
    full_plate = ""

    for (bbox, text, prob) in results:
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())
        if prob > 0.35 and len(clean_text) >= 2:
            # Draw box around detected text
            (tl, tr, br, bl) = bbox
            cv2.rectangle(small_frame, (int(tl[0]), int(tl[1])), (int(br[0]), int(br[1])), (0, 255, 0), 2)
            cv2.putText(small_frame, clean_text, (int(tl[0]), int(tl[1]) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Case 1: Single line plate (e.g., CAB1234 or WPCAB1234)
            if len(clean_text) >= 6 and any(c.isalpha() for c in clean_text) and any(c.isdigit() for c in clean_text):
                full_plate = clean_text

            # Case 2: Two-line plate (Line 1: CBO, Line 2: 3286)
            elif clean_text.isalpha() and 2 <= len(clean_text) <= 5:
                # Ignore province codes like WP, CP, SP if needed, or keep main letters
                if clean_text not in ["WP", "CP", "SP", "NW", "NC", "UV", "SG", "EP", "NP"]:
                    letters_part = clean_text
            elif clean_text.isdigit() and len(clean_text) == 4:
                numbers_part = clean_text

    # Combine 2-line plate if both letters and 4 digits are detected
    if not full_plate and letters_part and numbers_part:
        full_plate = f"{letters_part}-{numbers_part}"

    if full_plate:
        cv2.putText(small_frame, f"DETECTED: {full_plate}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)

        if full_plate != last_sent_plate or (time.time() - last_sent_time > 8):
            try:
                requests.post(f"{BACKEND_URL}/api/gate/entry-scan", json={
                    "plate": full_plate,
                    "vehicle_type": "Car"
                })
                print(f"[AUTO-SCANNED] Sent Plate to App: {full_plate}")
                last_sent_plate = full_plate
                last_sent_time = time.time()
            except Exception as e:
                print("Backend connection error:", e)

    cv2.imshow("Camera 1 - Entry Gate ALPR", small_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()