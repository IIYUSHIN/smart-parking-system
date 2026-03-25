/*
 * ═══════════════════════════════════════════════════════════
 * SMART PARKING SYSTEM — Arduino Firmware
 * ═══════════════════════════════════════════════════════════
 *
 * Hardware:  Arduino Uno
 * Sensors:   2x IR (Entry on Pin 2, Exit on Pin 3)
 * Actuator:  Servo motor (Pin 9)
 * Display:   16x2 LCD (I2C, address 0x27)
 * Serial:    9600 baud, JSON output via USB
 *
 * Logic:     Centralized total-capacity counting (count-based)
 * Safety:    Barrier is rule-based, AI never controls barrier
 * ═══════════════════════════════════════════════════════════
 */

#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ── PIN DEFINITIONS ──
#define ENTRY_IR_PIN   2
#define EXIT_IR_PIN    3
#define SERVO_PIN      9

// ── PARKING CONFIGURATION ──
const int MAX_CAPACITY = 4;

// ── STATE VARIABLES ──
int currentCount = 0;

// ── DEBOUNCE ──
unsigned long lastEntryTrigger = 0;
unsigned long lastExitTrigger  = 0;
const unsigned long DEBOUNCE_MS = 1000;

// ── SENSOR STATE TRACKING ──
bool entryBlocked = false;
bool exitBlocked  = false;

// ── HARDWARE OBJECTS ──
Servo barrierServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);


// ═══════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════

void setup() {
    // Serial communication (USB to Python on laptop)
    Serial.begin(9600);

    // IR sensor pins
    pinMode(ENTRY_IR_PIN, INPUT);
    pinMode(EXIT_IR_PIN, INPUT);

    // Servo initialization
    barrierServo.attach(SERVO_PIN);
    barrierServo.write(0);  // Start closed

    // LCD initialization
    lcd.init();
    lcd.backlight();
    lcd.setCursor(0, 0);
    lcd.print("Smart Parking   ");
    lcd.setCursor(0, 1);
    lcd.print("Slots: 0/4  OK  ");

    // Boot event via serial
    Serial.println("{\"e\":\"BOOT\",\"c\":0,\"m\":4,\"t\":0}");

    delay(1000);  // Startup stabilization
}


// ═══════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════

void loop() {
    checkEntry();
    checkExit();
    delay(50);  // 50ms loop cycle — balances responsiveness and stability
}


// ═══════════════════════════════════════════════════════════
// ENTRY DETECTION (Module M1)
// ═══════════════════════════════════════════════════════════

void checkEntry() {
    int sensorState = digitalRead(ENTRY_IR_PIN);
    unsigned long now = millis();

    // IR sensor: LOW = object detected (beam broken)
    if (sensorState == LOW && !entryBlocked
        && (now - lastEntryTrigger > DEBOUNCE_MS)) {

        entryBlocked = true;
        lastEntryTrigger = now;

        if (currentCount < MAX_CAPACITY) {
            currentCount++;
            openBarrier();
            updateLCD();
            sendSerialJSON("ENTRY");
        }
        // If full: barrier stays closed, no count change, no serial output
    }

    // Reset when object passes (beam restored)
    if (sensorState == HIGH) {
        entryBlocked = false;
    }
}


// ═══════════════════════════════════════════════════════════
// EXIT DETECTION (Module M2)
// ═══════════════════════════════════════════════════════════

void checkExit() {
    int sensorState = digitalRead(EXIT_IR_PIN);
    unsigned long now = millis();

    if (sensorState == LOW && !exitBlocked
        && (now - lastExitTrigger > DEBOUNCE_MS)) {

        exitBlocked = true;
        lastExitTrigger = now;

        if (currentCount > 0) {
            currentCount--;
            openBarrier();
            updateLCD();
            sendSerialJSON("EXIT");
        }
        // If empty: no decrement, no serial output
    }

    if (sensorState == HIGH) {
        exitBlocked = false;
    }
}


// ═══════════════════════════════════════════════════════════
// BARRIER CONTROL (Module M4) — Rule-based, local, deterministic
// ═══════════════════════════════════════════════════════════

void openBarrier() {
    barrierServo.write(90);   // Open position
    delay(3000);              // Hold 3 seconds for vehicle passage
    barrierServo.write(0);    // Close position
}


// ═══════════════════════════════════════════════════════════
// LCD DISPLAY UPDATE
// ═══════════════════════════════════════════════════════════

void updateLCD() {
    lcd.setCursor(0, 1);
    lcd.print("Slots: ");
    lcd.print(currentCount);
    lcd.print("/");
    lcd.print(MAX_CAPACITY);
    lcd.print("  ");

    if (currentCount >= MAX_CAPACITY) {
        lcd.print("FULL");
    } else {
        lcd.print("OK  ");
    }
}


// ═══════════════════════════════════════════════════════════
// SERIAL JSON OUTPUT (Module M5) — USB to Python
// ═══════════════════════════════════════════════════════════
// Format: {"e":"ENTRY","c":1,"m":4,"t":12345}
//   e = event type (ENTRY / EXIT / BOOT)
//   c = current count after event
//   m = max capacity
//   t = Arduino millis() timestamp

void sendSerialJSON(const char* eventType) {
    Serial.print("{\"e\":\"");
    Serial.print(eventType);
    Serial.print("\",\"c\":");
    Serial.print(currentCount);
    Serial.print(",\"m\":");
    Serial.print(MAX_CAPACITY);
    Serial.print(",\"t\":");
    Serial.print(millis());
    Serial.println("}");
}
