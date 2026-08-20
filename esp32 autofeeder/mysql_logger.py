#!/usr/bin/env python3
"""
ESP32 MySQL Logger Server
Receives HTTP POST requests from ESP32 and logs to MySQL
Run with: python mysql_logger.py
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import mysql.connector
from urllib.parse import parse_qs
import json

# MySQL Configuration
MYSQL_HOST = '127.0.0.1'
MYSQL_PORT = 3306
MYSQL_USER = 'admin'
MYSQL_PASSWORD = 'YOUR_DB_PASSWORD'
MYSQL_DATABASE = 'goat_monitoring'

class LoggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests from ESP32"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        # Parse form data
        params = parse_qs(post_data)
        event_type = params.get('event_type', [''])[0]
        sensor_value = int(params.get('sensor_value', [0])[0])
        device_id = int(params.get('device_id', [1])[0])
        
        print(f"[Received] Event: {event_type}, Value: {sensor_value}, Device: {device_id}")
        
        # Insert to MySQL
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor()
            
            query = """INSERT INTO feeder_events (event_type, sensor_value, device_id) 
                       VALUES (%s, %s, %s)"""
            cursor.execute(query, (event_type, sensor_value, device_id))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            print(f"[MySQL] ✓ Inserted successfully")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode())
            
        except Exception as e:
            print(f"[MySQL] ✗ Error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

def run_server(port=8080):
    """Start the HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, LoggerHandler)
    print(f"""
╔════════════════════════════════════════════════════╗
║     ESP32 MySQL Logger Server                      ║
╠════════════════════════════════════════════════════╣
║  Status: Running on port {port}                       ║
║  Endpoint: http://192.168.137.1:{port}/log            ║
║  MySQL: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}     ║
╚════════════════════════════════════════════════════╝

Waiting for ESP32 events...
Press Ctrl+C to stop
""")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        httpd.server_close()

if __name__ == '__main__':
    run_server(8080)
