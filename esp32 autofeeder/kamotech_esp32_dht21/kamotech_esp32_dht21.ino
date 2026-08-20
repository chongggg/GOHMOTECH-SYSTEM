/*
 * ═══════════════════════════════════════════════════════════════════
 * KAMOTECH ESP32 - DHT21 Temperature & Humidity Monitor
 * ═══════════════════════════════════════════════════════════════════
 * 
 * This code reads DHT21 sensor data and sends it to Django server
 * Device Name: kamotech esp32
 * 
 * Features:
 * - Reads DHT21 temperature and humidity
 * - Sends data to Django via HTTP POST
 * - Auto-reconnects to WiFi if connection lost
 * - Visual LED status indicators
 * - Serial monitoring for debugging
 * 
 * ═══════════════════════════════════════════════════════════════════
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ═══════════════════════════════════════════════════════════════════
// CONFIGURATION - CHANGE THESE TO MATCH YOUR SETUP
// ═══════════════════════════════════════════════════════════════════

// WiFi Credentials
const char* ssid = "YOUR_WIFI_SSID";        // Your WiFi network
const char* password = "YOUR_WIFI_PASSWORD";           // Your WiFi password

// Django Server Configuration  
// ⚠️  IMPORTANT: Use your WiFi IP address (from ipconfig)
const char* serverUrl = "http://10.135.113.155:8000/iot/api/sensor-readings/";
// Your computer's WiFi IP: 10.135.113.155

// Device Configuration
const char* deviceId = "kamotech_esp32_001";
const char* deviceName = "kamotech esp32";

// DHT21 Sensor Configuration
#define DHT_PIN 14           // GPIO 14 (Yellow wire from DHT21)
#define DHT_TYPE DHT21       // DHT21 (AM2301)

// LED Status Indicator
#define STATUS_LED 2         // Built-in LED on most ESP32 boards

// Timing Configuration (in milliseconds)
#define SENSOR_READ_INTERVAL 10000   // Read sensor every 10 seconds
#define SEND_DATA_INTERVAL 30000     // Send data to server every 30 seconds
#define WIFI_RETRY_DELAY 5000        // Wait 5 seconds before WiFi reconnect

// ═══════════════════════════════════════════════════════════════════
// GLOBAL OBJECTS & VARIABLES
// ═══════════════════════════════════════════════════════════════════

DHT dht(DHT_PIN, DHT_TYPE);
HTTPClient http;

// Sensor data storage
float currentTemperature = 0.0;
float currentHumidity = 0.0;
bool sensorDataValid = false;

// Timing variables
unsigned long lastSensorRead = 0;
unsigned long lastDataSend = 0;
unsigned long lastWifiCheck = 0;

// Status tracking
int consecutiveFailures = 0;
bool ledState = false;

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("╔════════════════════════════════════════════════════════╗");
  Serial.println("║      KAMOTECH ESP32 - DHT21 MONITORING SYSTEM         ║");
  Serial.println("╚════════════════════════════════════════════════════════╝");
  Serial.println();
  
  // Initialize LED
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);
  
  // Initialize DHT sensor
  Serial.println("🌡️  Initializing DHT21 sensor...");
  dht.begin();
  delay(2000);  // DHT sensor needs time to stabilize
  Serial.println("✓ DHT21 initialized");
  
  // Connect to WiFi
  connectWiFi();
  
  // Print configuration
  printConfiguration();
  
  Serial.println("\n✓ System ready! Starting monitoring...\n");
  Serial.println("─────────────────────────────────────────────────────────");
}

// ═══════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════

void loop() {
  unsigned long currentMillis = millis();
  
  // Check WiFi connection every 30 seconds
  if (currentMillis - lastWifiCheck >= 30000) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("\n⚠️  WiFi connection lost! Reconnecting...");
      connectWiFi();
    }
    lastWifiCheck = currentMillis;
  }
  
  // Read sensor data
  if (currentMillis - lastSensorRead >= SENSOR_READ_INTERVAL) {
    readSensorData();
    lastSensorRead = currentMillis;
  }
  
  // Send data to server
  if (currentMillis - lastDataSend >= SEND_DATA_INTERVAL) {
    if (sensorDataValid) {
      sendDataToServer();
    } else {
      Serial.println("⚠️  No valid sensor data to send");
    }
    lastDataSend = currentMillis;
  }
  
  // Blink LED to show system is alive
  if (currentMillis % 2000 < 100) {
    digitalWrite(STATUS_LED, HIGH);
  } else {
    digitalWrite(STATUS_LED, LOW);
  }
  
  delay(100);  // Small delay to prevent watchdog timer issues
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
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));  // Blink LED during connection
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED, HIGH);  // Solid LED when connected
    Serial.println("\n✓ WiFi Connected!");
    Serial.print("   IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("   Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    digitalWrite(STATUS_LED, LOW);
    Serial.println("\n✗ WiFi Connection Failed!");
    Serial.println("   Will retry in 5 seconds...");
    delay(WIFI_RETRY_DELAY);
  }
}

// ═══════════════════════════════════════════════════════════════════
// SENSOR DATA READING
// ═══════════════════════════════════════════════════════════════════

void readSensorData() {
  Serial.println("\n📊 Reading DHT21 sensor...");
  
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  
  // Check if readings are valid
  if (isnan(temp) || isnan(hum)) {
    Serial.println("✗ Failed to read from DHT21 sensor!");
    Serial.println("  Check wiring:");
    Serial.println("  - RED wire → 5V");
    Serial.println("  - YELLOW wire → GPIO 14");
    Serial.println("  - BLACK wire → GND");
    sensorDataValid = false;
    consecutiveFailures++;
    
    if (consecutiveFailures >= 5) {
      Serial.println("\n⚠️  WARNING: 5+ consecutive sensor failures!");
      Serial.println("  Possible issues:");
      Serial.println("  - Loose wiring");
      Serial.println("  - Faulty sensor");
      Serial.println("  - Power supply problem");
    }
    return;
  }
  
  // Valid reading
  currentTemperature = temp;
  currentHumidity = hum;
  sensorDataValid = true;
  consecutiveFailures = 0;
  
  // Print readings
  Serial.println("✓ Sensor data read successfully:");
  Serial.println("  ┌────────────────────────────┐");
  Serial.print("  │ Temperature: ");
  Serial.print(currentTemperature, 1);
  Serial.println(" °C       │");
  Serial.print("  │ Humidity:    ");
  Serial.print(currentHumidity, 1);
  Serial.println(" %        │");
  Serial.println("  └────────────────────────────┘");
  
  // Temperature warnings
  if (currentTemperature > 35.0) {
    Serial.println("  ⚠️  High temperature warning!");
  } else if (currentTemperature < 10.0) {
    Serial.println("  ⚠️  Low temperature warning!");
  }
  
  // Humidity warnings
  if (currentHumidity > 80.0) {
    Serial.println("  ⚠️  High humidity warning!");
  } else if (currentHumidity < 30.0) {
    Serial.println("  ⚠️  Low humidity warning!");
  }
}

// ═══════════════════════════════════════════════════════════════════
// SEND DATA TO DJANGO SERVER
// ═══════════════════════════════════════════════════════════════════

void sendDataToServer() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("✗ Cannot send data - WiFi not connected");
    return;
  }
  
  Serial.println("\n📤 Sending data to Django server...");
  
  // Create JSON payload
  StaticJsonDocument<512> doc;
  doc["device_id"] = deviceId;
  doc["device_name"] = deviceName;
  doc["temperature"] = currentTemperature;
  doc["humidity"] = currentHumidity;
  doc["timestamp"] = millis() / 1000;  // Unix timestamp in seconds
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  Serial.println("  JSON Payload:");
  Serial.print("  ");
  Serial.println(jsonString);
  
  // Send HTTP POST request
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  
  int httpResponseCode = http.POST(jsonString);
  
  // Handle response
  if (httpResponseCode > 0) {
    Serial.print("  ✓ Server response code: ");
    Serial.println(httpResponseCode);
    
    if (httpResponseCode == 200 || httpResponseCode == 201) {
      Serial.println("  ✓ Data sent successfully!");
      
      String response = http.getString();
      if (response.length() > 0 && response.length() < 500) {
        Serial.println("  Server response:");
        Serial.print("  ");
        Serial.println(response);
      }
      
      // Flash LED to indicate successful send
      for (int i = 0; i < 3; i++) {
        digitalWrite(STATUS_LED, LOW);
        delay(100);
        digitalWrite(STATUS_LED, HIGH);
        delay(100);
      }
    } else {
      Serial.print("  ✗ Server returned error: ");
      Serial.println(httpResponseCode);
      String response = http.getString();
      if (response.length() > 0) {
        Serial.println("  Error details:");
        Serial.print("  ");
        Serial.println(response);
      }
    }
  } else {
    Serial.print("  ✗ HTTP request failed: ");
    Serial.println(http.errorToString(httpResponseCode));
    Serial.println("  Possible causes:");
    Serial.println("  - Django server not running");
    Serial.println("  - Incorrect server URL");
    Serial.println("  - Firewall blocking connection");
    Serial.println("  - Network issue");
  }
  
  http.end();
}

// ═══════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

void printConfiguration() {
  Serial.println("\n📋 Configuration:");
  Serial.println("  ┌────────────────────────────────────────────┐");
  Serial.print("  │ Device ID:   ");
  Serial.print(deviceId);
  for (int i = strlen(deviceId); i < 29; i++) Serial.print(" ");
  Serial.println("│");
  Serial.print("  │ Device Name: ");
  Serial.print(deviceName);
  for (int i = strlen(deviceName); i < 29; i++) Serial.print(" ");
  Serial.println("│");
  Serial.print("  │ DHT Pin:     GPIO ");
  Serial.print(DHT_PIN);
  Serial.println("                        │");
  Serial.print("  │ Server URL:  ");
  Serial.println(serverUrl);
  Serial.println("  │                                            │");
  Serial.print("  │ Read Interval:  ");
  Serial.print(SENSOR_READ_INTERVAL / 1000);
  Serial.println(" seconds              │");
  Serial.print("  │ Send Interval:  ");
  Serial.print(SEND_DATA_INTERVAL / 1000);
  Serial.println(" seconds              │");
  Serial.println("  └────────────────────────────────────────────┘");
}

// ═══════════════════════════════════════════════════════════════════
// END OF CODE
// ═══════════════════════════════════════════════════════════════════
