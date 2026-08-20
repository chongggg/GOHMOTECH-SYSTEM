<?php
// ESP32 Event Logger - Receives POST data and inserts to MySQL
header('Content-Type: text/plain');

// MySQL connection settings
$host = '127.0.0.1';
$port = 3306;
$database = 'goat_monitoring';
$username = 'admin';
$password = 'YOUR_DB_PASSWORD';

// Get POST data
$event_type = isset($_POST['event_type']) ? $_POST['event_type'] : '';
$sensor_value = isset($_POST['sensor_value']) ? intval($_POST['sensor_value']) : 0;
$device_id = isset($_POST['device_id']) ? intval($_POST['device_id']) : 1;

if (empty($event_type)) {
    echo "ERROR: Missing event_type\n";
    exit(1);
}

try {
    // Connect to MySQL
    $pdo = new PDO("mysql:host=$host;port=$port;dbname=$database", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    // Insert event
    $stmt = $pdo->prepare("INSERT INTO feeder_events (event_type, sensor_value, device_id) VALUES (:event, :value, :device)");
    $stmt->execute([
        ':event' => $event_type,
        ':value' => $sensor_value,
        ':device' => $device_id
    ]);
    
    echo "OK: Logged $event_type = $sensor_value\n";
    
} catch (PDOException $e) {
    echo "ERROR: " . $e->getMessage() . "\n";
    exit(1);
}
?>
