"""
WebSocket Consumers for ML Models

Real-time WebSocket consumers for:
- Goat detection updates
- Model status updates
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class DetectionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time detection updates.
    
    Clients can subscribe to this to receive instant notifications
    when new goats are detected.
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        # Join detection group
        await self.channel_layer.group_add(
            'detections',
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave detection group
        await self.channel_layer.group_discard(
            'detections',
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            json.loads(text_data)
            # Handle client requests if needed
            # For now, this is mostly one-way (server -> client)
        except json.JSONDecodeError:
            pass
    
    async def detection_update(self, event):
        """
        Send detection update to WebSocket client.
        
        This is called when a message is sent to the 'detections' group.
        """
        await self.send(text_data=json.dumps({
            'type': 'detection',
            'data': event['data']
        }))
