/*
 * ESP32 IoT KaMoTech System - MQTT + Django Integration
 * 
 * Features:
 * - MQTT Real-time Communication
 * - Automated Feeder (Servo Motor)
 * - Ultrasonic Feed Level Monitoring
 * - DHT21/AM2301 Temperature & Humidity Sensor
 * - Door Actuator Control (Relays)
 * - Light Control (Relay)
 * - Rain Detection
 * - Two-way communication with Django
 * 
 * MQTT Topics:
 * Subscribe (Commands from Django):
 *   - goat_farm/door/control {"action":"open"} or {"action":"close"}
 *   - goat_farm/light/control {"state":"on"} or {"state":"off"}
 *   - goat_farm/feeder/control {"action":"dispense","amount":500}
 * 
 * Publish (Data to Django):
 *   - goat_farm/feed_level {"percentage":75,"distance":10.5}
 *   - goat_farm/temperature {"temperature":25.5,"humidity":65.2}
 *   - goat_farm/door/status {"state":"open","mode":"auto"}
 *   - goat_farm/light/status {"state":"on"}
 *   - goat_farm/rain {"raining":true}
 * 
 * Required Libraries (Install via Arduino Library Manager):
 * - WiFi (ESP32 built-in)
 * - PubSubClient by Nick O'Leary
 * - ESP32Servo by Kevin Harrington
 * - ArduinoJson by Benoit Blanchon
 * - DHT sensor library by Adafruit
 * - Adafruit Unified Sensor
 * 
 * Author: KaMoTech
 * Date: March 2026
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ============================================
// WIFI CONFIGURATION
// ============================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ============================================
// MQTT CONFIGURATION
// ============================================
const char* mqtt_server = "192.168.137.1";  // Your Django server IP (same as MQTT broker)
const int mqtt_port = 1883;
const char* mqtt_username = "";  // If using authentication
const char* mqtt_password = "YOUR_MQTT_PASSWORD";  // If using authentication
const char* device_id = "ESP32_FEEDER_01";

// MQTT Topics
const char* topic_door_control = "goat_farm/door/control";
const char* topic_light_control = "goat_farm/light/control";
const char* topic_feeder_control = "goat_farm/feeder/control";

const char* topic_feed_level = "goat_farm/feed_level";
const char* topic_temperature = "goat_farm/temperature";
const char* topic_door_status = "goat_farm/door/status";
const char* topic_light_status = "goat_farm/light/status";
const char* topic_rain_status = "goat_farm/rain";

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
#define DHT_PIN 14            // DHT21/AM2301 temperature & humidity sensor
#define DHT_TYPE DHT21        // DHT21 (AM2301)
#define RAIN_SENSOR_PIN 32    // Analog input for rain sensor
#define TRIG_PIN 5            // Ultrasonic sensor trigger
#define ECHO_PIN 18           // Ultrasonic sensor echo

// Manual Control Buttons (Optional)
#define BTN_DOOR 15           // Manual door control button
#define BTN_LIGHT 33          // Manual light toggle button
#define BTN_FEED 34           // Manual feed dispense button

// Status LED (Built-in)
#define STATUS_LED 2          // ESP32 built-in LED

// ============================================
// DHT21 SENSOR CONFIGURATION
// ============================================
DHT dht(DHT_PIN, DHT_TYPE);
#define DHT_CHECK_INTERVAL 10000    // Check every 10 seconds
#define DHT_REPORT_INTERVAL 30000   // Report to server every 30 seconds
unsigned long last_dht_check = 0;
unsigned long last_dht_report = 0;
float current_temperature = 0.0;
float current_humidity = 0.0;
bool dht_valid = false;

// ============================================
// SERVO MOTOR CONFIGURATION
// ============================================
Servo feederServo;
#define SERVO_CLOSED_ANGLE 0      // Servo angle when feeder is closed
#define SERVO_OPEN_ANGLE 90       // Servo angle when dispensing feed
#define DEFAULT_DISPENSE_TIME 3000 // Default time to keep servo open (ms)
bool is_feeding = false;
unsigned long feed_start_time = 0;
int current_dispense_time = DEFAULT_DISPENSE_TIME;

// ============================================
// ULTRASONIC SENSOR (Feed Level Monitoring)
// ============================================
#define FEED_CONTAINER_HEIGHT 30    // Total container depth (cm)
#define FEED_FULL_DISTANCE 5        // Distance when full (cm)
#define FEED_EMPTY_DISTANCE 28      // Distance when empty (cm)
#define ULTRASONIC_CHECK_INTERVAL 5000  // Check every 5 seconds
#define FEED_REPORT_INTERVAL 30000  // Report to server every 30 seconds
unsigned long last_ultrasonic_check = 0;
unsigned long last_feed_report = 0;
float current_feed_distance = 0;
int current_feed_percentage = 0;

// ============================================
// RAIN SENSOR
// ============================================
#define RAIN_THRESHOLD 2000         // Analog threshold for rain detection
#define RAIN_CHECK_INTERVAL 10000   // Check every 10 seconds
unsigned long last_rain_check = 0;
bool is_raining = false;
bool rain_status_changed = false;

// ============================================
// DOOR ACTUATOR STATES
// ============================================
enum DoorState {
  DOOR_STOPPED,
  DOOR_OPENING,
  DOOR_CLOSING,
  DOOR_OPEN,
  DOOR_CLOSED
};
DoorState door_state = DOOR_STOPPED;
unsigned long door_operation_start = 0;
#define DOOR_OPERATION_TIME 15000  // Time to fully open/close door (15 seconds)

// ============================================
// LIGHT STATE
// ============================================
bool light_on = false;

// ============================================
// MQTT & WIFI CLIENTS
// ============================================
WiFiClient espClient;
PubSubClient mqtt_client(espClient);

// ============================================
// FUNCTION DECLARATIONS
// ============================================
void setup_wifi();
void mqtt_callback(char* topic, byte* payload, unsigned int length);
void reconnect_mqtt();
void process_door_command(const char* action);
void process_light_command(const char* state);
void process_feeder_command(const char* action, int amount);
float measure_distance();
int calculate_feed_percentage(float distance);
bool check_rain();
void read_dht_sensor();
void update_door_state();
void publish_feed_level();
void publish_temperature();
void publish_door_status();
void publish_light_status();
void publish_rain_status();

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== ESP32 KaMoTech - MQTT System ===");
  
  // Initialize GPIO pins
  pinMode(RELAY_DOOR_OPEN, OUTPUT);
  pinMode(RELAY_DOOR_CLOSE, OUTPUT);
  pinMode(LIGHT_PIN, OUTPUT);
  pinMode(STATUS_LED, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RAIN_SENSOR_PIN, INPUT);
  
  // Initialize outputs to safe state
  digitalWrite(RELAY_DOOR_OPEN, LOW);
  digitalWrite(RELAY_DOOR_CLOSE, LOW);
  digitalWrite(LIGHT_PIN, LOW);
  digitalWrite(STATUS_LED, LOW);
  
  // Initialize servo
  feederServo.attach(SERVO_PIN);
  feederServo.write(SERVO_CLOSED_ANGLE);
  
  // Initialize DHT sensor
  dht.begin();
  Serial.println("DHT21 sensor initialized");
  
  // Connect to WiFi
  setup_wifi();
  
  // Configure MQTT
  mqtt_client.setServer(mqtt_server, mqtt_port);
  mqtt_client.setCallback(mqtt_callback);
  
  Serial.println("Setup complete!");
  digitalWrite(STATUS_LED, HIGH);
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
  // Ensure MQTT connection
  if (!mqtt_client.connected()) {
    reconnect_mqtt();
  }
  mqtt_client.loop();
  
  // Update door state machine
  update_door_state();
  
  // Check and update DHT21 sensor
  if (millis() - last_dht_check >= DHT_CHECK_INTERVAL) {
    last_dht_check = millis();
    read_dht_sensor();
  }
  
  // Report temperature & humidity to server
  if (millis() - last_dht_report >= DHT_REPORT_INTERVAL) {
    last_dht_report = millis();
    if (dht_valid) {
      publish_temperature();
    }
  }
  
  // Check and update feed level
  if (millis() - last_ultrasonic_check >= ULTRASONIC_CHECK_INTERVAL) {
    last_ultrasonic_check = millis();
    current_feed_distance = measure_distance();
    current_feed_percentage = calculate_feed_percentage(current_feed_distance);
    
    Serial.printf("Feed Level: %d%% (Distance: %.1f cm)\n", 
                  current_feed_percentage, current_feed_distance);
  }
  
  // Report feed level to server
  if (millis() - last_feed_report >= FEED_REPORT_INTERVAL) {
    last_feed_report = millis();
    publish_feed_level();
  }
  
  // Check rain sensor
  if (millis() - last_rain_check >= RAIN_CHECK_INTERVAL) {
    last_rain_check = millis();
    bool new_rain_status = check_rain();
    
    if (new_rain_status != is_raining) {
      is_raining = new_rain_status;
      rain_status_changed = true;
      publish_rain_status();
      
      // Auto-close door if raining
      if (is_raining && door_state != DOOR_CLOSING && door_state != DOOR_CLOSED) {
        Serial.println("Rain detected! Auto-closing door...");
        process_door_command("close");
      }
    }
  }
  
  // Handle feeding timer
  if (is_feeding && (millis() - feed_start_time >= current_dispense_time)) {
    is_feeding = false;
    feederServo.write(SERVO_CLOSED_ANGLE);
    Serial.println("Feeding complete - Servo closed");
  }
  
  delay(50);  // Small delay for stability
}

// ============================================
// WIFI SETUP
// ============================================
void setup_wifi() {
  delay(10);
  Serial.println("\nConnecting to WiFi...");
  Serial.print("SSID: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));  // Blink LED
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(STATUS_LED, HIGH);
  } else {
    Serial.println("\n✗ WiFi Connection Failed!");
    digitalWrite(STATUS_LED, LOW);
  }
}

// ============================================
// MQTT CALLBACK (Receive Commands)
// ============================================
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message received [");
  Serial.print(topic);
  Serial.print("]: ");
  
  // Convert payload to string
  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.println(message);
  
  // Parse JSON
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.print("JSON parse error: ");
    Serial.println(error.c_str());
    return;
  }
  
  // Route to appropriate handler
  if (strcmp(topic, topic_door_control) == 0) {
    const char* action = doc["action"];
    process_door_command(action);
  }
  else if (strcmp(topic, topic_light_control) == 0) {
    const char* state = doc["state"];
    process_light_command(state);
  }
  else if (strcmp(topic, topic_feeder_control) == 0) {
    const char* action = doc["action"];
    int amount = doc["amount"] | DEFAULT_DISPENSE_TIME;  // Default if not provided
    process_feeder_command(action, amount);
  }
}

// ============================================
// MQTT RECONNECT
// ============================================
void reconnect_mqtt() {
  while (!mqtt_client.connected()) {
    Serial.print("Attempting MQTT connection...");
    
    // Attempt to connect
    bool connected;
    if (strlen(mqtt_username) > 0) {
      connected = mqtt_client.connect(device_id, mqtt_username, mqtt_password);
    } else {
      connected = mqtt_client.connect(device_id);
    }
    
    if (connected) {
      Serial.println("✓ MQTT Connected!");
      
      // Subscribe to control topics
      mqtt_client.subscribe(topic_door_control);
      mqtt_client.subscribe(topic_light_control);
      mqtt_client.subscribe(topic_feeder_control);
      
      Serial.println("Subscribed to control topics");
      
      // Publish initial status
      publish_door_status();
      publish_light_status();
      publish_feed_level();
    } else {
      Serial.print("✗ Failed, rc=");
      Serial.print(mqtt_client.state());
      Serial.println(" retrying in 5 seconds...");
      delay(5000);
    }
  }
}

// ============================================
// DOOR CONTROL
// ============================================
void process_door_command(const char* action) {
  Serial.print("Door command: ");
  Serial.println(action);
  
  if (strcmp(action, "open") == 0) {
    // Start opening door
    digitalWrite(RELAY_DOOR_CLOSE, LOW);  // Stop closing
    digitalWrite(RELAY_DOOR_OPEN, HIGH);  // Start opening
    door_state = DOOR_OPENING;
    door_operation_start = millis();
    Serial.println("→ Opening door...");
  }
  else if (strcmp(action, "close") == 0) {
    // Start closing door
    digitalWrite(RELAY_DOOR_OPEN, LOW);   // Stop opening
    digitalWrite(RELAY_DOOR_CLOSE, HIGH); // Start closing
    door_state = DOOR_CLOSING;
    door_operation_start = millis();
    Serial.println("→ Closing door...");
  }
  else if (strcmp(action, "stop") == 0) {
    // Stop door
    digitalWrite(RELAY_DOOR_OPEN, LOW);
    digitalWrite(RELAY_DOOR_CLOSE, LOW);
    door_state = DOOR_STOPPED;
    Serial.println("→ Door stopped");
  }
  
  publish_door_status();
}

// ============================================
// DOOR STATE MACHINE
// ============================================
void update_door_state() {
  if (door_state == DOOR_OPENING || door_state == DOOR_CLOSING) {
    // Check if operation time completed
    if (millis() - door_operation_start >= DOOR_OPERATION_TIME) {
      // Stop relays
      digitalWrite(RELAY_DOOR_OPEN, LOW);
      digitalWrite(RELAY_DOOR_CLOSE, LOW);
      
      // Update state
      if (door_state == DOOR_OPENING) {
        door_state = DOOR_OPEN;
        Serial.println("✓ Door fully opened");
      } else {
        door_state = DOOR_CLOSED;
        Serial.println("✓ Door fully closed");
      }
      
      publish_door_status();
    }
  }
}

// ============================================
// LIGHT CONTROL
// ============================================
void process_light_command(const char* state) {
  Serial.print("Light command: ");
  Serial.println(state);
  
  if (strcmp(state, "on") == 0) {
    digitalWrite(LIGHT_PIN, HIGH);
    light_on = true;
    Serial.println("→ Light ON");
  }
  else if (strcmp(state, "off") == 0) {
    digitalWrite(LIGHT_PIN, LOW);
    light_on = false;
    Serial.println("→ Light OFF");
  }
  
  publish_light_status();
}

// ============================================
// FEEDER CONTROL
// ============================================
void process_feeder_command(const char* action, int amount) {
  Serial.print("Feeder command: ");
  Serial.print(action);
  Serial.print(" Amount: ");
  Serial.println(amount);
  
  if (strcmp(action, "dispense") == 0) {
    if (!is_feeding) {
      is_feeding = true;
      current_dispense_time = amount;
      feed_start_time = millis();
      feederServo.write(SERVO_OPEN_ANGLE);
      Serial.println("→ Dispensing feed...");
      
      // Publish feeding status
      StaticJsonDocument<100> doc;
      doc["feeding"] = true;
      doc["amount"] = amount;
      char buffer[100];
      serializeJson(doc, buffer);
      mqtt_client.publish("goat_farm/feeder/status", buffer);
    } else {
      Serial.println("Already feeding!");
    }
  }
}

// ============================================
// ULTRASONIC DISTANCE MEASUREMENT
// ============================================
float measure_distance() {
  // Clear trigger
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  
  // Send pulse
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  // Read echo
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);  // 30ms timeout
  
  if (duration == 0) {
    Serial.println("Ultrasonic timeout - no echo received");
    return current_feed_distance;  // Return last valid reading
  }
  
  // Calculate distance (speed of sound = 343 m/s)
  float distance = duration * 0.0343 / 2;
  
  // Validate reading
  if (distance < 2 || distance > 400) {
    Serial.println("Invalid distance reading");
    return current_feed_distance;
  }
  
  return distance;
}

// ============================================
// CALCULATE FEED PERCENTAGE
// ============================================
int calculate_feed_percentage(float distance) {
  if (distance <= FEED_FULL_DISTANCE) {
    return 100;  // Full
  } else if (distance >= FEED_EMPTY_DISTANCE) {
    return 0;    // Empty
  }
  
  // Linear interpolation
  float percentage = 100.0 * (FEED_EMPTY_DISTANCE - distance) / 
                     (FEED_EMPTY_DISTANCE - FEED_FULL_DISTANCE);
  return constrain((int)percentage, 0, 100);
}

// ============================================
// READ DHT21 SENSOR
// ============================================
void read_dht_sensor() {
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();  // Celsius
  
  // Check if readings are valid
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Failed to read from DHT sensor!");
    dht_valid = false;
    return;
  }
  
  // Store valid readings
  current_humidity = humidity;
  current_temperature = temperature;
  dht_valid = true;
  
  Serial.printf("Temperature: %.1f°C | Humidity: %.1f%%\n", 
                current_temperature, current_humidity);
  
  // Check for extreme conditions
  if (current_temperature > 35.0) {
    Serial.println("⚠️ WARNING: High temperature detected!");
  }
  if (current_temperature < 10.0) {
    Serial.println("⚠️ WARNING: Low temperature detected!");
  }
  if (current_humidity > 80.0) {
    Serial.println("⚠️ WARNING: High humidity detected!");
  }
}

// ============================================
// RAIN DETECTION
// ============================================
bool check_rain() {
  int rain_value = analogRead(RAIN_SENSOR_PIN);
  return (rain_value < RAIN_THRESHOLD);  // Lower value = more moisture
}

// ============================================
// PUBLISH FEED LEVEL
// ============================================
void publish_feed_level() {
  StaticJsonDocument<100> doc;
  doc["percentage"] = current_feed_percentage;
  doc["distance_cm"] = current_feed_distance;
  doc["device_id"] = device_id;
  
  char buffer[100];
  serializeJson(doc, buffer);
  mqtt_client.publish(topic_feed_level, buffer);
  
  Serial.print("Published feed level: ");
  Serial.println(buffer);
}

// ============================================
// PUBLISH TEMPERATURE & HUMIDITY
// ============================================
void publish_temperature() {
  StaticJsonDocument<150> doc;
  doc["temperature"] = round(current_temperature * 10) / 10.0;  // Round to 1 decimal
  doc["humidity"] = round(current_humidity * 10) / 10.0;
  doc["device_id"] = device_id;
  doc["timestamp"] = millis() / 1000;  // Seconds since boot
  
  char buffer[150];
  serializeJson(doc, buffer);
  mqtt_client.publish(topic_temperature, buffer);
  
  Serial.print("Published temperature: ");
  Serial.println(buffer);
}

// ============================================
// PUBLISH DOOR STATUS
// ============================================
void publish_door_status() {
  StaticJsonDocument<100> doc;
  
  switch(door_state) {
    case DOOR_OPEN:
      doc["state"] = "open";
      break;
    case DOOR_CLOSED:
      doc["state"] = "closed";
      break;
    case DOOR_OPENING:
      doc["state"] = "opening";
      break;
    case DOOR_CLOSING:
      doc["state"] = "closing";
      break;
    default:
      doc["state"] = "stopped";
  }
  
  doc["device_id"] = device_id;
  
  char buffer[100];
  serializeJson(doc, buffer);
  mqtt_client.publish(topic_door_status, buffer);
  
  Serial.print("Published door status: ");
  Serial.println(buffer);
}

// ============================================
// PUBLISH LIGHT STATUS
// ============================================
void publish_light_status() {
  StaticJsonDocument<100> doc;
  doc["state"] = light_on ? "on" : "off";
  doc["device_id"] = device_id;
  
  char buffer[100];
  serializeJson(doc, buffer);
  mqtt_client.publish(topic_light_status, buffer);
  
  Serial.print("Published light status: ");
  Serial.println(buffer);
}

// ============================================
// PUBLISH RAIN STATUS
// ============================================
void publish_rain_status() {
  StaticJsonDocument<100> doc;
  doc["raining"] = is_raining;
  doc["device_id"] = device_id;
  
  char buffer[100];
  serializeJson(doc, buffer);
  mqtt_client.publish(topic_rain_status, buffer);
  
  Serial.print("Published rain status: ");
  Serial.println(buffer);
}
