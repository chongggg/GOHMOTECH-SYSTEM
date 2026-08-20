"""
Notification Service for Smart Goat Monitoring System

Handles multi-channel notifications:
- WebSocket (real-time push)
- Email (alerts)
- SMS (optional, via Twilio)
- In-app notifications

Integrates with:
- MissingGoatAlert
- NotificationLog
- Django Channels (WebSocket)
"""

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Multi-channel notification service for goat monitoring alerts.
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def send_missing_goat_notification(self, alert, channels: List[str] = None):
        """
        Send missing goat notification through multiple channels.
        
        Args:
            alert: MissingGoatAlert instance
            channels: List of channels to use ['websocket', 'email', 'sms']
                     If None, uses all enabled channels
        """
        if channels is None:
            channels = self._get_enabled_channels()
        
        # Prepare notification data
        notification_data = self._prepare_missing_goat_data(alert)
        
        results = {}
        
        # Send through each channel
        if 'websocket' in channels:
            results['websocket'] = self._send_websocket(notification_data, alert)
        
        if 'email' in channels:
            results['email'] = self._send_email(notification_data, alert)
        
        if 'sms' in channels:
            results['sms'] = self._send_sms(notification_data, alert)
        
        logger.info(f"Sent missing goat notification for alert #{alert.id}: {results}")
        
        return results
    
    def send_goat_detected_notification(self, goat_id: str, is_new: bool = False):
        """
        Send notification when a goat is detected.
        
        Args:
            goat_id: ID of detected goat
            is_new: Whether this is a newly registered goat
        """
        notification_data = {
            'type': 'goat_detected',
            'goat_id': goat_id,
            'is_new': is_new,
            'timestamp': timezone.now().isoformat(),
            'message': f"New goat auto-registered: {goat_id}" if is_new else f"Goat detected: {goat_id}"
        }
        
        return self._send_websocket(notification_data)
    
    def send_door_status_notification(self, action: str, metadata: Dict = None):
        """
        Send notification about door status change.
        
        Args:
            action: 'closed', 'held_open', 'opened'
            metadata: Additional context
        """
        notification_data = {
            'type': 'door_status',
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'metadata': metadata or {}
        }
        
        return self._send_websocket(notification_data)
    
    def send_all_goats_present_notification(self, detected_count: int):
        """
        Send positive notification when all goats are accounted for.
        
        Args:
            detected_count: Number of goats detected
        """
        notification_data = {
            'type': 'all_goats_present',
            'detected_count': detected_count,
            'timestamp': timezone.now().isoformat(),
            'message': f"✅ All {detected_count} goats are present. Door secured.",
            'severity': 'info'
        }
        
        return self._send_websocket(notification_data)
    
    def _prepare_missing_goat_data(self, alert) -> Dict:
        """
        Prepare notification data from MissingGoatAlert.
        
        Args:
            alert: MissingGoatAlert instance
            
        Returns:
            Dict with notification data
        """
        missing_goat_ids = list(alert.missing_goats.values_list('goat_id', flat=True))
        
        return {
            'type': 'missing_goat_alert',
            'alert_id': alert.id,
            'missing_count': alert.missing_count,
            'detected_count': alert.detected_count,
            'expected_count': alert.expected_count,
            'missing_goats': missing_goat_ids,
            'severity': alert.severity,
            'description': alert.description,
            'timestamp': alert.detected_at.isoformat(),
            'camera': alert.camera.name if alert.camera else 'Unknown',
            'snapshot_url': alert.snapshot_image.url if alert.snapshot_image else None
        }
    
    def _send_websocket(self, notification_data: Dict, alert=None) -> Dict:
        """
        Send notification via WebSocket to connected clients.
        
        Args:
            notification_data: Data to send
            alert: Optional MissingGoatAlert instance for logging
            
        Returns:
            Dict with result status
        """
        try:
            if not self.channel_layer:
                logger.warning("Channel layer not configured")
                return {'status': 'skipped', 'message': 'Channel layer not configured'}
            
            # Send to alerts group
            async_to_sync(self.channel_layer.group_send)(
                'alerts',
                {
                    'type': 'alert_notification',
                    'data': notification_data
                }
            )
            
            # Log notification
            if alert:
                self._log_notification(
                    alert=alert,
                    channel='websocket',
                    status='sent',
                    notification_data=notification_data
                )
            
            logger.info(f"WebSocket notification sent: {notification_data['type']}")
            
            return {'status': 'success', 'channel': 'websocket'}
            
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
            
            if alert:
                self._log_notification(
                    alert=alert,
                    channel='websocket',
                    status='failed',
                    error_message=str(e)
                )
            
            return {'status': 'error', 'channel': 'websocket', 'error': str(e)}
    
    def _send_email(self, notification_data: Dict, alert) -> Dict:
        """
        Send notification via email.
        
        Args:
            notification_data: Data to send
            alert: MissingGoatAlert instance
            
        Returns:
            Dict with result status
        """
        try:
            # Check if email is configured
            if not getattr(settings, 'EMAIL_HOST', None):
                logger.info("Email not configured, skipping")
                return {'status': 'skipped', 'message': 'Email not configured'}
            
            # Get recipient email
            recipient_email = getattr(settings, 'ADMIN_EMAIL', None)
            if not recipient_email:
                logger.warning("No admin email configured")
                return {'status': 'skipped', 'message': 'No recipient email'}
            
            # Prepare email content
            subject = self._format_email_subject(notification_data)
            message = self._format_email_message(notification_data)
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False
            )
            
            # Log notification
            self._log_notification(
                alert=alert,
                channel='email',
                status='sent',
                recipient=recipient_email,
                notification_data=notification_data
            )
            
            logger.info(f"Email notification sent to {recipient_email}")
            
            return {'status': 'success', 'channel': 'email', 'recipient': recipient_email}
            
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            
            self._log_notification(
                alert=alert,
                channel='email',
                status='failed',
                error_message=str(e)
            )
            
            return {'status': 'error', 'channel': 'email', 'error': str(e)}
    
    def _send_sms(self, notification_data: Dict, alert) -> Dict:
        """
        Send notification via SMS (Twilio).
        
        Args:
            notification_data: Data to send
            alert: MissingGoatAlert instance
            
        Returns:
            Dict with result status
        """
        try:
            # Check if Twilio is configured
            twilio_enabled = getattr(settings, 'TWILIO_ENABLED', False)
            
            if not twilio_enabled:
                logger.info("SMS (Twilio) not configured, skipping")
                return {'status': 'skipped', 'message': 'SMS not configured'}
            
            # Import Twilio (only if enabled)
            from twilio.rest import Client
            
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            from_phone = settings.TWILIO_PHONE_NUMBER
            to_phone = settings.ADMIN_PHONE_NUMBER
            
            # Create Twilio client
            client = Client(account_sid, auth_token)
            
            # Prepare SMS message
            message_body = self._format_sms_message(notification_data)
            
            # Send SMS
            message = client.messages.create(
                body=message_body,
                from_=from_phone,
                to=to_phone
            )
            
            # Log notification
            self._log_notification(
                alert=alert,
                channel='sms',
                status='sent',
                recipient=to_phone,
                notification_data=notification_data
            )
            
            logger.info(f"SMS notification sent to {to_phone}")
            
            return {'status': 'success', 'channel': 'sms', 'message_sid': message.sid}
            
        except ImportError:
            logger.warning("Twilio library not installed")
            return {'status': 'skipped', 'message': 'Twilio library not installed'}
            
        except Exception as e:
            logger.error(f"SMS notification failed: {e}")
            
            self._log_notification(
                alert=alert,
                channel='sms',
                status='failed',
                error_message=str(e)
            )
            
            return {'status': 'error', 'channel': 'sms', 'error': str(e)}
    
    def _format_email_subject(self, notification_data: Dict) -> str:
        """Format email subject line"""
        severity = notification_data.get('severity', 'info').upper()
        
        if notification_data['type'] == 'missing_goat_alert':
            return f"[{severity}] Missing Goat Alert - {notification_data['missing_count']} goat(s) missing"
        else:
            return "Goat Monitoring System Alert"
    
    def _format_email_message(self, notification_data: Dict) -> str:
        """Format email message body"""
        if notification_data['type'] == 'missing_goat_alert':
            missing_goats = ", ".join(notification_data['missing_goats'])
            
            message = f"""
Smart Goat Monitoring System - Missing Goat Alert

SEVERITY: {notification_data['severity'].upper()}

{notification_data['description']}

Details:
- Detected: {notification_data['detected_count']} goat(s)
- Expected: {notification_data['expected_count']} goat(s)
- Missing: {notification_data['missing_count']} goat(s)
- Missing IDs: {missing_goats}
- Camera: {notification_data['camera']}
- Time: {notification_data['timestamp']}

The automatic door has been held open to allow missing goats to return.

Please check the goat house and verify all goats are safe.

---
Smart Goat Monitoring System
Automated Alert
            """
            return message.strip()
        
        return notification_data.get('message', 'System notification')
    
    def _format_sms_message(self, notification_data: Dict) -> str:
        """Format SMS message (keep it short, under 160 chars)"""
        if notification_data['type'] == 'missing_goat_alert':
            missing_goats = ", ".join(notification_data['missing_goats'][:3])  # Limit to 3 IDs
            return f"⚠️ {notification_data['missing_count']} goat(s) missing: {missing_goats}. Door held open. Check goat house."
        
        return notification_data.get('message', 'Goat monitoring alert')[:160]
    
    def _log_notification(self, alert, channel: str, status: str, 
                         recipient: str = None, notification_data: Dict = None,
                         error_message: str = None):
        """
        Log notification to NotificationLog model.
        
        Args:
            alert: MissingGoatAlert instance
            channel: 'websocket', 'email', 'sms'
            status: 'sent', 'failed', 'skipped'
            recipient: Email or phone number
            notification_data: Full notification data
            error_message: Error message if failed
        """
        try:
            from iot.goat_models import NotificationLog
            
            notification_type = notification_data.get('type', 'unknown') if notification_data else 'unknown'
            severity = notification_data.get('severity', 'info') if notification_data else 'info'
            
            NotificationLog.objects.create(
                alert=alert,
                notification_type=notification_type,
                channel=channel,
                recipient=recipient or 'broadcast',
                title=self._format_email_subject(notification_data) if notification_data else 'Notification',
                message=notification_data.get('message', '') if notification_data else '',
                severity=severity,
                is_sent=(status == 'sent'),
                sent_at=timezone.now() if status == 'sent' else None,
                error_message=error_message
            )
            
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    def _get_enabled_channels(self) -> List[str]:
        """
        Get list of enabled notification channels from settings.
        
        Returns:
            List of enabled channels
        """
        channels = ['websocket']  # Always enabled
        
        if getattr(settings, 'EMAIL_HOST', None):
            channels.append('email')
        
        if getattr(settings, 'TWILIO_ENABLED', False):
            channels.append('sms')
        
        return channels


# Global notification service instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get or create global notification service instance"""
    global _notification_service
    
    if _notification_service is None:
        _notification_service = NotificationService()
    
    return _notification_service


def send_missing_goat_alert(alert, channels: List[str] = None) -> Dict:
    """
    Convenience function to send missing goat alert.
    
    Args:
        alert: MissingGoatAlert instance
        channels: List of channels to use (None = all enabled)
        
    Returns:
        Dict with results from each channel
    """
    service = get_notification_service()
    return service.send_missing_goat_notification(alert, channels)


def send_goat_detected(goat_id: str, is_new: bool = False) -> Dict:
    """
    Convenience function to send goat detected notification.
    
    Args:
        goat_id: ID of detected goat
        is_new: Whether this is a newly registered goat
        
    Returns:
        Dict with result
    """
    service = get_notification_service()
    return service.send_goat_detected_notification(goat_id, is_new)


def send_door_status(action: str, metadata: Dict = None) -> Dict:
    """
    Convenience function to send door status notification.
    
    Args:
        action: 'closed', 'held_open', 'opened'
        metadata: Additional context
        
    Returns:
        Dict with result
    """
    service = get_notification_service()
    return service.send_door_status_notification(action, metadata)
