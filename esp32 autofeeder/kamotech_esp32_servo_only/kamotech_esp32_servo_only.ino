/*
 * ═══════════════════════════════════════════════════════════════════
 * KAMOTECH ESP32 - SERVO/FEEDER ONLY
 * ═══════════════════════════════════════════════════════════════════
 * 
 * Simplified version - Servo Motor Control Only
 * Device Name: kamotech esp32 servo
 * 
 * HARDWARE CONFIGURATION (SERVO ONLY)
 * ----------------------
 * ACTUATORS:
 * - Servo Motor (Feeder)          → GPIO 25
 * 
 * BUTTONS (Physical Control):
 * - Servo Button                  → GPIO 15
 * 
 * FEATURES:
 * - Remote servo control via API
 * - Physical button control
 * - Auto WiFi reconnection
 * - Status LED indicator
 * 
 * ═══════════════════════════════════════════════════════════════════
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ═══════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════

// WiFi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Django Server Configuration
// ⚠️ IMPORTANT: Update this IP when your laptop restarts!
const char* commandUrl = "http://10.87.22.155:8000/iot/api/actuators/esp32_commands/";
const char* syncUrl = "http://192.168.137.1:8000/iot/api/actuators/esp32_sync_state/";

// Device Configuration
const char* deviceId = "kamotech_esp32_servo_001";
const char* deviceName = "kamotech esp32 servo";

// Pin Definitions
// Actuators
#define SERVO_PIN 13

// Ultrasonic Sensor (Feed Level)
#define ULTRASONIC_TRIG 5
#define ULTRASONIC_ECHO 18

// I2C LCD
#define I2C_SDA 21
#define I2C_SCL 22
#define LCD_ADDRESS 0x27

// Buttons
#define SERVO_BUTTON 15

// Status LED
#define STATUS_LED 2

// Timing Configuration
#define BUTTON_DEBOUNCE 200           // Button debounce delay
#define ACTUATOR_CHECK_INTERVAL 5000  // Check for actuator commands every 5 seconds
#define FEED_DURATION 2000            // Servo opens for 2 seconds
#define FEED_ANGLE 45                 // Servo open angle (degrees)
#define LCD_UPDATE_INTERVAL 1000      // Update LCD every 1 second

// Feed bin calibration (cm)
#define FEED_FULL_CM 5.0
#define FEED_EMPTY_CM 30.0

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS & VARIABLES
// ═══════════════════════════════════════════════════════════════════

Servo feederServo;
HTTPClient http;
LiquidCrystal_I2C lcd(LCD_ADDRESS, 16, 2);

// Actuator States
bool isFeeding = false;
unsigned long feedingStartTime = 0;
int servoAngle = 0;

// Button States
bool lastServoButtonState = HIGH;

// Timing Variables
unsigned long lastActuatorCheck = 0;
unsigned long lastServoButtonPress = 0;
unsigned long lastLcdUpdate = 0;

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("╔════════════════════════════════════════════════════════╗");
  Serial.println("║     KAMOTECH ESP32 - SERVO/FEEDER ONLY                ║");
  Serial.println("╚════════════════════════════════════════════════════════╝");
  Serial.println();
  
  // Initialize Pins
  initializePins();
  
  // Initialize Sensors
  initializeSensors();
  
  // Connect to WiFi
  connectWiFi();
  
  // Print configuration
  printConfiguration();
  
  Serial.println("\n✓ System ready! Waiting for commands...\n");
  Serial.println("─────────────────────────────────────────────────────────");
}

// ═══════════════════════════════════════════════════════════════════
// INITIALIZATION FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

void initializePins() {
  Serial.println("🔧 Initializing pins...");
  
  // Status LED
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);
  
  // Button Pins (with internal pull-up resistors)
  pinMode(SERVO_BUTTON, INPUT_PULLUP);

  // Ultrasonic pins
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);
  digitalWrite(ULTRASONIC_TRIG, LOW);
  
  Serial.println("✓ Pins initialized");
}

void initializeSensors() {
  Serial.println("🎮 Initializing servo...");
  
  // Servo Motor
  feederServo.attach(SERVO_PIN);
  feederServo.write(0);  // Initial position (closed)
  servoAngle = 0;
  
  Serial.println("✓ Servo initialized (position: 0°)");

  Serial.println("📟 Initializing LCD...");
  Wire.begin(I2C_SDA, I2C_SCL);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Feed Level");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(800);
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
  unsigned long currentMillis = millis();
  
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n⚠️  WiFi connection lost! Reconnecting...");
    connectWiFi();
  }
  
  // Check for actuator control commands from server
  if (currentMillis - lastActuatorCheck >= ACTUATOR_CHECK_INTERVAL) {
    checkActuatorCommands();
    lastActuatorCheck = currentMillis;
  }
  
  // Handle physical button presses
  handleButton();
  
  // Update feeding process (auto-close servo after 2 seconds)
  updateFeeding();

  // Update LCD with feed level
  if (currentMillis - lastLcdUpdate >= LCD_UPDATE_INTERVAL) {
    updateFeedLevelDisplay();
    lastLcdUpdate = currentMillis;
  }
  
  // Blink LED to show system is alive
  if (currentMillis % 2000 < 100) {
    digitalWrite(STATUS_LED, HIGH);
  } else {
    digitalWrite(STATUS_LED, LOW);
  }
  
  delay(100);
}

// ═══════════════════════════════════════════════════════════════════
// WIFI CONNECTION
// ═══════════════════════════════════════════════════════════════════

void connectWiFi() {
  Serial.println("\n📡 Connecting to WiFi...");
  Serial.print("   SSID: ");
  Serial.println(ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED, HIGH);
    Serial.println("\n✓ WiFi Connected!");
    Serial.print("   IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("   Signal: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    digitalWrite(STATUS_LED, LOW);
    Serial.println("\n✗ WiFi Connection Failed!");
  }
}

// ═══════════════════════════════════════════════════════════════════
// ACTUATOR CONTROL FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

void checkActuatorCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  // Build command URL with device_id parameter
  String url = String(commandUrl) + "?device_id=" + deviceId;
  
  http.begin(url);
  http.setTimeout(5000);
  
  int httpResponseCode = http.GET();
  
  if (httpResponseCode == 200) {
    String payload = http.getString();
    
    // Parse JSON response
    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error && doc.containsKey("commands")) {
      JsonArray commands = doc["commands"].as<JsonArray>();
      
      for (JsonObject cmd : commands) {
        String type = cmd["type"].as<String>();
        String state = cmd["state"].as<String>();
        
        // Execute feeder/servo commands
        if (type == "feeder" || type == "servo") {
          if (state == "on" && !isFeeding) {
            Serial.println("📱 Remote command: Start feeding");
            startFeeding();
          }
        }
      }
    }
  } else if (httpResponseCode > 0) {
    // HTTP error but connection worked
    Serial.print("⚠️  Command check HTTP error: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}

void updateDjangoState(String actuatorType, String state) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Not connected to WiFi, cannot sync state");
    return;
  }
  
  http.begin(syncUrl);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  
  // Create JSON payload
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceId;
  doc["actuator_type"] = actuatorType;
  doc["state"] = state;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode == 200) {
    Serial.print("✅ Synced to Django: ");
    Serial.print(actuatorType);
    Serial.print(" = ");
    Serial.println(state);
  } else {
    Serial.print("⚠️ Sync failed (HTTP ");
    Serial.print(httpResponseCode);
    Serial.print("): ");
    Serial.print(actuatorType);
    Serial.print(" = ");
    Serial.println(state);
  }
  
  http.end();
}

void updateDjangoStateWithButton(String actuatorType, String state) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Not connected to WiFi, cannot sync state");
    return;
  }
  
  http.begin(syncUrl);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  
  // Create JSON payload with physical_button trigger
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceId;
  doc["actuator_type"] = actuatorType;
  doc["state"] = state;
  doc["triggered_by"] = "physical_button";
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  Serial.print("🔘 Physical button ");
  Serial.print(actuatorType);
  Serial.print(" → ");
  Serial.println(state);
  
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode == 200) {
    Serial.println("✅ Physical button action logged to Django");
  } else {
    Serial.print("⚠️ Failed to log (HTTP ");
    Serial.print(httpResponseCode);
    Serial.println(")");
  }
  
  http.end();
}

void startFeeding() {
  if (isFeeding) {
    return;  // Already feeding, don't start again
  }
  
  Serial.println("🍽️ AUTO-FEEDING: Opening feeder...");
  feederServo.write(FEED_ANGLE);  // Open to feed angle
  servoAngle = FEED_ANGLE;
  isFeeding = true;
  feedingStartTime = millis();
}

void updateFeeding() {
  if (!isFeeding) {
    return;
  }
  
  unsigned long elapsed = millis() - feedingStartTime;
  
  if (elapsed >= FEED_DURATION) {
    // 2 seconds elapsed - close feeder
    Serial.println("✓ AUTO-FEEDING: Closing feeder");
    feederServo.write(0);  // Close to 0°
    servoAngle = 0;
    isFeeding = false;
    
    // Sync back to Django - set feeder to "off" so it doesn't retrigger
    updateDjangoState("feeder", "off");
  }
}

// ═══════════════════════════════════════════════════════════════════
// FEED LEVEL (ULTRASONIC + LCD)
// ═══════════════════════════════════════════════════════════════════

float readUltrasonicCm() {
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);

  long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 30000); // 30ms timeout
  if (duration == 0) {
    return -1.0;
  }

  // Speed of sound: 0.0343 cm/us
  return (duration * 0.0343f) / 2.0f;
}

int calculateFeedLevelPercent(float distanceCm) {
  if (distanceCm < 0) {
    return -1;
  }

  float clamped = distanceCm;
  if (clamped < FEED_FULL_CM) clamped = FEED_FULL_CM;
  if (clamped > FEED_EMPTY_CM) clamped = FEED_EMPTY_CM;

  float ratio = (FEED_EMPTY_CM - clamped) / (FEED_EMPTY_CM - FEED_FULL_CM);
  int percent = (int)(ratio * 100.0f + 0.5f);
  if (percent < 0) percent = 0;
  if (percent > 100) percent = 100;
  return percent;
}

void updateFeedLevelDisplay() {
  float distance = readUltrasonicCm();
  int percent = calculateFeedLevelPercent(distance);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Feed Level:");

  lcd.setCursor(0, 1);
  if (percent < 0) {
    lcd.print("No echo");
  } else {
    lcd.print(percent);
    lcd.print("%  ");
    lcd.print((int)distance);
    lcd.print("cm");
  }
}

// ═══════════════════════════════════════════════════════════════════
// BUTTON HANDLING
// ═══════════════════════════════════════════════════════════════════

void handleButton() {
  unsigned long currentMillis = millis();
  
  // Servo Button - Auto Feed (Open 180° for 2 seconds, then auto-close)
  bool servoButtonState = digitalRead(SERVO_BUTTON);
  if (servoButtonState == LOW && lastServoButtonState == HIGH) {
    if (currentMillis - lastServoButtonPress > BUTTON_DEBOUNCE) {
      if (!isFeeding) {
        startFeeding();  // Start auto-feed cycle
        // Sync actuator state to Django with physical button flag
        updateDjangoStateWithButton("feeder", "on");
      }
      lastServoButtonPress = currentMillis;
    }
  }
  lastServoButtonState = servoButtonState;
}

// ═══════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

void printConfiguration() {
  Serial.println("\n📋 System Configuration (SERVO ONLY):");
  Serial.println("  ╔════════════════════════════════════════════════╗");
  Serial.println("  ║              ACTUATORS                         ║");
  Serial.println("  ╠════════════════════════════════════════════════╣");
  Serial.println("  ║  Servo Motor (Feeder)    → GPIO 25              ║");
  Serial.println("  ║    Position: 0° = Closed, 45° = Open           ║");
  Serial.println("  ║    Auto-feed Duration: 2 seconds               ║");
  Serial.println("  ╠════════════════════════════════════════════════╣");
  Serial.println("  ║              BUTTONS                           ║");
  Serial.println("  ╠════════════════════════════════════════════════╣");
  Serial.println("  ║  Servo/Feed Button       → GPIO 15              ║");
  Serial.println("  ║    (Open 180° for 2sec, auto-close)            ║");
  Serial.println("  ╠════════════════════════════════════════════════╣");
  Serial.println("  ║              SENSORS                           ║");
  Serial.println("  ║  Ultrasonic (Feed)     → TRIG 5, ECHO 18        ║");
  Serial.println("  ║  LCD I2C               → SDA 21, SCL 22         ║");
  Serial.println("  ╚════════════════════════════════════════════════╝");
  Serial.println();
  Serial.print("  Command URL: ");
  Serial.println(commandUrl);
  Serial.print("  Sync URL: ");
  Serial.println(syncUrl);
}

// ═══════════════════════════════════════════════════════════════════
// END OF CODE
// ═══════════════════════════════════════════════════════════════════
