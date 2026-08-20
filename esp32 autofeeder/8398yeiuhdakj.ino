GRANT ALL PRIVILEGES ON goat_monitoring.* TO 'admin'@'%' IDENTIFIED BY 'kamotech01';
FLUSH PRIVILEGES;/*
 * ESP32 IoT Goat Feeder System with Web Dashboard
 * Integrates: Automated Feeder (Servo), Rain Detection, Ultrasonic Feed Level
 * Web Server: Real-time sensor monitoring via HTTP
 * Database: MySQL over WiFi
 * 
 * Author: IoT System
 * Date: 2026
 */

#include <WiFi.h>
#include <WebServer.h>
#include <Arduino.h>
#include <ESP32Servo.h>
#include <time.h>
#include <MySQL_Connection.h>
#include <MySQL_Cursor.h>

// ============================================
// WIFI CONFIGURATION
// ============================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ============================================
// WEB SERVER
// ============================================
WebServer server(80);

// ============================================
// MYSQL CONFIGURATION
// ============================================
const char* mysql_server = "10.253.199.155";  // e.g., "192.168.1.100"
const int mysql_port = 3306;
const char* mysql_user = "admin";             // e.g., "iot_user"
const char* mysql_password = "YOUR_DB_PASSWORD";     // e.g., "YOUR_DB_PASSWORD"
const char* mysql_database = "goat_monitoring";        // Your database name
const char* mysql_table = "feeder_events";             // Table for event logs

// Alternative: Use HTTP + PHP API (recommended for ESP32)
const char* api_server = "10.253.199.155";  // Django server IP
const int api_port = 80;
String php_endpoint = "/api/log_event.php";         // Your PHP endpoint
String django_feed_level_endpoint = "/feeding/api/levels/update/";  // Django feed level API

// ============================================
// PIN DEFINITIONS (ESP32 GPIO)
// ============================================
#define SERVO_PIN 15        // PWM output for servo motor
#define RAIN_SENSOR_PIN 32  // ADC1_CH4 - Analog input for rain sensor
#define TRIG_PIN 5          // Ultrasonic sensor trigger
#define ECHO_PIN 18         // Ultrasonic sensor echo (via voltage divider)
#define BUTTON_PIN 25       // Manual feed button (active LOW, use INPUT_PULLUP)

// ============================================
// SYSTEM CONFIGURATION
// ============================================
// Ultrasonic Sensor Settings (Feed Level Monitoring)
// Logic: Measure distance from sensor to feed surface
//        CLOSER distance (smaller number) = HIGHER feed level (FULL = 100%)
//        FARTHER distance (larger number) = LOWER feed level (EMPTY = 0%)
#define ULTRASONIC_CHECK_INTERVAL 2000   // Check feed level every 2 seconds (real-time for web)
#define FEED_CONTAINER_HEIGHT 30         // Total height of container in cm
#define FEED_FULL_DISTANCE 5             // Distance when container is full (cm)
#define FEED_EMPTY_DISTANCE 28           // Distance when container is empty (cm)
#define FEED_MIN_DISTANCE 3              // Minimum possible distance (closer = overflow)
#define FEED_MAX_DISTANCE 35             // Maximum distance to measure
#define DEFAULT_FEEDER_ID 1              // Default feeder device ID
unsigned long last_ultrasonic_check = 0;
unsigned long last_feed_level_report = 0;
#define FEED_LEVEL_REPORT_INTERVAL 30000 // Report to server every 30 seconds
float current_feed_distance = 0;        // Current distance reading (cm)
int current_feed_percentage = 0;        // Current feed level as percentage (0-100%)
bool feeder_is_open = false;            // Current feeder state

// Servo Motor Control
Servo feederServo;
#define SERVO_OPEN_ANGLE 90
#define SERVO_CLOSE_ANGLE 0
#define SERVO_SPEED_MS 500  // Time to move servo
unsigned long servo_move_start = 0;
bool servo_moving = false;
int servo_target_angle = SERVO_CLOSE_ANGLE;
int servo_current_angle = SERVO_CLOSE_ANGLE;

// Automatic Feeding System (controlled by ultrasonic sensor)
// No time-based feeding - purely feed level based

// Rain Detection System
#define RAIN_THRESHOLD 2000  // Threshold for rain detection
#define RAIN_CHECK_INTERVAL 10000  // Check rain every 10 seconds
unsigned long last_rain_check = 0;
int last_rain_value = 0;
bool currently_raining = false;

// Timing
#define DEBUG_INTERVAL 5000  // Print debug info every 5 seconds
unsigned long last_debug_time = 0;

// WiFi and DB status
bool wifi_connected = false;
bool mysql_connected = false;
unsigned long last_wifi_check = 0;
#define WIFI_CHECK_INTERVAL 30000
unsigned long last_mysql_attempt = 0;
#define MYSQL_RETRY_INTERVAL 10000

WiFiClient mysql_client;
MySQL_Connection mysql_conn(&mysql_client);
IPAddress mysql_server_ip;
bool mysql_ip_resolved = false;

// Button debounce
const unsigned long BUTTON_DEBOUNCE_MS = 50;
unsigned long last_button_change = 0;
bool last_button_state = HIGH;
bool button_pressed = false;

// Manual feed state machine (non-blocking)
const unsigned long MANUAL_FEED_HOLD_MS = 3000;
enum ManualFeedStage {
  MANUAL_FEED_IDLE = 0,
  MANUAL_FEED_OPENING,
  MANUAL_FEED_HOLDING,
  MANUAL_FEED_CLOSING
};
ManualFeedStage manual_feed_stage = MANUAL_FEED_IDLE;
unsigned long manual_feed_stage_start = 0;

// ============================================
// FUNCTION DECLARATIONS
// ============================================
void initializeWiFi();
void checkWiFiConnection();
void initializeServo();
void initializeRainSensor();
void controlFeeder(int angle);
void moveServo();
void checkFeedLevelAndControl();    // Check feed level and control servo
void readRainSensor();
void initializeUltrasonic();
float getDistance();
int calculateFeedPercentage(float distance);
void reportFeedLevelToDjango();     // Report feed level to Django server
void processSerialCommands();       // Process serial monitor commands
void logEventToDatabase(String eventType, int sensorValue);
void logEventViaHTTP(String eventType, int sensorValue);
void displayDebugInfo();
String getTimestamp();
bool resolveMySQLServer();
bool ensureMySQLConnection();
String escapeSql(String value);

// Web Server Functions
void initializeWebServer();
void handleRoot();
void handleSensorAPI();
void handleCommandAPI();
void handleNotFound();

// Manual Control Functions
void manualFeed();
void openFeeder();
void closeFeeder();
void testServo();
void handleManualFeedSequence();

// ============================================
// WEB SERVER FUNCTIONS
// ============================================

void initializeWebServer() {
  // Route handlers
  server.on("/", HTTP_GET, handleRoot);
  server.on("/api/sensors", HTTP_GET, handleSensorAPI);
  server.on("/api/command", HTTP_GET, handleCommandAPI);
  server.onNotFound(handleNotFound);
  
  // Start server
  server.begin();
  Serial.println("[Web] Server started on port 80");
  Serial.print("[Web] Access dashboard at: http://");
  Serial.println(WiFi.localIP());
}

void handleRoot() {
  // Serve the HTML dashboard
  static const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32 Goat Feeder Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .status-bar {
            background: white;
            border-radius: 10px;
            padding: 15px 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .status-item { display: flex; align-items: center; margin: 5px 10px; }
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-dot.connected { background: #4caf50; }
        .status-dot.disconnected { background: #f44336; animation: none; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 24px rgba(0,0,0,0.15);
        }
        .card-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        .card-icon { font-size: 2.5em; margin-right: 15px; }
        .card-title { font-size: 1.3em; font-weight: 600; color: #555; }
        .card-value {
            font-size: 3em;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .card-unit { font-size: 0.4em; opacity: 0.7; margin-left: 5px; }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #f0f0f0;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
            margin-top: 15px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4caf50, #8bc34a);
            border-radius: 15px;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 0.9em;
        }
        .progress-fill.low { background: linear-gradient(90deg, #f44336, #e91e63); }
        .progress-fill.medium { background: linear-gradient(90deg, #ff9800, #ffc107); }
        .rain-status {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            border-radius: 10px;
            margin-top: 15px;
            font-size: 1.2em;
            font-weight: 600;
        }
        .rain-status.raining {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        .rain-status.dry {
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            color: #555;
        }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
        .info-item {
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .info-label { font-size: 0.85em; color: #888; margin-bottom: 5px; }
        .info-value { font-size: 1.1em; font-weight: 600; color: #333; }
        .last-update { text-align: center; color: white; margin-top: 20px; font-size: 0.9em; opacity: 0.8; }
        .error-message {
            background: #f44336;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        @media (max-width: 768px) {
            .header h1 { font-size: 1.8em; }
            .status-bar { flex-direction: column; }
            .info-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐐 ESP32 Goat Feeder Monitor</h1>
            <p>Real-time Sensor Monitoring System</p>
        </div>
        <div class="status-bar">
            <div class="status-item">
                <div class="status-dot" id="connectionStatus"></div>
                <span id="connectionText">Connecting...</span>
            </div>
            <div class="status-item"><strong>WiFi:</strong>&nbsp;<span id="wifiStatus">--</span></div>
            <div class="status-item"><strong>IP:</strong>&nbsp;<span id="ipAddress">--</span></div>
          <div class="status-item"><strong>MySQL:</strong>&nbsp;<span id="mysqlStatus">--</span></div>
        </div>
        <div class="error-message" id="errorMessage"></div>
        
        <!-- Control Panel -->
        <div style="background: white; border-radius: 15px; padding: 25px; margin-bottom: 20px; box-shadow: 0 8px 16px rgba(0,0,0,0.1);">
            <h2 style="margin: 0 0 20px 0; color: #555; font-size: 1.5em; border-bottom: 2px solid #f0f0f0; padding-bottom: 15px;">⚡ Feeder Controls</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
                <button onclick="sendCommand('feed')" style="padding: 15px 25px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; font-size: 1em; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 12px rgba(0,0,0,0.3)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';">🍽️ Manual Feed</button>
                <button onclick="sendCommand('open')" style="padding: 15px 25px; background: linear-gradient(135deg, #4caf50 0%, #8bc34a 100%); color: white; border: none; border-radius: 10px; font-size: 1em; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 12px rgba(0,0,0,0.3)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';">⬆️ Open Feeder</button>
                <button onclick="sendCommand('close')" style="padding: 15px 25px; background: linear-gradient(135deg, #f44336 0%, #e91e63 100%); color: white; border: none; border-radius: 10px; font-size: 1em; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 12px rgba(0,0,0,0.3)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';">⬇️ Close Feeder</button>
                <button onclick="sendCommand('test')" style="padding: 15px 25px; background: linear-gradient(135deg, #ff9800 0%, #ffc107 100%); color: white; border: none; border-radius: 10px; font-size: 1em; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 12px rgba(0,0,0,0.3)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';">🔧 Test Servo</button>
            </div>
              <div style="margin-top: 15px; font-weight: 600; color: #444;">
                Feeder State: <span id="feederStateBadge">--</span>
              </div>
            <div id="commandFeedback" style="margin-top: 15px; padding: 10px; border-radius: 8px; display: none; font-weight: 600;"></div>
        </div>
        
        <div class="dashboard">
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📊</div>
                    <div class="card-title">Feed Level</div>
                </div>
                <div class="card-value"><span id="feedLevel">--</span><span class="card-unit">%</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="feedProgress" style="width: 0%">0%</div>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Distance</div>
                        <div class="info-value"><span id="feedDistance">--</span> cm</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Status</div>
                        <div class="info-value" id="feederStatus">--</div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">🌧️</div>
                    <div class="card-title">Rain Sensor</div>
                </div>
                <div class="card-value"><span id="rainValue">--</span></div>
                <div class="rain-status dry" id="rainStatus">☀️ No Rain Detected</div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Threshold</div>
                        <div class="info-value">2000</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Sensor State</div>
                        <div class="info-value" id="rainState">DRY</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="last-update">Last updated: <span id="lastUpdate">Never</span></div>
    </div>
    <script>
        const UPDATE_INTERVAL = 2000;
        let updateTimer;
        async function updateData() {
            try {
                const response = await fetch('/api/sensors');
                if (!response.ok) throw new Error('Failed to fetch data');
                const data = await response.json();
                document.getElementById('connectionStatus').className = 'status-dot connected';
                document.getElementById('connectionText').textContent = 'Connected';
                document.getElementById('errorMessage').style.display = 'none';
                document.getElementById('wifiStatus').textContent = data.wifi_connected ? 'Connected' : 'Disconnected';
                document.getElementById('ipAddress').textContent = data.ip_address || '--';
                document.getElementById('mysqlStatus').textContent = data.mysql_connected ? 'Connected' : 'Disconnected';
                const feedLevel = data.feed_level || 0;
                const feedDistance = data.feed_distance || 0;
                document.getElementById('feedLevel').textContent = feedLevel;
                document.getElementById('feedDistance').textContent = feedDistance.toFixed(1);
                const progressBar = document.getElementById('feedProgress');
                progressBar.style.width = feedLevel + '%';
                progressBar.textContent = feedLevel + '%';
                if (feedLevel < 30) {
                    progressBar.className = 'progress-fill low';
                } else if (feedLevel < 70) {
                    progressBar.className = 'progress-fill medium';
                } else {
                    progressBar.className = 'progress-fill';
                }
                document.getElementById('feederStatus').textContent = data.feeder_open ? 'OPEN' : 'CLOSED';
                document.getElementById('feederStateBadge').textContent = data.feeder_open ? 'OPEN' : 'CLOSED';
                const rainValue = data.rain_value || 0;
                const isRaining = data.is_raining || false;
                document.getElementById('rainValue').textContent = rainValue;
                document.getElementById('rainState').textContent = isRaining ? 'WET' : 'DRY';
                const rainStatus = document.getElementById('rainStatus');
                if (isRaining) {
                    rainStatus.className = 'rain-status raining';
                    rainStatus.innerHTML = '🌧️ Rain Detected!';
                } else {
                    rainStatus.className = 'rain-status dry';
                    rainStatus.innerHTML = '☀️ No Rain Detected';
                }
                const now = new Date();
                document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('connectionStatus').className = 'status-dot disconnected';
                document.getElementById('connectionText').textContent = 'Connection Lost';
                const errorMsg = document.getElementById('errorMessage');
                errorMsg.textContent = '⚠️ Unable to connect to ESP32. Please check your connection.';
                errorMsg.style.display = 'block';
            }
        }
        function formatUptime(milliseconds) {
            const seconds = Math.floor(milliseconds / 1000);
            const minutes = Math.floor(seconds / 60);
            const hours = Math.floor(minutes / 60);
            const days = Math.floor(hours / 24);
            if (days > 0) return `${days}d ${hours % 24}h`;
            if (hours > 0) return `${hours}h ${minutes % 60}m`;
            if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
            return `${seconds}s`;
        }
        function formatBytes(bytes) {
            return (bytes / 1024).toFixed(1) + ' KB';
        }
        function startUpdates() {
            updateData();
            updateTimer = setInterval(updateData, UPDATE_INTERVAL);
        }
        function stopUpdates() {
            if (updateTimer) clearInterval(updateTimer);
        }
        
        // Send command to ESP32
        async function sendCommand(cmd) {
            const feedback = document.getElementById('commandFeedback');
            feedback.style.display = 'block';
            feedback.style.background = '#2196f3';
            feedback.style.color = 'white';
            feedback.textContent = '⏳ Sending command: ' + cmd + '...';
            
            try {
                const response = await fetch('/api/command?cmd=' + cmd);
                const result = await response.json();
                
                if (result.success) {
                    feedback.style.background = '#4caf50';
                    feedback.textContent = '✓ ' + result.message;
                } else {
                    feedback.style.background = '#f44336';
                    feedback.textContent = '✗ Error: ' + result.message;
                }
                
                // Hide feedback after 3 seconds
                setTimeout(() => {
                    feedback.style.display = 'none';
                }, 3000);
                
            } catch (error) {
                feedback.style.background = '#f44336';
                feedback.textContent = '✗ Failed to send command';
                setTimeout(() => {
                    feedback.style.display = 'none';
                }, 3000);
            }
        }
        
        window.addEventListener('load', () => { startUpdates(); });
        window.addEventListener('beforeunload', () => { stopUpdates(); });
    </script>
</body>
</html>
)rawliteral";

  server.send_P(200, "text/html", INDEX_HTML);
}

void handleSensorAPI() {
  // Build JSON response with all sensor data
  String json = "{";
  json += "\"wifi_connected\":" + String(wifi_connected ? "true" : "false") + ",";
  json += "\"ip_address\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  json += "\"mysql_connected\":" + String(mysql_connected ? "true" : "false") + ",";
  json += "\"feed_level\":" + String(current_feed_percentage) + ",";
  json += "\"feed_distance\":" + String(current_feed_distance) + ",";
  json += "\"feeder_open\":" + String(feeder_is_open ? "true" : "false") + ",";
  json += "\"rain_value\":" + String(last_rain_value) + ",";
  json += "\"is_raining\":" + String(currently_raining ? "true" : "false") + ",";
  json += "\"uptime\":" + String(millis()) + ",";
  json += "\"free_heap\":" + String(ESP.getFreeHeap());
  json += "}";
  
  server.send(200, "application/json", json);
}

void handleCommandAPI() {
  String cmd = server.arg("cmd");
  String response = "{";
  
  if (cmd == "feed") {
    manualFeed();
    response += "\"success\":true,\"message\":\"Manual feed executed (open 3s, close)\"";
  }
  else if (cmd == "open") {
    openFeeder();
    response += "\"success\":true,\"message\":\"Feeder opened\"";
  }
  else if (cmd == "close") {
    closeFeeder();
    response += "\"success\":true,\"message\":\"Feeder closed\"";
  }
  else if (cmd == "test") {
    // Run test in non-blocking way (just start it)
    Serial.println("[Web] Test servo command received");
    testServo();
    response += "\"success\":true,\"message\":\"Servo test started\"";
  }
  else {
    response += "\"success\":false,\"message\":\"Unknown command: " + cmd + "\"";
  }
  
  response += "}";
  server.send(200, "application/json", response);
}

void handleNotFound() {
  server.send(404, "text/plain", "404: Not Found");
}

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n=== ESP32 IoT Goat Feeder System Starting ===");
  
  // Initialize pins
  pinMode(RAIN_SENSOR_PIN, INPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Initialize components
  initializeWiFi();
  
  // Initialize Web Server
  initializeWebServer();
  
  initializeServo();
  initializeRainSensor();
  initializeUltrasonic();
  
  // Set starting time
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("Waiting for NTP time update...");
  delay(2000);
  
  Serial.println("Setup complete!");
  Serial.println("\n=== SERIAL COMMANDS ===");
  Serial.println("Type 'feed' - Manual feeding (open/close)");
  Serial.println("Type 'open' - Open feeder");
  Serial.println("Type 'close' - Close feeder");
  Serial.println("Type 'test' - Test servo sweep (0-90-180-90-0)");
  Serial.println("Type 'status' - Show system status");
  Serial.println("Type 'help' - Show this menu");
  Serial.println("======================\n");
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
  // Non-blocking timing system
  unsigned long current_time = millis();
  
  // Handle web server requests
  server.handleClient();
  
  // Check for serial commands
  processSerialCommands();
  
  // Check WiFi connection periodically
  if (current_time - last_wifi_check >= WIFI_CHECK_INTERVAL) {
    checkWiFiConnection();
    last_wifi_check = current_time;
  }
  
  int button_state = digitalRead(BUTTON_PIN);
  if (button_state != last_button_state) {
    last_button_change = current_time;
    last_button_state = button_state;
  }
  if (current_time - last_button_change > BUTTON_DEBOUNCE_MS) {
    if (!button_pressed && button_state == LOW) {
      button_pressed = true;
      manualFeed();
    } else if (button_state == HIGH) {
      button_pressed = false;
    }
  }
  
  // Servo Motor Control (non-blocking movement)
  if (servo_moving) {
    moveServo();
  }

  handleManualFeedSequence();
  
  // Automatic Feeder System (Feed Level Monitoring)
  // Checks ultrasonic sensor and controls servo based on feed level
  if (current_time - last_ultrasonic_check >= ULTRASONIC_CHECK_INTERVAL) {
    checkFeedLevelAndControl();
    last_ultrasonic_check = current_time;
  }
  
  // Rain Detection System
  if (current_time - last_rain_check >= RAIN_CHECK_INTERVAL) {
    readRainSensor();
    last_rain_check = current_time;
  }
  
  // Debug Information
  if (current_time - last_debug_time >= DEBUG_INTERVAL) {
    displayDebugInfo();
    last_debug_time = current_time;
  }
}

// ============================================
// WIFI + MYSQL CONNECTION
// ============================================
void initializeWiFi() {
  Serial.println("\n[WiFi] Initializing WiFi...");
  Serial.print("[WiFi] Connecting to SSID: ");
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
    Serial.print("[WiFi] RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    resolveMySQLServer();
  } else {
    wifi_connected = false;
    Serial.println("\n[WiFi] Failed to connect!");
  }
}

void checkWiFiConnection() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifi_connected) {
      wifi_connected = true;
      Serial.println("[WiFi] Reconnected!");
      resolveMySQLServer();
    }
  } else {
    if (wifi_connected) {
      wifi_connected = false;
      Serial.println("[WiFi] Connection lost!");
      mysql_connected = false;
    }
  }
}

bool resolveMySQLServer() {
  if (!wifi_connected) {
    return false;
  }

  mysql_ip_resolved = WiFi.hostByName(mysql_server, mysql_server_ip);
  if (!mysql_ip_resolved) {
    Serial.println("[MySQL] DNS lookup failed");
    return false;
  }

  Serial.print("[MySQL] Server IP: ");
  Serial.println(mysql_server_ip);
  return true;
}

bool ensureMySQLConnection() {
  if (!wifi_connected) {
    return false;
  }

  if (mysql_conn.connected()) {
    mysql_connected = true;
    return true;
  }

  unsigned long now = millis();
  if (now - last_mysql_attempt < MYSQL_RETRY_INTERVAL) {
    return false;
  }

  last_mysql_attempt = now;

  if (!mysql_ip_resolved && !resolveMySQLServer()) {
    return false;
  }

  Serial.println("[MySQL] Connecting...");
  if (mysql_conn.connect(mysql_server_ip, mysql_port, (char*)mysql_user, (char*)mysql_password)) {
    mysql_connected = true;
    Serial.println("[MySQL] Connected");
    return true;
  }

  mysql_connected = false;
  Serial.println("[MySQL] Connection failed");
  return false;
}

// ============================================
// SERVO CONTROL FUNCTIONS
// ============================================
void initializeServo() {
  Serial.println("[Servo] Initializing servo motor...");
  
  // Attach servo to pin
  feederServo.attach(SERVO_PIN);
  
  // Set to closed position initially
  feederServo.write(SERVO_CLOSE_ANGLE);
  servo_current_angle = SERVO_CLOSE_ANGLE;
  servo_target_angle = SERVO_CLOSE_ANGLE;
  feeder_is_open = false;
  
  Serial.println("[Servo] Initialized at CLOSE position (0°)");
}

void controlFeeder(int angle) {
  if (angle == servo_current_angle) {
    Serial.println("[Servo] Already at target angle");
    return;
  }
  
  servo_target_angle = angle;
  servo_moving = true;
  servo_move_start = millis();
  
  // Update feeder status
  feeder_is_open = (angle == SERVO_OPEN_ANGLE);
  
  String status = (angle == SERVO_OPEN_ANGLE) ? "OPENING" : "CLOSING";
  Serial.print("[Servo] ");
  Serial.print(status);
  Serial.print(" feeder to ");
  Serial.print(angle);
  Serial.println("°");
}

void moveServo() {
  unsigned long current_time = millis();
  
  // Check if movement is complete
  if (current_time - servo_move_start >= SERVO_SPEED_MS) {
    feederServo.write(servo_target_angle);
    servo_current_angle = servo_target_angle;
    servo_moving = false;
    
    String status = (servo_current_angle == SERVO_OPEN_ANGLE) ? "OPEN" : "CLOSED";
    Serial.print("[Servo] Feeder is now ");
    Serial.println(status);
    
    // Log event
    String eventType = (servo_current_angle == SERVO_OPEN_ANGLE) ? "FEEDER_OPENED" : "FEEDER_CLOSED";
    logEventViaHTTP(eventType, servo_current_angle);
  } else {
    // Gradual movement (optional - for smoother operation)
    float progress = (float)(current_time - servo_move_start) / SERVO_SPEED_MS;
    int current_pos = servo_current_angle + (servo_target_angle - servo_current_angle) * progress;
    feederServo.write(current_pos);
  }
}

// ============================================
// ULTRASONIC SENSOR (FEED LEVEL)
// ============================================
void initializeUltrasonic() {
  Serial.println("[Ultrasonic] Initializing ultrasonic sensor...");
  Serial.print("[Ultrasonic] Container height: ");
  Serial.print(FEED_CONTAINER_HEIGHT);
  Serial.println(" cm");
  Serial.print("[Ultrasonic] Full distance: ");
  Serial.print(FEED_FULL_DISTANCE);
  Serial.println(" cm");
  Serial.print("[Ultrasonic] Empty distance: ");
  Serial.print(FEED_EMPTY_DISTANCE);
  Serial.println(" cm");
  
  // Initial reading
  float initial_distance = getDistance();
  current_feed_distance = initial_distance;
  current_feed_percentage = calculateFeedPercentage(initial_distance);
  
  Serial.print("[Ultrasonic] Initial reading: ");
  Serial.print(initial_distance);
  Serial.print(" cm (");
  Serial.print(current_feed_percentage);
  Serial.println("%)");
}

float getDistance() {
  // Send ultrasonic pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  // Read echo pulse duration
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);  // Timeout: 30ms
  
  // Calculate distance in cm
  // Speed of sound = 343 m/s = 0.0343 cm/µs
  // Distance = (duration / 2) * 0.0343
  float distance = (duration * 0.0343) / 2.0;
  
  // Validate reading
  if (distance < FEED_MIN_DISTANCE || distance > FEED_MAX_DISTANCE || distance == 0) {
    // Invalid reading - return last known good value
    return current_feed_distance;
  }
  
  return distance;
}

int calculateFeedPercentage(float distance) {
  // Invert logic: closer distance = higher feed level
  // FEED_FULL_DISTANCE (e.g., 5cm) = 100%
  // FEED_EMPTY_DISTANCE (e.g., 28cm) = 0%
  
  if (distance <= FEED_FULL_DISTANCE) {
    return 100;  // Full or overflow
  }
  
  if (distance >= FEED_EMPTY_DISTANCE) {
    return 0;  // Empty
  }
  
  // Linear interpolation
  int percentage = 100 - ((distance - FEED_FULL_DISTANCE) * 100 / (FEED_EMPTY_DISTANCE - FEED_FULL_DISTANCE));
  
  // Clamp to 0-100 range
  percentage = constrain(percentage, 0, 100);
  
  return percentage;
}

void checkFeedLevelAndControl() {
  // Read current distance
  float distance = getDistance();
  int percentage = calculateFeedPercentage(distance);
  
  // Update global variables
  current_feed_distance = distance;
  current_feed_percentage = percentage;
  
  Serial.print("[Feed Level] Distance: ");
  Serial.print(distance);
  Serial.print(" cm | Level: ");
  Serial.print(percentage);
  Serial.println("%");
  
  // Report to Django server periodically
  unsigned long current_time = millis();
  if (current_time - last_feed_level_report >= FEED_LEVEL_REPORT_INTERVAL) {
    reportFeedLevelToDjango();
    last_feed_level_report = current_time;
  }
  
  // Automatic feeding logic (example - customize as needed)
  // Uncomment to enable automatic feeding based on level
  /*
  if (percentage < 20 && !feeder_is_open) {
    Serial.println("[Auto Feed] Low feed level detected - opening feeder");
    controlFeeder(SERVO_OPEN_ANGLE);
  }
  else if (percentage > 80 && feeder_is_open) {
    Serial.println("[Auto Feed] Feed level sufficient - closing feeder");
    controlFeeder(SERVO_CLOSE_ANGLE);
  }
  */
}

// ============================================
// RAIN SENSOR
// ============================================
void initializeRainSensor() {
  Serial.println("[Rain] Initializing rain sensor...");
  Serial.print("[Rain] Threshold set to: ");
  Serial.println(RAIN_THRESHOLD);
  
  // Initial reading
  int initial_rain = analogRead(RAIN_SENSOR_PIN);
  last_rain_value = initial_rain;
  currently_raining = (initial_rain < RAIN_THRESHOLD);
  
  Serial.print("[Rain] Initial reading: ");
  Serial.print(initial_rain);
  Serial.print(" - ");
  Serial.println(currently_raining ? "RAINING" : "DRY");
}

void readRainSensor() {
  int rain_value = analogRead(RAIN_SENSOR_PIN);
  last_rain_value = rain_value;  // Update reading every time
  
  bool is_raining = (rain_value < RAIN_THRESHOLD);  // Low value = wet = rain
  
  if (is_raining && !currently_raining) {
    // Rain started
    currently_raining = true;
    Serial.println("\n[Rain] *** RAIN DETECTED ***");
    Serial.print("[Rain] Sensor Value: ");
    Serial.println(rain_value);
    logEventViaHTTP("Rain Detected", rain_value);
  } 
  else if (!is_raining && currently_raining) {
    // Rain stopped
    currently_raining = false;
    Serial.println("[Rain] Rain cleared");
    logEventViaHTTP("Rain Cleared", rain_value);
  }
}

// ============================================
// DATABASE LOGGING
// ============================================
void logEventViaHTTP(String eventType, int sensorValue) {
  logEventToDatabase(eventType, sensorValue);
}

void reportFeedLevelToDjango() {
  if (!wifi_connected) {
    return;
  }
  
  Serial.print("[Django] Reporting feed level: ");
  Serial.print(current_feed_percentage);
  Serial.println("%");
  
  // Implement HTTP POST to Django server here using HTTPClient
  // Example: POST to /feeding/api/levels/update/
}

// ============================================
// SERIAL COMMANDS
// ============================================
void processSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();  // Remove whitespace
    command.toLowerCase();  // Convert to lowercase
    
    Serial.print("\n[Command] Received: ");
    Serial.println(command);
    
    if (command == "feed") {
      Serial.println("[Command] Executing manual feed...");
      manualFeed();
    }
    else if (command == "open") {
      Serial.println("[Command] Opening feeder...");
      openFeeder();
    }
    else if (command == "close") {
      Serial.println("[Command] Closing feeder...");
      closeFeeder();
    }
    else if (command == "status") {
      Serial.println("[Command] Displaying system status...");
      displayDebugInfo();
    }
    else if (command == "help") {
      Serial.println("\n=== SERIAL COMMANDS ===");
      Serial.println("Type 'feed' - Manual feeding (open/close)");
      Serial.println("Type 'open' - Open feeder");
      Serial.println("Type 'close' - Close feeder");
      Serial.println("Type 'test' - Test servo sweep (0-90-180-90-0)");
      Serial.println("Type 'status' - Show system status");
      Serial.println("Type 'help' - Show this menu");
      Serial.println("======================\n");
    }
    else if (command == "test") {
      Serial.println("[Command] Testing servo sweep...");
      testServo();
    }
    else {
      Serial.println("[Command] Unknown command. Type 'help' for available commands.");
    }
  }
}

// ============================================
// MANUAL CONTROL FUNCTIONS
// ============================================

// Call this to manually trigger feeding (opens then closes feeder)
void manualFeed() {
  if (manual_feed_stage != MANUAL_FEED_IDLE) {
    Serial.println("[Feed] Manual feed already in progress");
    return;
  }

  Serial.println("[Feed] Manual feed triggered");
  controlFeeder(SERVO_OPEN_ANGLE);
  manual_feed_stage = MANUAL_FEED_OPENING;
  manual_feed_stage_start = millis();
}

void handleManualFeedSequence() {
  unsigned long now = millis();

  if (manual_feed_stage == MANUAL_FEED_OPENING) {
    if (!servo_moving) {
      manual_feed_stage = MANUAL_FEED_HOLDING;
      manual_feed_stage_start = now;
      Serial.println("[Feed] Holding open...");
    }
    return;
  }

  if (manual_feed_stage == MANUAL_FEED_HOLDING) {
    if (now - manual_feed_stage_start >= MANUAL_FEED_HOLD_MS) {
      Serial.println("[Feed] Closing feeder...");
      controlFeeder(SERVO_CLOSE_ANGLE);
      manual_feed_stage = MANUAL_FEED_CLOSING;
      manual_feed_stage_start = now;
    }
    return;
  }

  if (manual_feed_stage == MANUAL_FEED_CLOSING) {
    if (!servo_moving) {
      manual_feed_stage = MANUAL_FEED_IDLE;
      Serial.println("[Feed] Manual feed complete!");
    }
  }
}

// Call this to manually open the feeder
void openFeeder() {
  Serial.println("[Feed] Manually opening feeder");
  controlFeeder(SERVO_OPEN_ANGLE);
  feeder_is_open = true;
}

// Call this to manually close the feeder
void closeFeeder() {
  Serial.println("[Feed] Manually closing feeder");
  controlFeeder(SERVO_CLOSE_ANGLE);
  feeder_is_open = false;
}

// Test servo with full sweep
void testServo() {
  Serial.println("[Test] Starting servo test sweep...");
  
  Serial.println("[Test] Moving to 0°...");
  feederServo.write(0);
  delay(1000);
  
  Serial.println("[Test] Moving to 90°...");
  feederServo.write(90);
  delay(1000);
  
  Serial.println("[Test] Moving to 180°...");
  feederServo.write(180);
  delay(1000);
  
  Serial.println("[Test] Moving to 90°...");
  feederServo.write(90);
  delay(1000);
  
  Serial.println("[Test] Moving back to 0°...");
  feederServo.write(0);
  delay(1000);
  
  Serial.println("[Test] Servo test complete!");
}

// ============================================
// DEBUG AND STATUS
// ============================================
void displayDebugInfo() {
  Serial.println("\n========== SYSTEM STATUS ==========");
  Serial.print("WiFi: ");
  Serial.print(wifi_connected ? "Connected" : "Disconnected");
  if (wifi_connected) {
    Serial.print(" | IP: ");
    Serial.print(WiFi.localIP());
    Serial.print(" | RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.print(" dBm");
  }
  Serial.println();
  
  Serial.print("Feeder: ");
  Serial.print(feeder_is_open ? "OPEN" : "CLOSED");
  Serial.print(" (");
  Serial.print(servo_current_angle);
  Serial.println("°)");
  
  Serial.print("Feed Level: ");
  Serial.print(current_feed_percentage);
  Serial.print("% (");
  Serial.print(current_feed_distance);
  Serial.println(" cm)");
  
  Serial.print("Rain Sensor: ");
  Serial.print(last_rain_value);
  Serial.print(" | ");
  Serial.println(currently_raining ? "RAINING" : "DRY");
  
  Serial.print("Uptime: ");
  Serial.print(millis() / 1000);
  Serial.print(" seconds | Free Heap: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
  Serial.println("===================================\n");
}

String getTimestamp() {
  time_t now;
  struct tm timeinfo;
  time(&now);
  localtime_r(&now, &timeinfo);
  
  char buffer[64];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", &timeinfo);
  return String(buffer);
}

void logEventToDatabase(String eventType, int sensorValue) {
  if (!ensureMySQLConnection()) {
    return;
  }

  String safeEvent = escapeSql(eventType);
  char query[256];
  snprintf(
    query,
    sizeof(query),
    "INSERT INTO %s.%s (event_type, sensor_value, device_id) VALUES ('%s', %d, %d)",
    mysql_database,
    mysql_table,
    safeEvent.c_str(),
    sensorValue,
    DEFAULT_FEEDER_ID
  );

  MySQL_Cursor *cursor = new MySQL_Cursor(&mysql_conn);
  cursor->execute(query);
  delete cursor;
}

String escapeSql(String value) {
  value.replace("'", "''");
  return value;
}
