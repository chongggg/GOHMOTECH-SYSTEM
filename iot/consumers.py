"""
WebSocket Consumers for IoT System

Real-time WebSocket consumers for:
- Sensor data updates
- Device alerts
- Feeding system status
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class SensorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time sensor data updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        await self.channel_layer.group_add(
            'sensors',
            self.channel_name
        )
        await self.accept()
        logger.debug("Sensor WebSocket connected")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            'sensors',
            self.channel_name
        )
        logger.debug("Sensor WebSocket disconnected")
    
    async def sensor_update(self, event):
        """Send sensor update to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'sensor_reading',
            'data': event['data']
        }))


class AlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time alerts.
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        await self.channel_layer.group_add(
            'alerts',
            self.channel_name
        )
        await self.accept()
        logger.debug("Alert WebSocket connected")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            'alerts',
            self.channel_name
        )
        logger.debug("Alert WebSocket disconnected")
    
    async def alert_notification(self, event):
        """Send alert notification to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'alert',
            'data': event['data']
        }))


class FeedingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time feeding system updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        await self.channel_layer.group_add(
            'feeding',
            self.channel_name
        )
        await self.accept()
        logger.debug("Feeding WebSocket connected")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            'feeding',
            self.channel_name
        )
        logger.debug("Feeding WebSocket disconnected")
    
    async def feeding_update(self, event):
        """Send feeding update to WebSocket client"""
        await self.send(text_data=json.dumps({
            'type': 'feeding',
            'data': event['data']
        }))
