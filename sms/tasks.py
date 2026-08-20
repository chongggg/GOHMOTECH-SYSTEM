"""
Celery tasks for the SMS subsystem.

Two beat-driven tasks run every minute and mirror the proven scheduling shape of
``iot.tasks.execute_scheduled_feeding`` (local time, minute-precision match,
0=Sunday day arithmetic):

  * ``send_daily_summary``  — fires the once-a-day digest at the operator's time.
  * ``send_due_reminders``  — fires any reminder whose time/day matches now.

Plus two event-driven tasks:

  * ``send_alert_sms``      — enqueued by the security notification funnel when a
                              new notification is raised (task #6).
  * ``send_test_sms``       — invoked by the Test SMS button.

All actual sending goes through ``sms.services.send_sms`` so every message is
logged uniformly. Operator toggles are read from the ``SmsSettings`` DB
singleton at run time (never from per-process settings), so a change made in the
UI is honoured by the worker on its next tick.
"""

import logging

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Max characters we let an alert body reach before truncating, to keep an alert
# SMS to a small, predictable number of segments.
ALERT_MAX_CHARS = 300


@shared_task
def send_daily_summary():
    """Send the daily summary SMS if it is due this minute.

    Runs every minute via Celery Beat. Sends only when SMS + daily summary are
    enabled and the current local HH:MM equals the configured ``daily_time``.
    Deduplicated so a restart or overlapping tick cannot double-send: at most one
    'daily' log per calendar day.
    """
    from .models import SmsLog, SmsSettings
    from .services import send_sms
    from .summaries import build_daily_summary_text

    settings_obj = SmsSettings.get_config()
    if not (settings_obj.enabled and settings_obj.daily_enabled):
        return "Daily summary disabled"

    now = timezone.localtime(timezone.now())
    target = settings_obj.daily_time
    if not (now.hour == target.hour and now.minute == target.minute):
        return "Not the scheduled minute"

    # One per day, regardless of how many times this minute is polled. Compared
    # against local midnight with a plain datetime lookup (not __date) so it does
    # not depend on MySQL timezone tables, which are not loaded on this install.
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if SmsLog.objects.filter(sms_type='daily', created_at__gte=day_start).exists():
        return "Daily summary already sent today"

    log = send_sms(message=build_daily_summary_text(), sms_type='daily')
    return f"Daily summary: {log.status if log else 'skipped'}"


@shared_task
def send_due_reminders():
    """Send any active reminders whose schedule matches the current minute.

    Runs every minute via Celery Beat. Mirrors ``execute_scheduled_feeding``:
    local-time minute match plus 0=Sunday day-of-week filtering. Per-reminder,
    per-minute dedup prevents a double-send within the same minute.
    """
    from .models import SmsLog, SmsReminder, SmsSettings
    from .services import send_sms

    settings_obj = SmsSettings.get_config()
    if not (settings_obj.enabled and settings_obj.reminders_enabled):
        return "Reminders disabled"

    now = timezone.localtime(timezone.now())
    current_time = now.time().replace(second=0, microsecond=0)
    current_day = (now.weekday() + 1) % 7  # 0=Sunday, matching the model

    reminders = SmsReminder.objects.filter(
        is_active=True, schedule_time=current_time)

    sent_count = 0
    for reminder in reminders:
        days = reminder.days_of_week
        if days and current_day not in days:
            continue

        # Dedup: skip if this reminder already sent within the current minute.
        minute_start = now.replace(second=0, microsecond=0)
        already = SmsLog.objects.filter(
            sms_type='reminder', reminder=reminder,
            created_at__gte=minute_start,
        ).exists()
        if already:
            continue

        log = send_sms(
            message=reminder.message, sms_type='reminder', reminder=reminder)
        if log is not None:
            sent_count += 1

    return f"Sent {sent_count} reminder(s)"


def _format_alert_text(notification):
    """Build a compact alert SMS body from a Notification (<= ALERT_MAX_CHARS)."""
    prefix = f"[{notification.get_severity_display()}] "
    body = notification.title
    if notification.description:
        body += f" - {notification.description}"
    if notification.source:
        body += f" ({notification.source})"
    text = prefix + body
    if len(text) > ALERT_MAX_CHARS:
        text = text[:ALERT_MAX_CHARS - 1].rstrip() + "…"
    return text


@shared_task
def send_alert_sms(notification_id):
    """Send an SMS for a security Notification, if the rules allow it.

    Re-checks ``SmsSettings.should_send_alert`` at send time (the toggle may have
    changed since the notification was raised) and applies a per-type cooldown
    via the shared DB cache so a burst of the same alert type does not spam SMS.
    """
    from .models import SmsSettings
    from .services import send_sms
    from security.models import Notification

    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        logger.warning("send_alert_sms: notification %s not found", notification_id)
        return "Notification not found"

    settings_obj = SmsSettings.get_config()
    if not settings_obj.should_send_alert(
            notification.notification_type, notification.severity):
        return "Alert not eligible for SMS"

    # Per-type cooldown, shared across processes via the DB cache.
    cooldown = settings_obj.alert_cooldown_minutes or 0
    cache_key = f"sms_alert_cooldown:{notification.notification_type}"
    if cooldown and cache.get(cache_key):
        logger.info("send_alert_sms: cooldown active for %s",
                    notification.notification_type)
        return "Cooldown active"

    log = send_sms(
        message=_format_alert_text(notification),
        sms_type='alert',
        notification=notification,
    )

    # Only start the cooldown once a message was actually attempted+sent.
    if cooldown and log is not None and log.status == 'sent':
        cache.set(cache_key, True, timeout=cooldown * 60)

    return f"Alert SMS: {log.status if log else 'skipped'}"


@shared_task
def send_test_sms(number=None):
    """Send a test SMS to verify configuration (Test SMS button).

    Uses ``force=True`` so an operator can confirm credentials/recipient work
    before flipping the master switch on.
    """
    from .services import send_sms

    now = timezone.localtime(timezone.now())
    message = (
        f"GoHMoTech test SMS — configuration OK. Sent {now:%Y-%m-%d %H:%M}."
    )
    log = send_sms(message=message, sms_type='test', number=number, force=True)
    return f"Test SMS: {log.status if log else 'skipped'}"
