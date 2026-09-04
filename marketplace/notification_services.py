from django.contrib.auth import get_user_model

from .models import MarketplaceNotification


def create_marketplace_notification(
    *,
    recipient,
    notification_type,
    title,
    message="",
    actor=None,
    listing=None,
    conversation=None,
    reservation=None,
    report=None,
    support_ticket=None,
    dedup_key=None,
):
    """Create one private in-app marketplace notification.

    Marketplace events deliberately do not enter the security notification/SMS
    funnel. Ordinary messages and transaction updates must not consume SMS
    credits or appear in the client's global farm alert inbox.
    """
    if not recipient or not getattr(recipient, "is_active", False):
        return None, False
    if actor and recipient.pk == actor.pk:
        return None, False
    values = {
        "recipient": recipient,
        "notification_type": notification_type,
        "title": title[:180],
        "message": message[:1000],
        "actor": actor if getattr(actor, "is_authenticated", False) else None,
        "listing": listing,
        "conversation": conversation,
        "reservation": reservation,
        "report": report,
        "support_ticket": support_ticket,
    }
    if dedup_key:
        notification, created = MarketplaceNotification.objects.get_or_create(
            dedup_key=dedup_key[:180],
            defaults=values,
        )
        return notification, created
    return MarketplaceNotification.objects.create(**values), True


def notify_marketplace_staff(**kwargs):
    User = get_user_model()
    notifications = []
    actor = kwargs.get("actor")
    for staff_user in User.objects.filter(is_active=True, is_staff=True).iterator():
        if actor and staff_user.pk == actor.pk:
            continue
        per_user = dict(kwargs)
        base_key = per_user.get("dedup_key")
        if base_key:
            per_user["dedup_key"] = f"{base_key}:staff:{staff_user.pk}"
        notification, created = create_marketplace_notification(
            recipient=staff_user,
            **per_user,
        )
        if notification:
            notifications.append((notification, created))
    return notifications
