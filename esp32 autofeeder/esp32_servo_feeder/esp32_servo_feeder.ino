/*
 * ESP32 Servo Feeder Control
 * Controls servo motor on pin D25 to open/close feeder
 * Connects to Django backend for commands
 * 
 * Hardware:
 * - Servo Motor: GPIO 25 (D25)
 * - WiFi: ESP32 built-in
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ============================================
// WIFI CONFIGURATION
// ============================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ============================================
// DJANGO SERVER CONFIGURATION
// ============================================
const char* serverUrl = "http://192.168.137.1:8000/feeding/api/logs/servo-commands/";
const char* confirmUrl = "http://192.168.137.1:8000/feeding/api/logs/servo-confirm/";

// ============================================
// DEVICE CONFIGURATION
// ============================================
const char* deviceId = "feeder_servo_001";
const char* deviceName = "Servo Feeder 1";
const int feederId = 1;  // Feeder ID in Django database

// ============================================
// SERVO MOTOR CONFIGURATION
// ============================================
#define SERVO_PIN 25           // GPIO 25 (D25)
#define SERVO_CLOSE_ANGLE 0    // Servo angle when feeder is CLOSED
#define SERVO_OPEN_ANGLE 90    // Servo angle when feeder is OPEN
#define SERVO_FULL_OPEN 180    // Maximum open angle

Servo feederServo;
int currentServoAngle = SERVO_CLOSE_ANGLE;
bool feederIsOpen = false;

// ============================================
// TIMING CONFIGURATION
// ============================================
#define COMMAND_CHECK_INTERVAL 2000  // Check for commands every 2 seconds
#define FEED_DURATION_SMALL 2000     // Open duration for small portion (100g)
#define FEED_DURATION_MEDIUM 4000    // Open duration for medium portion (250g)
#define FEED_DURATION_LARGE 6000     // Open duration for large portion (500g)

unsigned long lastCommandCheck = 0;
unsigned long feedingStartTime = 0;
unsigned long feedingDuration = 0;
bool isFeeding = false;
int currentFeedLogId = 0;

// ============================================
// WiFi Connection
// ============================================
void connectWiFi() {
    Serial.println("\n📡 Connecting to WiFi...");
    Serial.printf("   SSID: %s\n", ssid);
    
    WiFi.begin(ssid, password);
    int attempts = 0;
    
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✓ WiFi Connected!");
        Serial.printf("   IP Address: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("   Signal Strength: %d dBm\n", WiFi.RSSI());
    } else {
        Serial.println("\n✗ WiFi Connection Failed!");
    }
}

// ============================================
// Servo Motor Control
// ============================================
void initServo() {
    feederServo.attach(SERVO_PIN);
    feederServo.write(SERVO_CLOSE_ANGLE);
    currentServoAngle = SERVO_CLOSE_ANGLE;
    feederIsOpen = false;
    Serial.println("✓ Servo motor initialized (Position: CLOSED)");
}

void openFeeder(int angle = SERVO_OPEN_ANGLE) {
    Serial.printf("🔓 Opening feeder to %d degrees...\n", angle);
    feederServo.write(angle);
    currentServoAngle = angle;
    feederIsOpen = true;
    delay(500);  // Give servo time to move
}

void closeFeeder() {
    Serial.println("🔒 Closing feeder...");
    feederServo.write(SERVO_CLOSE_ANGLE);
    currentServoAngle = SERVO_CLOSE_ANGLE;
    feederIsOpen = false;
    delay(500);  // Give servo time to move
}

// ============================================
// Check for Feed Commands from Django
// ============================================
void checkFeedCommands() {
    if (WiFi.status() != WL_CONNECTED) {
        return;
    }
    
    HTTPClient http;
    String url = String(serverUrl) + "?feeder_id=" + String(feederId);
    
    http.begin(url);
    http.setTimeout(5000);  // 5 second timeout
    http.addHeader("Content-Type", "application/json");
    
    int httpCode = http.GET();
    
    if (httpCode == HTTP_CODE_OK || httpCode == 200) {
        String payload = http.getString();
        
        // Parse JSON response
        StaticJsonDocument<512> doc;
        DeserializationError error = deserializeJson(doc, payload);
        
        if (!error && doc.containsKey("has_command") && doc["has_command"] == true) {
            // Extract command details
            int feedLogId = doc["feed_log_id"];
            int amount = doc["amount"];
            String mode = doc["mode"] | "manual";
            
            Serial.println("\n📥 New feed command received!");
            Serial.printf("   Feed Log ID: %d\n", feedLogId);
            Serial.printf("   Amount: %dg\n", amount);
            Serial.printf("   Mode: %s\n", mode.c_str());
            
            // Start feeding
            startFeeding(feedLogId, amount);
        }
    } else if (httpCode > 0) {
        Serial.printf("⚠ HTTP GET failed: %d\n", httpCode);
    }
    
    http.end();
}

// ============================================
// Start Feeding Process
// ============================================
void startFeeding(int feedLogId, int amount) {
    currentFeedLogId = feedLogId;
    
    // Determine feeding duration based on amount
    if (amount <= 100) {
        feedingDuration = FEED_DURATION_SMALL;
        openFeeder(60);  // Partial open
    } else if (amount <= 250) {
        feedingDuration = FEED_DURATION_MEDIUM;
        openFeeder(90);  // Medium open
    } else {
        feedingDuration = FEED_DURATION_LARGE;
        openFeeder(120);  // Wide open
    }
    
    feedingStartTime = millis();
    isFeeding = true;
    
    Serial.printf("🍽️ Feeding started: %dg for %dms\n", amount, feedingDuration);
}

// ============================================
// Update Feeding Process
// ============================================
void updateFeeding() {
    if (!isFeeding) {
        return;
    }
    
    unsigned long elapsed = millis() - feedingStartTime;
    
    if (elapsed >= feedingDuration) {
        // Feeding complete - close feeder
        closeFeeder();
        isFeeding = false;
        
        Serial.println("✓ Feeding complete!");
        
        // Confirm to Django server
        confirmFeedingComplete(currentFeedLogId);
    }
}

// ============================================
// Confirm Feeding Completion to Django
// ============================================
void confirmFeedingComplete(int feedLogId) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("✗ WiFi not connected, skipping confirmation");
        return;
    }
    
    HTTPClient http;
    http.begin(confirmUrl);
    http.setTimeout(5000);  // 5 second timeout
    http.addHeader("Content-Type", "application/json");
    
    // Create JSON payload
    StaticJsonDocument<256> doc;
    doc["feed_log_id"] = feedLogId;
    doc["status"] = "success";  // Valid status: pending, success, failed, partial
    doc["device_id"] = deviceId;
    
    String jsonPayload;
    serializeJson(doc, jsonPayload);
    
    Serial.println("📤 Confirming feeding completion...");
    Serial.printf("   URL: %s\n", confirmUrl);
    Serial.printf("   Payload: %s\n", jsonPayload.c_str());
    
    int httpCode = http.POST(jsonPayload);
    
    Serial.printf("   HTTP Response Code: %d\n", httpCode);
    
    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED || httpCode == 200) {
        String response = http.getString();
        Serial.println("✓ Feeding confirmed!");
        Serial.printf("   Response: %s\n", response.c_str());
    } else if (httpCode > 0) {
        String response = http.getString();
        Serial.printf("✗ Confirmation failed: HTTP %d\n", httpCode);
        Serial.printf("   Response: %s\n", response.c_str());
    } else {
        Serial.printf("✗ HTTP request failed: %s\n", http.errorToString(httpCode).c_str());
    }
    
    http.end();
}

// ============================================
// Display System Status
// ============================================
void displayStatus() {
    Serial.println("\n─────────────────────────────────────────────────────────");
    Serial.println("📊 SERVO FEEDER STATUS");
    Serial.println("─────────────────────────────────────────────────────────");
    Serial.printf("Device ID:       %s\n", deviceId);
    Serial.printf("Device Name:     %s\n", deviceName);
    Serial.printf("Feeder ID:       %d\n", feederId);
    Serial.printf("Servo Pin:       GPIO %d\n", SERVO_PIN);
    Serial.printf("Current Angle:   %d°\n", currentServoAngle);
    Serial.printf("Feeder Status:   %s\n", feederIsOpen ? "OPEN" : "CLOSED");
    Serial.printf("Feeding Active:  %s\n", isFeeding ? "YES" : "NO");
    Serial.printf("WiFi Status:     %s\n", WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected");
    Serial.printf("Server URL:      %s\n", serverUrl);
    Serial.println("─────────────────────────────────────────────────────────\n");
}

// ============================================
// SETUP
// ============================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n\n");
    Serial.println("╔════════════════════════════════════════════════════════╗");
    Serial.println("║       ESP32 SERVO FEEDER CONTROL SYSTEM               ║");
    Serial.println("║       Version 1.0 - 2026                              ║");
    Serial.println("╚════════════════════════════════════════════════════════╝");
    
    // Initialize servo motor
    Serial.println("\n⚙️ Initializing hardware...");
    initServo();
    
    // Connect to WiFi
    connectWiFi();
    
    // Display initial status
    displayStatus();
    
    Serial.println("✓ System ready! Monitoring for feed commands...\n");
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
    // Check WiFi connection
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("⚠ WiFi disconnected. Reconnecting...");
        connectWiFi();
        delay(5000);
        return;
    }
    
    // Update ongoing feeding process
    updateFeeding();
    
    // Check for new feed commands (every 2 seconds)
    if (millis() - lastCommandCheck >= COMMAND_CHECK_INTERVAL && !isFeeding) {
        checkFeedCommands();
        lastCommandCheck = millis();
    }
    
    delay(100);  // Small delay to prevent watchdog issues
}
