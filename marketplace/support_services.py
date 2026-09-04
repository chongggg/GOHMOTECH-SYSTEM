import os

from .models import (
    MarketplaceNotification,
    SupportAttachment,
    UserActivity,
)
from .notification_services import (
    create_marketplace_notification,
    notify_marketplace_staff,
)


def log_user_activity(user, event, description="", *, actor=None, metadata=None):
    return UserActivity.objects.create(
        user=user,
        actor=actor,
        event=event,
        description=description[:500],
        metadata=metadata or {},
    )


def save_support_attachment(message, upload):
    if not upload:
        return None
    attachment = SupportAttachment(
        message=message,
        file=upload,
        original_name=os.path.basename(upload.name)[:255],
        content_type=upload.content_type[:100],
        size=upload.size,
    )
    attachment.full_clean()
    attachment.save()
    return attachment


def notify_ticket_created(ticket):
    notify_marketplace_staff(
        actor=ticket.user,
        notification_type=MarketplaceNotification.SUPPORT,
        title=f"New customer support ticket received: {ticket.ticket_number}",
        message=ticket.subject,
        support_ticket=ticket,
        dedup_key=f"support:{ticket.pk}:created",
    )


def notify_support_reply(ticket, message):
    if message.sender_id == ticket.user_id:
        notify_marketplace_staff(
            actor=message.sender,
            notification_type=MarketplaceNotification.SUPPORT,
            title=f"Customer replied to {ticket.ticket_number}",
            message=message.body,
            support_ticket=ticket,
            dedup_key=f"support-message:{message.pk}",
        )
    else:
        create_marketplace_notification(
            recipient=ticket.user,
            actor=message.sender,
            notification_type=MarketplaceNotification.SUPPORT,
            title=f"Support replied to your ticket {ticket.ticket_number}.",
            message=message.body,
            support_ticket=ticket,
            dedup_key=f"support-message:{message.pk}",
        )


def notify_ticket_status_changed(ticket, actor, previous_status):
    create_marketplace_notification(
        recipient=ticket.user,
        actor=actor,
        notification_type=MarketplaceNotification.SUPPORT,
        title=f"Ticket {ticket.ticket_number} is now {ticket.get_status_display()}",
        message=f"Status changed from {dict(ticket.STATUS_CHOICES).get(previous_status, previous_status)}.",
        support_ticket=ticket,
        dedup_key=(
            f"support:{ticket.pk}:status:{ticket.status}:"
            f"{ticket.updated_at.isoformat()}"
        ),
    )
