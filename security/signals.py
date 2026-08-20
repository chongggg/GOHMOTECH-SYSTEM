"""
Bridge IoT/livestock events into the unified Notification inbox.

Before this bridge the header bell (security.Notification) was only ever fed by
the person-detection path, so it was effectively always empty while real
`iot.Alert` and `MissingGoatAlert` events went unseen. These post_save
receivers raise (or update) exactly one Notification per source event using the
dedup-safe `create_or_update_notification`, and keep the resolved state in sync
so the bell's unread count is accurate.

Design notes:
- **Never raises.** Alert creation is a critical IoT path; a notification
  failure must not break it. Every receiver body is wrapped in try/except.
- **Broadcast only on first creation.** The unread badge is computed from the
  DB (`unread_count()`), which is correct across processes regardless of the
  channel layer; the WebSocket push is a same-process bonus, so we don't
  re-broadcast on every subsequent save.
- **Resolution syncs down.** When the source event is resolved, we resolve its
  notification (which also marks it read), so the badge decrements. We do not
  auto-reopen, matching the inbox's conservative dedup philosophy.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_VALID_SEVERITIES = {'critical', 'high', 'medium', 'low', 'info'}


def _severity(value):
    """Coerce a source severity to a valid Notification severity."""
    return value if value in _VALID_SEVERITIES else 'medium'


def _sync_resolution(notification, is_resolved):
    """Resolve the notification when its source event is resolved."""
    if is_resolved and notification and not notification.is_resolved:
        notification.resolve()


@receiver(post_save, sender='iot.Alert', dispatch_uid='bridge_iot_alert')
def bridge_iot_alert(sender, instance, created, **kwargs):
    """Mirror an iot.Alert into the unified Notification inbox."""
    try:
        from .services import create_or_update_notification

        device_name = getattr(getattr(instance, 'device', None), 'name', '') or 'Device'
        message = getattr(instance, 'message', '') or 'Sensor alert'
        # Keep the headline short; the full message goes in the description.
        title = message.splitlines()[0][:120] if message else 'Device / sensor alert'

        notification, _ = create_or_update_notification(
            title=title,
            description=message,
            severity=_severity(getattr(instance, 'severity', 'medium')),
            notification_type='device_anomaly',
            source=device_name,
            source_object=instance,
            metadata={'alert_id': instance.pk, 'device': device_name},
            broadcast=created,
        )
        _sync_resolution(notification, getattr(instance, 'is_resolved', False))
    except Exception:
        logger.exception("Failed to bridge iot.Alert #%s to notifications",
                         getattr(instance, 'pk', '?'))


@receiver(post_save, sender='iot.MissingGoatAlert', dispatch_uid='bridge_missing_goat_alert')
def bridge_missing_goat_alert(sender, instance, created, **kwargs):
    """Mirror a MissingGoatAlert into the unified Notification inbox."""
    try:
        from .services import create_or_update_notification

        camera_name = getattr(getattr(instance, 'camera', None), 'name', '') or 'Camera'
        title = getattr(instance, 'title', '') or 'Missing goat alert'
        description = getattr(instance, 'message', '') or title

        notification, _ = create_or_update_notification(
            title=title,
            description=description,
            severity=_severity(getattr(instance, 'severity', 'high')),
            notification_type='missing_goat',
            source=camera_name,
            source_object=instance,
            metadata={
                'expected_count': getattr(instance, 'expected_count', None),
                'detected_count': getattr(instance, 'detected_count', None),
                'missing_count': getattr(instance, 'missing_count', None),
            },
            broadcast=created,
        )
        _sync_resolution(notification, getattr(instance, 'is_resolved', False))
    except Exception:
        logger.exception("Failed to bridge MissingGoatAlert #%s to notifications",
                         getattr(instance, 'pk', '?'))
