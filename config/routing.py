"""
WebSocket URL Routing for Django Channels

Defines WebSocket endpoints for real-time updates:
- /ws/detections/ : Real-time goat detection updates
- /ws/sensors/ : Real-time sensor data
- /ws/alerts/ : Real-time alerts
- /ws/feeding/ : Real-time feeding status
"""

from django.urls import re_path
from iot import consumers as iot_consumers
from ml_models import consumers as ml_consumers

websocket_urlpatterns = [
    # ML Detection WebSocket
    re_path(r'ws/detections/$', ml_consumers.DetectionConsumer.as_asgi()),
    
    # IoT Sensor WebSocket
    re_path(r'ws/sensors/$', iot_consumers.SensorConsumer.as_asgi()),
    
    # Alerts WebSocket
    re_path(r'ws/alerts/$', iot_consumers.AlertConsumer.as_asgi()),
    
    # Feeding WebSocket
    re_path(r'ws/feeding/$', iot_consumers.FeedingConsumer.as_asgi()),
]
