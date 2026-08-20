/*
 * ESP32 IoT KaMoTech System - Django Integration
 * 
 * Features:
 * - Automated Feeder (Servo Motor)
 * - Ultrasonic Feed Level Monitoring
 * - Door Actuator Control (Relays)
 * - Light Control
 * - Rain Detection
 * - Web Dashboard Integration with Django REST API
 * 
 * Django API Endpoints:
 * - POST /feeding/api/levels/update/ - Update feed level
 * - POST /feeding/api/logs/ - Log feeding events
 * - POST /iot/api/actuators/{id}/control/ - Control actuators
 * - GET /iot/api/actuators/status/ - Get actuator states
 * 
 * Author: KaMoTech
 * Date: March 2026
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

// ============================================
// WIFI CONFIGURATION
// ============================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ============================================
// DJANGO SERVER CONFIGURATION
// ============================================
const char* django_server = "192.168.137.1";  // Your Django server IP
const int django_port = 8000;
const int device_id = 1;  // This ESP32's device ID in Django database

// API Endpoints
String api_feed_level = "http://" + String(django_server) + ":" + String(django_port) + "/feeding/api/levels/update/";
String api_feed_log = "http://" + String(django_server) + ":" + String(django_port) + "/feeding/api/logs/";
String api_actuator_status = "http://" + String(django_server) + ":" + String(django_port) + "/iot/api/actuators/status/";

// ============================================
// PIN DEFINITIONS (ESP32 GPIO)
// ============================================
// Automated Feeder
#define SERVO_PIN 25          // PWM output for servo motor (feeder dispenser)

// Door Actuator (Linear Actuator with Relays)
#define RELAY_DOOR_OPEN 26    // Relay to extend actuator (open door)
#define RELAY_DOOR_CLOSE 27   // Relay to retract actuator (close door)

// Light Control
#define LIGHT_PIN 13          // Relay for automated light

// Sensors
#define RAIN_SENSOR_PIN 32    // Analog input for rain sensor
#define TRIG_PIN 5            // Ultrasonic sensor trigger
#define ECHO_PIN 18           // Ultrasonic sensor echo

// Manual Control Buttons
#define BTN_DOOR 15           // Manual door control button
#define BTN_LIGHT 33          // Manual light toggle button
#define BTN_FEED 34           // Manual feed dispense button (input only)

// ============================================
// SERVO MOTOR CONFIGURATION
// ============================================
Servo feederServo;
#define SERVO_CLOSED_ANGLE 0    // Servo angle when feeder is closed
#define SERVO_OPEN_ANGLE 90     // Servo angle when dispensing feed
#define SERVO_DISPENSE_TIME 3000 // Time to keep servo open (ms)
bool is_feeding = false;
unsigned long feed_start_time = 0;

// ============================================
// ULTRASONIC SENSOR (Feed Level Monitoring)
// ============================================
#define FEED_CONTAINER_HEIGHT 30    // Total container depth (cm)
#define FEED_FULL_DISTANCE 5        // Distance when full (cm)
#define FEED_EMPTY_DISTANCE 28      // Distance when empty (cm)
#define ULTRASONIC_CHECK_INTERVAL 5000  // Check every 5 seconds
unsigned long last_ultrasonic_check = 0;
float current_feed_distance = 0;
int current_feed_percentage = 0;

// ============================================
// RAIN SENSOR
// ============================================
#define RAIN_THRESHOLD 2000         // Analog threshold for rain detection
#define RAIN_CHECK_INTERVAL 10000   // Check every 10 seconds
unsigned long last_rain_check = 0;
bool is_raining = false;

// ============================================
// ACTUATOR STATES
// ============================================
// Door States: 0=STOPPED, 1=OPENING, 2=CLOSING
int door_state = 0;
unsigned long door_action_start = 0;
#define DOOR_MOVE_TIME 10000  // Time for door to fully open/close (ms)

// Light State
bool light_state = false;

// ============================================
// BUTTON DEBOUNCING
// ============================================
unsigned long last_button_press = 0;
#define DEBOUNCE_DELAY 200

// ============================================
// REPORTING INTERVALS
// ============================================
#define REPORT_FEED_LEVEL_INTERVAL 30000  // Report feed level every 30 seconds
unsigned long last_feed_level_report = 0;

#define CHECK_DJANGO_COMMANDS_INTERVAL 10000  // Check for commands every 10 seconds
unsigned long last_django_check = 0;

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n╔════════════════════════════════════════════╗");
  Serial.println("║   KaMoTech System - v2.0                  ║");
  Serial.println("║   Django Integration - March 2026         ║");
  Serial.println("╚════════════════════════════════════════════╝\n");
  
  // Initialize Pins
  initializePins();
  
  // Initialize WiFi
  initializeWiFi();
  
  // Initialize Servo
  feederServo.attach(SERVO_PIN);
  feederServo.write(SERVO_CLOSED_ANGLE);
  delay(500);
  
  Serial.println("✓ System Ready!\n");
}

void initializePins() {
  Serial.println("Initializing pins...");
  
  // Door Relays (start with both OFF)
  pinMode(RELAY_DOOR_OPEN, OUTPUT);
  pinMode(RELAY_DOOR_CLOSE, OUTPUT);
  digitalWrite(RELAY_DOOR_OPEN, LOW);
  digitalWrite(RELAY_DOOR_CLOSE, LOW);
  
  // Light
  pinMode(LIGHT_PIN, OUTPUT);
  digitalWrite(LIGHT_PIN, LOW);
  
  // Ultrasonic Sensor
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  // Buttons (with internal pullup resistors)
  pinMode(BTN_DOOR, INPUT_PULLUP);
  pinMode(BTN_LIGHT, INPUT_PULLUP);
  pinMode(BTN_FEED, INPUT_PULLUP);
  
  Serial.println("✓ Pins initialized");
}

void initializeWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi Connected!");
    Serial.print("  IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("  Django Server: ");
    Serial.print(django_server);
    Serial.print(":");
    Serial.println(django_port);
  } else {
    Serial.println("\n✗ WiFi Connection Failed!");
    Serial.println("  System will operate in offline mode");
  }
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
  unsigned long currentMillis = millis();
  
  // Check manual control buttons
  checkManualButtons();
  
  // Update servo feeding cycle
  updateFeederServo(currentMillis);
  
  // Update door actuator movement
  updateDoorActuator(currentMillis);
  
  // Check ultrasonic sensor (feed level)
  if (currentMillis - last_ultrasonic_check >= ULTRASONIC_CHECK_INTERVAL) {
    last_ultrasonic_check = currentMillis;
    checkFeedLevel();
  }
  
  // Check rain sensor
  if (currentMillis - last_rain_check >= RAIN_CHECK_INTERVAL) {
    last_rain_check = currentMillis;
    checkRainSensor();
  }
  
  // Report feed level to Django server
  if (currentMillis - last_feed_level_report >= REPORT_FEED_LEVEL_INTERVAL) {
    last_feed_level_report = currentMillis;
    reportFeedLevelToDjango();
  }
  
  // Check Django for remote commands from web dashboard
  if (currentMillis - last_django_check >= CHECK_DJANGO_COMMANDS_INTERVAL) {
    last_django_check = currentMillis;
    checkDjangoCommands();
    checkFeedingCommands();
  }
  
  // Small delay to prevent watchdog timer issues
  delay(10);
}

// ============================================
// MANUAL BUTTON CONTROLS
// ============================================
void checkManualButtons() {
  unsigned long currentMillis = millis();
  
  // Debounce all buttons
  if (currentMillis - last_button_press < DEBOUNCE_DELAY) {
    return;
  }
  
  // Manual Feed Button
  if (digitalRead(BTN_FEED) == LOW) {
    Serial.println("[BUTTON] Manual feed triggered");
    dispenseFeed("manual_button");
    last_button_press = currentMillis;
  }
  
  // Manual Door Button (toggle open/close)
  if (digitalRead(BTN_DOOR) == LOW) {
    Serial.println("[BUTTON] Door toggle triggered");
    if (door_state == 0) {
      // Currently stopped, open the door
      openDoor("manual_button");
    } else {
      // Currently moving, stop it
      stopDoor();
    }
    last_button_press = currentMillis;
  }
  
  // Manual Light Button
  if (digitalRead(BTN_LIGHT) == LOW) {
    Serial.println("[BUTTON] Light toggle triggered");
    toggleLight("manual_button");
    last_button_press = currentMillis;
  }
}

// ============================================
// FEEDER CONTROL
// ============================================
void dispenseFeed(String source) {
  if (is_feeding) {
    Serial.println("[FEED] Already feeding, ignoring request");
    return;
  }
  
  Serial.println("[FEED] ⏳ Dispensing feed...");
  
  // Open servo to dispense
  feederServo.write(SERVO_OPEN_ANGLE);
  is_feeding = true;
  feed_start_time = millis();
  
  // Log to Django
  logFeedingEvent(source, current_feed_percentage);
}

void updateFeederServo(unsigned long currentMillis) {
  if (is_feeding && (currentMillis - feed_start_time >= SERVO_DISPENSE_TIME)) {
    // Close servo after dispense time
    feederServo.write(SERVO_CLOSED_ANGLE);
    is_feeding = false;
    Serial.println("[FEED] ✓ Feed dispensed, servo closed");
  }
}

// ============================================
// DOOR ACTUATOR CONTROL
// ============================================
void openDoor(String source) {
  Serial.println("[DOOR] 🚪 Opening door...");
  door_state = 1;  // OPENING
  door_action_start = millis();
  
  digitalWrite(RELAY_DOOR_CLOSE, LOW);  // Stop closing
  digitalWrite(RELAY_DOOR_OPEN, HIGH);  // Start opening
  
  // Log to Django
  logActuatorEvent("door", "open", source);
}

void closeDoor(String source) {
  Serial.println("[DOOR] 🚪 Closing door...");
  door_state = 2;  // CLOSING
  door_action_start = millis();
  
  digitalWrite(RELAY_DOOR_OPEN, LOW);   // Stop opening
  digitalWrite(RELAY_DOOR_CLOSE, HIGH); // Start closing
  
  // Log to Django
  logActuatorEvent("door", "closed", source);
}

void stopDoor() {
  Serial.println("[DOOR] ⏸ Door stopped");
  door_state = 0;  // STOPPED
  
  digitalWrite(RELAY_DOOR_OPEN, LOW);
  digitalWrite(RELAY_DOOR_CLOSE, LOW);
}

void updateDoorActuator(unsigned long currentMillis) {
  // Auto-stop door after full movement time
  if (door_state != 0 && (currentMillis - door_action_start >= DOOR_MOVE_TIME)) {
    Serial.println("[DOOR] ✓ Door movement complete");
    stopDoor();
  }
}

// ============================================
// LIGHT CONTROL
// ============================================
void toggleLight(String source) {
  light_state = !light_state;
  digitalWrite(LIGHT_PIN, light_state ? HIGH : LOW);
  
  Serial.print("[LIGHT] 💡 Light turned ");
  Serial.println(light_state ? "ON" : "OFF");
  
  // Log to Django
  logActuatorEvent("light", light_state ? "on" : "off", source);
}

void setLight(bool state, String source) {
  if (light_state != state) {
    toggleLight(source);
  }
}

// ============================================
// ULTRASONIC SENSOR (Feed Level)
// ============================================
void checkFeedLevel() {
  // Trigger ultrasonic pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  // Read echo duration
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);  // 30ms timeout
  
  if (duration == 0) {
    Serial.println("[ULTRASONIC] ⚠ No echo received");
    return;
  }
  
  // Calculate distance in cm
  current_feed_distance = duration * 0.034 / 2.0;
  
  // Calculate percentage (closer = fuller)
  // 5cm = 100%, 28cm = 0%
  if (current_feed_distance <= FEED_FULL_DISTANCE) {
    current_feed_percentage = 100;
  } else if (current_feed_distance >= FEED_EMPTY_DISTANCE) {
    current_feed_percentage = 0;
  } else {
    current_feed_percentage = map(
      (int)current_feed_distance,
      FEED_FULL_DISTANCE,
      FEED_EMPTY_DISTANCE,
      100,
      0
    );
  }
  
  Serial.print("[FEED LEVEL] Distance: ");
  Serial.print(current_feed_distance);
  Serial.print(" cm | Percentage: ");
  Serial.print(current_feed_percentage);
  Serial.println("%");
}

// ============================================
// RAIN SENSOR
// ============================================
void checkRainSensor() {
  int rain_value = analogRead(RAIN_SENSOR_PIN);
  bool was_raining = is_raining;
  is_raining = (rain_value > RAIN_THRESHOLD);
  
  if (is_raining && !was_raining) {
    Serial.println("[RAIN] 🌧 Rain detected!");
    // Auto-close door when raining
    if (door_state != 2) {  // If not already closing
      closeDoor("rain_sensor");
    }
  } else if (!is_raining && was_raining) {
    Serial.println("[RAIN] ☀ Rain stopped");
  }
}

// ============================================
// DJANGO API COMMUNICATION
// ============================================
void reportFeedLevelToDjango() {
  if (WiFi.status() != WL_CONNECTED) {
    return;  // Skip if WiFi not connected
  }
  
  HTTPClient http;
  http.begin(api_feed_level);
  http.addHeader("Content-Type", "application/json");
  
  // Create JSON payload
  StaticJsonDocument<256> doc;
  doc["feeder_id"] = device_id;
  doc["distance_cm"] = current_feed_distance;
  doc["percentage"] = current_feed_percentage;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  int httpCode = http.POST(jsonString);
  
  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
      Serial.println("[API] ✓ Feed level updated in Django");
    } else {
      Serial.print("[API] ⚠ Response code: ");
      Serial.println(httpCode);
    }
  } else {
    Serial.print("[API] ✗ Error: ");
    Serial.println(http.errorToString(httpCode));
  }
  
  http.end();
}

void logFeedingEvent(String source, int feed_percentage_before) {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  HTTPClient http;
  http.begin(api_feed_log);
  http.addHeader("Content-Type", "application/json");
  
  StaticJsonDocument<512> doc;
  doc["feeder_id"] = device_id;
  doc["amount_grams"] = 100;  // Adjust based on your calibration
  doc["feeding_mode"] = source;
  doc["triggered_by"] = "ESP32";
  doc["success"] = true;
  doc["goat_activity_score"] = 0;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  int httpCode = http.POST(jsonString);
  
  if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
    Serial.println("[API] ✓ Feeding event logged");
  } else {
    Serial.print("[API] ⚠ Log failed: ");
    Serial.println(httpCode);
  }
  
  http.end();
}

void logActuatorEvent(String actuator_type, String action, String source) {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  // Log actuator action (door/light control)
  Serial.print("[API] Logging ");
  Serial.print(actuator_type);
  Serial.print(" action: ");
  Serial.print(action);
  Serial.print(" (source: ");
  Serial.print(source);
  Serial.println(")");
  
  // You can add HTTP POST to Django actuator log endpoint here
  // Similar to logFeedingEvent()
}

// ============================================
// CHECK DJANGO FOR REMOTE COMMANDS
// ============================================
void checkDjangoCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  HTTPClient http;
  
  // Query Django REST API for ALL actuators (this ESP32 controls all of them)
  String url = "http://" + String(django_server) + ":" + String(django_port) + "/iot/api/actuators/";
  http.begin(url);
  http.addHeader("Accept", "application/json");
  
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    
    // Parse JSON response (DRF paginated format)
    DynamicJsonDocument doc(4096);
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      // DRF returns paginated response with "results" array
      JsonArray actuators = doc["results"].as<JsonArray>();
      
      if (actuators.isNull() || actuators.size() == 0) {
        // No actuators configured
        return;
      }
      
      // Process each actuator command (this ESP32 controls all actuators)
      for (JsonObject actuator : actuators) {
        String actuator_type = actuator["actuator_type"].as<String>();
        String current_state = actuator["current_state"].as<String>();
        String mode = actuator["mode"].as<String>();
        
        // Execute commands from Django
        if (actuator_type == "door") {
          if (current_state == "open" && door_state == 0) {
            Serial.println("[DJANGO] ✓ Command: OPEN DOOR");
            openDoor("django_web");
          } else if (current_state == "closed" && door_state != 0) {
            Serial.println("[DJANGO] ✓ Command: CLOSE DOOR");
            closeDoor("django_web");
          }
        } else if (actuator_type == "light") {
          if (current_state == "on" && !light_state) {
            Serial.println("[DJANGO] ✓ Command: TURN ON LIGHT");
            setLight(true, "django_web");
          } else if (current_state == "off" && light_state) {
            Serial.println("[DJANGO] ✓ Command: TURN OFF LIGHT");
            setLight(false, "django_web");
          }
        }
      }
    } else {
      Serial.print("[API] JSON parse error: ");
      Serial.println(error.c_str());
    }
  } else if (httpCode > 0) {
    Serial.print("[API] ⚠ Actuator check HTTP ");
    Serial.println(httpCode);
  } else {
    Serial.print("[API] ✗ Connection error: ");
    Serial.println(http.errorToString(httpCode));
  }
  
  http.end();
}

// Check for feeding commands from Django
void checkFeedingCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  HTTPClient http;
  
  // Query Django for pending feed commands for this device
  String url = "http://" + String(django_server) + ":" + String(django_port) + "/feeding/api/logs/esp32_pending/?feeder_id=" + String(device_id);
  http.begin(url);
  http.addHeader("Accept", "application/json");
  
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    
    // Parse JSON response
    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      bool has_pending = doc["has_pending"].as<bool>();
      
      if (has_pending) {
        JsonArray pending_commands = doc["pending_commands"].as<JsonArray>();
        
        for (JsonObject command : pending_commands) {
          int log_id = command["id"].as<int>();
          int amount = command["amount_dispensed"].as<int>();
          
          Serial.print("[DJANGO] ✓ Feed command received: ");
          Serial.print(amount);
          Serial.println("g");
          
          // Execute feed command
          dispenseFeed("django_web");
          
          // Confirm execution to Django
          confirmFeedExecuted(log_id);
        }
      }
    } else {
      Serial.print("[API] Feed check JSON error: ");
      Serial.println(error.c_str());
    }
  } else if (httpCode > 0) {
    Serial.print("[API] ⚠ Feed check HTTP ");
    Serial.println(httpCode);
  }
  
  http.end();
}

// Confirm feed execution to Django
void confirmFeedExecuted(int log_id) {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  HTTPClient http;
  
  String url = "http://" + String(django_server) + ":" + String(django_port) + "/feeding/api/logs/" + String(log_id) + "/confirm_executed/";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  
  int httpCode = http.POST("{}");
  
  if (httpCode == HTTP_CODE_OK) {
    Serial.println("[API] ✓ Feed execution confirmed");
  } else {
    Serial.print("[API] ⚠ Confirm failed: ");
    Serial.println(httpCode);
  }
  
  http.end();
}
