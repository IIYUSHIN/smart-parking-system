#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ═══════════════════════════════════════════════════════════
// PIN CONFIGURATION
// ═══════════════════════════════════════════════════════════
const int ENTRY_IR_PIN = 2;   // Entry IR Sensor OUT pin
const int EXIT_IR_PIN = 3;    // Exit IR Sensor OUT pin
const int SERVO_PIN = 9;      // Servo Motor Signal pin

// ═══════════════════════════════════════════════════════════
// PARKING LIMITS
// ═══════════════════════════════════════════════════════════
const int MAX_CAPACITY = 4;   // Matches ARDUINO_MAX_CAPACITY in config.py
int currentCount = 0;         // Current number of cars

// ═══════════════════════════════════════════════════════════
// HARDWARE OBJECTS
// ═══════════════════════════════════════════════════════════
Servo gateServo;
// Initialize I2C LCD (Address 0x27 is common, 16 columns, 2 rows)
LiquidCrystal_I2C lcd(0x27, 16, 2); 

// ═══════════════════════════════════════════════════════════
// STATE VARIABLES to prevent multiple triggers for one car
// ═══════════════════════════════════════════════════════════
bool entryTriggered = false;
bool exitTriggered = false;

void setup() {
  // 1. Initialize Serial Communication at 9600 baud rate
  Serial.begin(9600);
  
  // 2. Setup Sensor Pins
  pinMode(ENTRY_IR_PIN, INPUT);
  pinMode(EXIT_IR_PIN, INPUT);
  
  // 3. Setup Servo Motor (Default closed position = 90 degrees)
  gateServo.attach(SERVO_PIN);
  gateServo.write(90); 
  
  // 4. Setup LCD Display
  lcd.init();
  lcd.backlight();
  updateLCD();
  
  // Send Boot Sequence to Python Backend
  Serial.println("{\"e\": \"BOOT\", \"c\": 0, \"m\": 4}");
  delay(1000);
}

void loop() {
  // IR Sensors usually output LOW (0) when an object is detected
  int entryState = digitalRead(ENTRY_IR_PIN);
  int exitState = digitalRead(EXIT_IR_PIN);

  // ── HANDLE ENTRY ──
  if (entryState == LOW && !entryTriggered) {
    entryTriggered = true; // Block further triggers until car passes
    
    if (currentCount < MAX_CAPACITY) {
      currentCount++;
      sendEventToLaptop("ENTRY");
      openGate();
      updateLCD();
    } else {
      // Parking is Full
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("PARKING FULL!");
      delay(2000);
      updateLCD();
    }
  } 
  // Reset trigger when car leaves the sensor
  else if (entryState == HIGH && entryTriggered) {
    delay(500); // Debounce delay
    entryTriggered = false;
  }

  // ── HANDLE EXIT ──
  if (exitState == LOW && !exitTriggered) {
    exitTriggered = true;
    
    if (currentCount > 0) {
      currentCount--;
      sendEventToLaptop("EXIT");
      openGate();
      updateLCD();
    }
  } 
  // Reset trigger when car leaves the sensor
  else if (exitState == HIGH && exitTriggered) {
    delay(500);
    exitTriggered = false;
  }
}

// ═══════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════

void openGate() {
  // Open gate (0 degrees)
  gateServo.write(0);
  delay(3000); // Keep open for 3 seconds
  // Close gate (90 degrees)
  gateServo.write(90);
}

void updateLCD() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SmartPark v2.0");
  
  lcd.setCursor(0, 1);
  if (currentCount >= MAX_CAPACITY) {
    lcd.print("Status: FULL    ");
  } else {
    lcd.print("Available: ");
    lcd.print(MAX_CAPACITY - currentCount);
    lcd.print("  ");
  }
}

void sendEventToLaptop(String eventType) {
  // Format exactly matching what serial_bridge.py expects:
  // {"e": "ENTRY", "c": 2, "m": 4}
  Serial.print("{\"e\": \"");
  Serial.print(eventType);
  Serial.print("\", \"c\": ");
  Serial.print(currentCount);
  Serial.print(", \"m\": ");
  Serial.print(MAX_CAPACITY);
  Serial.println("}");
}
