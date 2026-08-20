#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ============================================
// WIFI CONFIGURATION
// ============================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ============================================
// HTTP SERVER CONFIGURATION (mysql_logger.py)
// ============================================
const char* logger_server = "http://192.168.137.1:8080/log";  // Update with your PC's IP
const int device_id = 1;  // Device ID for this ESP32

// ============================================
// PIN DEFINITIONS
// ============================================
#define RELAY_OPEN 26
#define RELAY_CLOSE 27

#define BTN_ACTUATOR 15   // button for actuator control (GPIO 34 is input-only, changed to 15)
#define BTN_LIGHT 32      // button for light toggle
#define BTN_SERVO 33      // button for servo control (changed from 35)

#define LIGHT_PIN 13
#define SERVO_PIN 25      // servo motor control (PWM-capable pin)

// Servo object
Servo myServo;

// WiFi status
bool wifi_connected = false;

// actuator states
int actuatorState = 0;
/*
0 = STOP
1 = EXTEND
2 = RETRACT
*/

// servo feeding cycle
bool isFeeding = false;
unsigned long feedStartTime = 0;
const unsigned long feedDuration = 3000; // 3 seconds

bool lastActBtn = HIGH;
bool lastLightBtn = HIGH;
bool lastServoBtn = HIGH;

bool lightState = false;

unsigned long lastPressTime = 0;
const int debounceDelay = 200;

// ============================================
// FUNCTION DECLARATIONS
// ============================================
void initializeWiFi();
void logEventViaHTTP(String eventType, int sensorValue);

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n\n=== ESP32 Autofeeder Starting ===");
  
  pinMode(RELAY_OPEN, OUTPUT);
  pinMode(RELAY_CLOSE, OUTPUT);
  pinMode(LIGHT_PIN, OUTPUT);

  pinMode(BTN_ACTUATOR, INPUT_PULLUP);
  pinMode(BTN_LIGHT, INPUT_PULLUP);
  pinMode(BTN_SERVO, INPUT_PULLUP);  // GPIO 33 supports internal pullup

  digitalWrite(RELAY_OPEN, LOW);
  digitalWrite(RELAY_CLOSE, LOW);
  digitalWrite(LIGHT_PIN, LOW);

  // Initialize servo to closed position then detach to save power
  myServo.attach(SERVO_PIN);
  myServo.write(0);  // Start at 0 degrees
  delay(500);  // Give servo time to move
  myServo.detach();  // Detach to reduce power consumption

  // Initialize WiFi
  initializeWiFi();
  
  Serial.println("=== System Ready ===\n");
}

void loop() {

  bool actBtn = digitalRead(BTN_ACTUATOR);
  bool lightBtn = digitalRead(BTN_LIGHT);
  bool servoBtn = digitalRead(BTN_SERVO);

  if (millis() - lastPressTime > debounceDelay) {

    // ===== ACTUATOR BUTTON =====
    if (lastActBtn == HIGH && actBtn == LOW) {
      lastPressTime = millis();

      actuatorState++;

      if (actuatorState > 2) actuatorState = 0;

      if (actuatorState == 1) {
        Serial.println("EXTENDING");
        logEventViaHTTP("ACTUATOR_EXTEND", actuatorState);
      }
      if (actuatorState == 2) {
        Serial.println("RETRACTING");
        logEventViaHTTP("ACTUATOR_RETRACT", actuatorState);
      }
      if (actuatorState == 0) {
        Serial.println("STOP");
        logEventViaHTTP("ACTUATOR_STOP", actuatorState);
      }
    }

    // ===== LIGHT BUTTON =====
    if (lastLightBtn == HIGH && lightBtn == LOW) {
      lastPressTime = millis();

      lightState = !lightState;
      digitalWrite(LIGHT_PIN, lightState);

      if (lightState) {
        Serial.println("LIGHT ON");
        logEventViaHTTP("LIGHT_ON", 1);
      }
      else {
        Serial.println("LIGHT OFF");
        logEventViaHTTP("LIGHT_OFF", 0);
      }
    }

    // ===== SERVO BUTTON (Start Feeding Cycle) =====
    if (lastServoBtn == HIGH && servoBtn == LOW && !isFeeding) {
      lastPressTime = millis();
      
      // Start feeding cycle
      isFeeding = true;
      feedStartTime = millis();
      myServo.attach(SERVO_PIN);  // Attach servo before use
      delay(10);
      myServo.write(180);  // Open to 180°
      Serial.println("FEEDING: Started - Servo at 180°");
      logEventViaHTTP("FEEDING_START", 180);
    }
  }

  lastActBtn = actBtn;
  lastLightBtn = lightBtn;
  lastServoBtn = servoBtn;

  // ===== SERVO FEEDING CYCLE CONTROL =====
  if (isFeeding) {
    if (millis() - feedStartTime >= feedDuration) {
      // 3 seconds elapsed, return to closed position
      myServo.write(0);
      delay(500);  // Give servo time to move to 0°
      myServo.detach();  // Detach to save power
      isFeeding = false;
      Serial.println("FEEDING: Complete - Servo returned to 0°");
      logEventViaHTTP("FEEDING_COMPLETE", 0);
    }
  }

  // ===== ACTUATOR CONTROL =====
  if (actuatorState == 1) {           // EXTEND
    digitalWrite(RELAY_OPEN, HIGH);
    digitalWrite(RELAY_CLOSE, LOW);
  }
  else if (actuatorState == 2) {      // RETRACT
    digitalWrite(RELAY_OPEN, LOW);
    digitalWrite(RELAY_CLOSE, HIGH);
  }
  else {                              // STOP
    digitalWrite(RELAY_OPEN, LOW);
    digitalWrite(RELAY_CLOSE, LOW);
  }
}

// ============================================
// WIFI FUNCTIONS
// ============================================
void initializeWiFi() {
  Serial.println("[WiFi] Connecting to WiFi...");
  Serial.print("[WiFi] SSID: ");
  Serial.println(ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifi_connected = true;
    Serial.println("\n[WiFi] Connected!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Logger Server: ");
    Serial.println(logger_server);
  } else {
    wifi_connected = false;
    Serial.println("\n[WiFi] Connection failed!");
    Serial.println("[WiFi] System will work offline (no database logging)");
  }
}

// ============================================
// HTTP LOGGING FUNCTIONS
// ============================================
void logEventViaHTTP(String eventType, int sensorValue) {
  if (!wifi_connected) {
    return;
  }

  HTTPClient http;
  http.begin(logger_server);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  
  // Build POST data
  String postData = "event_type=" + eventType + 
                    "&sensor_value=" + String(sensorValue) + 
                    "&device_id=" + String(device_id);
  
  Serial.print("[HTTP] Logging: ");
  Serial.print(eventType);
  Serial.print(" = ");
  Serial.print(sensorValue);
  
  int httpResponseCode = http.POST(postData);
  
  if (httpResponseCode > 0) {
    Serial.print(" → ");
    Serial.print(httpResponseCode);
    Serial.println(" OK");
  } else {
    Serial.print(" → ERROR: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  http.end();
}
