#include <ESP32Servo.h>

Servo entryGate;
Servo exitGate;

// 8 IR Sensors for S1 - S8
const int irPins[8] = {14, 27, 26, 25, 32, 35, 34, 39};
const int pirPin = 33;
const int entryServoPin = 13;
const int exitServoPin = 12;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 8; i++) {
    pinMode(irPins[i], INPUT);
  }
  pinMode(pirPin, INPUT);

  entryGate.attach(entryServoPin);
  exitGate.attach(exitServoPin);
  entryGate.write(0);
  exitGate.write(0);
}

void loop() {
  Serial.print("{");
  for (int i = 0; i < 8; i++) {
    int val = (digitalRead(irPins[i]) == LOW) ? 1 : 0;
    Serial.print("\"S");
    Serial.print(i + 1);
    Serial.print("\":");
    Serial.print(val);
    Serial.print(",");
  }
  int pir = (digitalRead(pirPin) == HIGH) ? 1 : 0;
  Serial.print("\"pir\":");
  Serial.print(pir);
  Serial.println("}");

  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "OPEN_ENTRY_GATE") {
      entryGate.write(90);
      delay(4000);
      entryGate.write(0);
    } else if (cmd == "OPEN_EXIT_GATE") {
      exitGate.write(90);
      delay(4000);
      exitGate.write(0);
    }
  }

  delay(500);
}
