/*
 * DHT21 (AM2301) Temperature & Humidity Sensor - Standalone Test
 * 
 * This is a simple test program to verify your DHT21 sensor is working correctly.
 * Use this to test the sensor before integrating with the full system.
 * 
 * Features:
 * - Reads temperature in Celsius and Fahrenheit
 * - Reads relative humidity percentage
 * - Displays readings on Serial Monitor
 * - Shows heat index (feels like temperature)
 * - Color-coded warnings for extreme conditions
 * 
 * Required Library:
 * - DHT sensor library by Adafruit
 * - Adafruit Unified Sensor
 * 
 * Author: KaMoTech
 * Date: March 2026
 */

#include <DHT.h>

// ============================================
// DHT21 SENSOR CONFIGURATION
// ============================================
#define DHT_PIN 14        // GPIO pin connected to DHT21 DATA pin
#define DHT_TYPE DHT21    // DHT21 (AM2301) sensor type

// Create DHT object
DHT dht(DHT_PIN, DHT_TYPE);

// ============================================
// LED INDICATOR (Optional - uses built-in LED)
// ============================================
#define LED_PIN 2         // ESP32 built-in LED

// ============================================
// TIMING CONFIGURATION
// ============================================
#define READ_INTERVAL 2000  // Read sensor every 2 seconds
unsigned long last_read = 0;

// ============================================
// TEMPERATURE THRESHOLDS
// ============================================
#define TEMP_LOW_WARNING 15.0    // Below this = cold warning
#define TEMP_HIGH_WARNING 30.0   // Above this = hot warning
#define TEMP_CRITICAL_HIGH 35.0  // Above this = critical warning

// ============================================
// HUMIDITY THRESHOLDS
// ============================================
#define HUMIDITY_LOW_WARNING 30.0   // Below this = dry warning
#define HUMIDITY_HIGH_WARNING 70.0  // Above this = humid warning
#define HUMIDITY_CRITICAL_HIGH 80.0 // Above this = critical warning

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n╔════════════════════════════════════════════╗");
  Serial.println("║  DHT21 Temperature & Humidity Sensor Test ║");
  Serial.println("╚════════════════════════════════════════════╝\n");
  
  // Initialize LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // Turn on LED to show system is ready
  
  // Initialize DHT sensor
  Serial.println("Initializing DHT21 sensor...");
  dht.begin();
  
  delay(2000);  // Give sensor time to stabilize
  
  Serial.println("✓ Sensor initialized!\n");
  Serial.println("Wiring Configuration (3-Wire DHT21):");
  Serial.println("┌─────────────────────────────────────┐");
  Serial.println("│ RED Wire (VCC)    →  5V or 3.3V    │");
  Serial.println("│ YELLOW Wire (DATA) →  GPIO 14      │");
  Serial.println("│ BLACK Wire (GND)  →  GND           │");
  Serial.println("└─────────────────────────────────────┘");
  Serial.println();
  Serial.println("✓ Your 3-wire module has built-in pull-up resistor");
  Serial.println("  No external resistor needed!\n");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
  
  delay(1000);
  
  Serial.println("Starting readings...\n");
  Serial.println("┌──────────┬─────────┬──────────┬────────────┬────────┐");
  Serial.println("│   Time   │  Temp   │ Humidity │ Heat Index │ Status │");
  Serial.println("├──────────┼─────────┼──────────┼────────────┼────────┤");
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
  // Check if it's time to read the sensor
  if (millis() - last_read >= READ_INTERVAL) {
    last_read = millis();
    
    // Read sensor
    read_and_display_sensor();
    
    // Blink LED to show activity
    digitalWrite(LED_PIN, LOW);
    delay(50);
    digitalWrite(LED_PIN, HIGH);
  }
}

// ============================================
// READ AND DISPLAY SENSOR DATA
// ============================================
void read_and_display_sensor() {
  // Read humidity
  float humidity = dht.readHumidity();
  
  // Read temperature in Celsius
  float temp_celsius = dht.readTemperature();
  
  // Read temperature in Fahrenheit
  float temp_fahrenheit = dht.readTemperature(true);
  
  // Check if readings failed
  if (isnan(humidity) || isnan(temp_celsius) || isnan(temp_fahrenheit)) {
    Serial.println("│ ERROR    │  ---    │   ---    │    ---     │  FAIL  │");
    Serial.println("│          │         │          │            │        │");
    Serial.println("│ ✗ Failed to read from DHT sensor!                  │");
    Serial.println("│ Check: Wiring, Power, Pull-up resistor             │");
    Serial.println("└─────────────────────────────────────────────────────┘");
    Serial.println();
    delay(1000);
    
    // Restart display header
    Serial.println("┌──────────┬─────────┬──────────┬────────────┬────────┐");
    Serial.println("│   Time   │  Temp   │ Humidity │ Heat Index │ Status │");
    Serial.println("├──────────┼─────────┼──────────┼────────────┼────────┤");
    return;
  }
  
  // Calculate heat index (feels like temperature)
  float heat_index = dht.computeHeatIndex(temp_fahrenheit, humidity);
  float heat_index_celsius = (heat_index - 32) * 5.0 / 9.0;
  
  // Format time (seconds since start)
  unsigned long seconds = millis() / 1000;
  char time_str[12];
  sprintf(time_str, "%3lum %02lus", seconds / 60, seconds % 60);
  
  // Display reading
  Serial.print("│ ");
  Serial.print(time_str);
  Serial.print(" │ ");
  
  // Temperature with color coding
  if (temp_celsius < TEMP_LOW_WARNING) {
    Serial.print("🔵 ");  // Cold
  } else if (temp_celsius > TEMP_CRITICAL_HIGH) {
    Serial.print("🔴 ");  // Too hot
  } else if (temp_celsius > TEMP_HIGH_WARNING) {
    Serial.print("🟠 ");  // Warm
  } else {
    Serial.print("🟢 ");  // Normal
  }
  
  Serial.printf("%4.1f°C", temp_celsius);
  Serial.print(" │ ");
  
  // Humidity with color coding
  if (humidity < HUMIDITY_LOW_WARNING) {
    Serial.print("🔵 ");  // Dry
  } else if (humidity > HUMIDITY_CRITICAL_HIGH) {
    Serial.print("🔴 ");  // Too humid
  } else if (humidity > HUMIDITY_HIGH_WARNING) {
    Serial.print("🟠 ");  // Humid
  } else {
    Serial.print("🟢 ");  // Normal
  }
  
  Serial.printf("%5.1f%%", humidity);
  Serial.print(" │ ");
  
  // Heat Index
  Serial.printf("%6.1f°C", heat_index_celsius);
  Serial.print(" │ ");
  
  // Status indicator
  String status = get_status(temp_celsius, humidity);
  Serial.print(status);
  
  // Pad status to 6 characters
  for (int i = status.length(); i < 6; i++) {
    Serial.print(" ");
  }
  
  Serial.println(" │");
  
  // Display warnings if conditions are extreme
  display_warnings(temp_celsius, temp_fahrenheit, humidity, heat_index_celsius);
}

// ============================================
// GET STATUS STRING
// ============================================
String get_status(float temp, float humidity) {
  // Critical conditions
  if (temp > TEMP_CRITICAL_HIGH) {
    return "CRITICAL";
  }
  if (humidity > HUMIDITY_CRITICAL_HIGH) {
    return "CRITICAL";
  }
  
  // Warning conditions
  if (temp < TEMP_LOW_WARNING || temp > TEMP_HIGH_WARNING) {
    return "WARN";
  }
  if (humidity < HUMIDITY_LOW_WARNING || humidity > HUMIDITY_HIGH_WARNING) {
    return "WARN";
  }
  
  // Normal
  return "OK";
}

// ============================================
// DISPLAY WARNINGS
// ============================================
void display_warnings(float temp_c, float temp_f, float humidity, float heat_index) {
  bool has_warning = false;
  
  // Temperature warnings
  if (temp_c < TEMP_LOW_WARNING) {
    Serial.println("│          │ ⚠️  LOW TEMPERATURE - Environment too cold     │");
    has_warning = true;
  }
  
  if (temp_c > TEMP_CRITICAL_HIGH) {
    Serial.println("│          │ 🚨 CRITICAL: High temperature detected!       │");
    Serial.println("│          │    Consider cooling or ventilation            │");
    has_warning = true;
  } else if (temp_c > TEMP_HIGH_WARNING) {
    Serial.println("│          │ ⚠️  HIGH TEMPERATURE - Consider turning on fan │");
    has_warning = true;
  }
  
  // Humidity warnings
  if (humidity < HUMIDITY_LOW_WARNING) {
    Serial.println("│          │ ⚠️  LOW HUMIDITY - Air is too dry              │");
    has_warning = true;
  }
  
  if (humidity > HUMIDITY_CRITICAL_HIGH) {
    Serial.println("│          │ 🚨 CRITICAL: Very high humidity detected!     │");
    Serial.println("│          │    Risk of condensation and mold growth       │");
    has_warning = true;
  } else if (humidity > HUMIDITY_HIGH_WARNING) {
    Serial.println("│          │ ⚠️  HIGH HUMIDITY - Ensure good ventilation    │");
    has_warning = true;
  }
  
  // Heat index warning
  if (heat_index > 32.0) {
    Serial.println("│          │ ⚠️  HIGH HEAT INDEX - Feels hotter than actual │");
    has_warning = true;
  }
  
  // Add separator after warnings
  if (has_warning) {
    Serial.println("├──────────┼─────────┼──────────┼────────────┼────────┤");
  }
}

/*
 * ═══════════════════════════════════════════════════════════════════
 * WIRING DIAGRAM - DHT21/AM2301 Sensor (3-Wire Module)
 * ═══════════════════════════════════════════════════════════════════
 * 
 * Your 3-Wire DHT21 Module:
 * 
 *     ┌──────────────┐
 *     │   DHT21/AM2301│
 *     │   (3-Wire)   │
 *     └──┬───┬───┬───┘
 *        │   │   │
 *      RED YELLOW BLACK
 *       │   │   │
 *       │   │   └─────────→ GND (ESP32)
 *       │   │
 *       │   └─────────────→ GPIO 14 (ESP32)
 *       │
 *       └─────────────────→ 5V or 3.3V (ESP32)
 * 
 * 
 * Wire Colors & Connections:
 * ┌────────────┬──────────────┬─────────────────┐
 * │ Wire Color │   Function   │   ESP32 Pin     │
 * ├────────────┼──────────────┼─────────────────┤
 * │    RED     │   VCC/Power  │   5V or 3.3V    │
 * │   YELLOW   │   DATA/Signal│   GPIO 14       │
 * │   BLACK    │   GND/Ground │   GND           │
 * └────────────┴──────────────┴─────────────────┘
 * 
 * 
 * Simplified Connection Diagram:
 * 
 *    ESP32                    DHT21 Sensor
 * ┌─────────┐              ┌──────────────┐
 * │         │              │              │
 * │  5V  ●──┼──────────────┼──● RED       │
 * │         │              │              │
 * │ GPIO14●─┼──────────────┼──● YELLOW    │
 * │         │              │              │
 * │  GND ●──┼──────────────┼──● BLACK     │
 * │         │              │              │
 * └─────────┘              └──────────────┘
 * 
 * 
 * ⚠️  IMPORTANT NOTES:
 * 
 * 1. Pull-up Resistor:
 *    ✓ Your 3-wire module has BUILT-IN pull-up resistor
 *    ✓ NO external 10kΩ resistor needed!
 * 
 * 2. Power Supply:
 *    - Works with both 3.3V or 5V
 *    - Recommended: Use 5V for more stable readings
 *    - ESP32 has both 3.3V and 5V pins available
 * 
 * 3. GPIO Pin (Currently using GPIO 14):
 *    - You can change to any GPIO pin
 *    - Change #define DHT_PIN 14 to your preferred pin
 *    - Avoid: GPIO 6-11 (flash), GPIO 34-39 (input only)
 * 
 * 4. Sensor Placement Tips:
 *    - Keep away from heat sources (motors, sunlight)
 *    - Allow good air circulation
 *    - Protect from direct water/rain
 *    - Mount vertically if possible
 * 
 * 5. Sensor Specifications:
 *    - Temperature Range: -40°C to 80°C
 *    - Humidity Range: 0% to 100% RH
 *    - Temperature Accuracy: ±0.5°C
 *    - Humidity Accuracy: ±3% RH
 *    - Reading Interval: Minimum 2 seconds
 * 
 * 6. Troubleshooting:
 *    ❌ "Failed to read" errors:
 *       - Check all 3 wires are connected firmly
 *       - Verify power (5V or 3.3V) is connected
 *       - Try different GPIO pin
 *       - Sensor needs 1-2 seconds to stabilize after power-on
 *    
 *    ❌ Readings always 0 or NaN:
 *       - Check YELLOW wire is on GPIO 14
 *       - Verify sensor is getting power (RED to 5V, BLACK to GND)
 *       - Try uploading code again
 * 
 *    ❌ Unstable readings:
 *       - Use 5V instead of 3.3V
 *       - Check for loose connections
 *       - Keep sensor away from electromagnetic interference
 * 
 * ═══════════════════════════════════════════════════════════════════
 * 
 * DHT21 vs DHT11 vs DHT22:
 * 
 * DHT21 (AM2301) = DHT22 with different housing
 * - Better accuracy than DHT11
 * - More expensive than DHT11
 * - Same performance as DHT22
 * - This code works for all three types!
 * 
 * ═══════════════════════════════════════════════════════════════════
 * 
 * Expected Serial Monitor Output:
 * 
 * ╔════════════════════════════════════════════╗
 * ║  DHT21 Temperature & Humidity Sensor Test ║
 * ╚════════════════════════════════════════════╝
 * 
 * ┌──────────┬─────────┬──────────┬────────────┬────────┐
 * │   Time   │  Temp   │ Humidity │ Heat Index │ Status │
 * ├──────────┼─────────┼──────────┼────────────┼────────┤
 * │   0m 02s │ 🟢 25.1°C │ 🟢 60.5% │   24.8°C   │   OK   │
 * │   0m 04s │ 🟢 25.2°C │ 🟢 60.3% │   24.9°C   │   OK   │
 * │   0m 06s │ 🟢 25.1°C │ 🟢 60.4% │   24.8°C   │   OK   │
 * 
 * ═══════════════════════════════════════════════════════════════════
 */
