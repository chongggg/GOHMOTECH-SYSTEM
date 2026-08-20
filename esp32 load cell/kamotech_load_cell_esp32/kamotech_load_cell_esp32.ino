/*
 * GoHMoTech - Dedicated Goat Weighing Platform ESP32
 *
 * Hardware:
 *   HX711 DOUT -> GPIO 19
 *   HX711 SCK  -> GPIO 18
 *   Status LED -> GPIO 2 (built-in on common ESP32 boards)
 *
 * This controller never chooses a goat and never saves weight history.
 * It only uploads the latest transient scale state to Django. The farmer
 * selects a goat in Goat Inventory and explicitly presses Save Weight.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <HX711_ADC.h>

// Reused from kamotech_esp32_complete.ino.
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
// Windows Mobile Hotspot/Internet Connection Sharing gateway used by
// green_house_IoT. The Django server must run on 0.0.0.0:8000.
const char* scaleReadingUrl = "http://192.168.137.1:8000/iot/api/scale/readings/";

// This must be unique because the scale is a separate physical ESP32.
const char* deviceId = "kamotech_scale_esp32_001";
const char* deviceName = "GoHMoTech Goat Scale ESP32";

#define HX711_DOUT_PIN 19
#define HX711_SCK_PIN 18
#define STATUS_LED 2

// CALIBRATION:
// 1. Run the HX711_ADC Calibration example with the completed four-cell platform.
// 2. Use a verified known mass.
// 3. Replace this placeholder with the resulting calibration factor.
const float HX711_CALIBRATION_FACTOR = 696.0f;

// Adjust these only after observing the completed platform under real conditions.
const float SCALE_ZERO_DEADBAND_KG = 0.10f;
const float SCALE_WEIGHT_DETECTED_KG = 0.50f;
const float SCALE_STABILITY_TOLERANCE_KG = 0.15f;
const int SCALE_STABILITY_SAMPLE_COUNT = 10;
const unsigned long SCALE_STABILIZING_TIME_MS = 3000;
const unsigned long SCALE_SEND_INTERVAL_MS = 1000;
const unsigned long SCALE_RETRY_INTERVAL_MS = 5000;
const unsigned long WIFI_RECONNECT_INTERVAL_MS = 10000;

HX711_ADC loadCell(HX711_DOUT_PIN, HX711_SCK_PIN);
HTTPClient http;

float currentWeightKg = 0.0f;
float variationKg = 0.0f;
float stabilitySamples[SCALE_STABILITY_SAMPLE_COUNT];
int stabilitySampleCount = 0;
int stabilitySampleIndex = 0;

bool hx711Ready = false;
bool hx711Initialized = false;
bool readingValid = false;
bool weightDetected = false;
bool weightStable = false;
bool scaleTimeoutReported = false;

unsigned long lastScaleSend = 0;
unsigned long currentSendInterval = SCALE_SEND_INTERVAL_MS;
unsigned long lastWiFiReconnectAttempt = 0;
unsigned long lastScaleSample = 0;
unsigned long lastSerialStatus = 0;


void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("====================================================");
  Serial.println(" GoHMoTech - Dedicated Goat Scale ESP32");
  Serial.println("====================================================");

  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);

  connectWiFi();
  // Initialize/tare only after the blocking initial WiFi connection attempt.
  // This lets HX711_ADC.update() run continuously immediately after startup.
  initializeScale();
  printConfiguration();
}


void loop() {
  unsigned long currentMillis = millis();

  // HX711_ADC update() must be called frequently for continuous conversions.
  updateScaleReading();

  if (WiFi.status() != WL_CONNECTED &&
      currentMillis - lastWiFiReconnectAttempt >= WIFI_RECONNECT_INTERVAL_MS) {
    lastWiFiReconnectAttempt = currentMillis;
    requestWiFiReconnect();
  }

  if (currentMillis - lastScaleSend >= currentSendInterval) {
    sendScaleSnapshot();
    lastScaleSend = currentMillis;
  }

  if (currentMillis - lastSerialStatus >= 500) {
    printScaleStatus();
    lastSerialStatus = currentMillis;
  }

  digitalWrite(STATUS_LED, WiFi.status() == WL_CONNECTED ? HIGH : LOW);
  delay(5);
}


void initializeScale() {
  Serial.println("Initializing HX711...");
  Serial.println("Keep the weighing platform completely empty during startup tare.");

  loadCell.begin();
  loadCell.start(SCALE_STABILIZING_TIME_MS, true);

  if (loadCell.getTareTimeoutFlag() || loadCell.getSignalTimeoutFlag()) {
    hx711Ready = false;
    hx711Initialized = false;
    readingValid = false;
    Serial.println("HX711 initialization/tare timed out.");
    Serial.println("Check wiring and restart with the platform empty.");
    return;
  }

  loadCell.setCalFactor(HX711_CALIBRATION_FACTOR);
  hx711Initialized = true;
  hx711Ready = true;
  lastScaleSample = millis();
  Serial.print("HX711 ready. Calibration factor: ");
  Serial.println(HX711_CALIBRATION_FACTOR, 3);
}


void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED, HIGH);
    Serial.println();
    Serial.println("WiFi connected.");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    digitalWrite(STATUS_LED, LOW);
    Serial.println();
    Serial.println("WiFi connection failed. Manual weight entry remains available.");
  }
}


void requestWiFiReconnect() {
  Serial.println("WiFi disconnected. Starting a non-blocking reconnect...");
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
}


void resetStabilityWindow() {
  stabilitySampleCount = 0;
  stabilitySampleIndex = 0;
  variationKg = 0.0f;
  weightStable = false;
}


void updateScaleReading() {
  if (!hx711Initialized) {
    readingValid = false;
    weightDetected = false;
    weightStable = false;
    return;
  }

  if (!loadCell.update()) {
    // Network operations can occasionally delay update(). Treat missing samples
    // as temporary and keep polling so the scale can recover automatically.
    if (millis() - lastScaleSample > 2000) {
      hx711Ready = false;
      readingValid = false;
      weightDetected = false;
      resetStabilityWindow();
      if (!scaleTimeoutReported) {
        Serial.println("No HX711 samples for 2 seconds. Retrying automatically...");
        scaleTimeoutReported = true;
      }
    }
    return;
  }

  lastScaleSample = millis();
  hx711Ready = true;
  scaleTimeoutReported = false;

  float readingKg = loadCell.getData();
  if (!isfinite(readingKg)) {
    readingValid = false;
    weightDetected = false;
    resetStabilityWindow();
    return;
  }

  if (fabs(readingKg) <= SCALE_ZERO_DEADBAND_KG) {
    readingKg = 0.0f;
  }

  currentWeightKg = max(0.0f, readingKg);
  readingValid = true;
  weightDetected = currentWeightKg >= SCALE_WEIGHT_DETECTED_KG;

  if (!weightDetected) {
    resetStabilityWindow();
    return;
  }

  stabilitySamples[stabilitySampleIndex] = currentWeightKg;
  stabilitySampleIndex = (stabilitySampleIndex + 1) % SCALE_STABILITY_SAMPLE_COUNT;
  if (stabilitySampleCount < SCALE_STABILITY_SAMPLE_COUNT) {
    stabilitySampleCount++;
  }

  if (stabilitySampleCount < SCALE_STABILITY_SAMPLE_COUNT) {
    weightStable = false;
    return;
  }

  float minimumWeight = stabilitySamples[0];
  float maximumWeight = stabilitySamples[0];
  for (int index = 1; index < SCALE_STABILITY_SAMPLE_COUNT; index++) {
    minimumWeight = min(minimumWeight, stabilitySamples[index]);
    maximumWeight = max(maximumWeight, stabilitySamples[index]);
  }

  variationKg = maximumWeight - minimumWeight;
  weightStable = variationKg <= SCALE_STABILITY_TOLERANCE_KG;
}


void sendScaleSnapshot() {
  if (WiFi.status() != WL_CONNECTED) {
    currentSendInterval = SCALE_RETRY_INTERVAL_MS;
    return;
  }

  StaticJsonDocument<384> doc;
  doc["device_id"] = deviceId;
  doc["device_name"] = deviceName;
  doc["hx711_ready"] = hx711Ready;
  doc["valid"] = readingValid;
  doc["weight_detected"] = weightDetected;
  doc["stable"] = weightStable;

  if (readingValid) {
    doc["weight_kg"] = currentWeightKg;
    doc["variation_kg"] = variationKg;
  } else {
    doc["weight_kg"] = nullptr;
    doc["variation_kg"] = nullptr;
  }

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  http.begin(scaleReadingUrl);
  // Keep network blocking short so HX711_ADC.update() continues near 10 Hz.
  http.setTimeout(750);
  http.addHeader("Content-Type", "application/json");
  int responseCode = http.POST(jsonPayload);
  http.end();

  if (responseCode == 200 || responseCode == 202) {
    currentSendInterval = SCALE_SEND_INTERVAL_MS;
  } else {
    currentSendInterval = SCALE_RETRY_INTERVAL_MS;
    Serial.print("Scale upload failed (HTTP ");
    Serial.print(responseCode);
    Serial.println("). Retrying in 5 seconds.");
  }
}


void printScaleStatus() {
  if (!hx711Initialized) {
    Serial.println("Scale: HX711 initialization failed");
    return;
  }
  if (!hx711Ready || !readingValid) {
    Serial.println("Scale: waiting for HX711 data");
    return;
  }

  Serial.print("Scale: ");
  Serial.print(currentWeightKg, 2);
  Serial.print(" kg | ");
  if (!weightDetected) {
    Serial.println("waiting for weight");
  } else if (!weightStable) {
    Serial.print("stabilizing, variation ");
    Serial.print(variationKg, 3);
    Serial.println(" kg");
  } else {
    Serial.println("stable");
  }
}


void printConfiguration() {
  Serial.println();
  Serial.println("Scale configuration:");
  Serial.print("  Device ID: ");
  Serial.println(deviceId);
  Serial.println("  HX711 DOUT: GPIO 19");
  Serial.println("  HX711 SCK:  GPIO 18");
  Serial.print("  Django endpoint: ");
  Serial.println(scaleReadingUrl);
  Serial.println("  No goat ID is transmitted by this controller.");
}
