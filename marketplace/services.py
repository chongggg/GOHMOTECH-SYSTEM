from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Conversation,
    Favorite,
    MarketplaceActivity,
    MarketplaceListing,
    MarketplaceNotification,
    Reservation,
    SellerProfile,
)
from .notification_services import create_marketplace_notification
from .scopes import can_manage_listing
from .support_services import log_user_activity


def log_activity(listing, actor, action, description="", reservation=None, metadata=None):
    return MarketplaceActivity.objects.create(
        listing=listing,
        reservation=reservation,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        description=description,
        metadata=metadata or {},
    )


def _is_listing_seller(actor, listing):
    return can_manage_listing(actor, listing)


def _seller_can_transact(actor, listing):
    if not _is_listing_seller(actor, listing):
        return False
    from .auth import can_manage_farm

    if can_manage_farm(actor):
        return True
    profile = getattr(actor, "seller_profile", None)
    return bool(profile and profile.status == SellerProfile.APPROVED)


def _validate_future(value, label):
    if not value or value <= timezone.now():
        raise ValidationError(f"{label} must be in the future.")


@transaction.atomic
def request_reservation(listing_id, buyer, conversation):
    listing = (
        MarketplaceListing.objects.select_for_update()
        .select_related("goat", "seller__seller_profile")
        .get(pk=listing_id)
    )
    if listing.status != MarketplaceListing.AVAILABLE:
        raise ValidationError("This goat is no longer available.")
    if listing.seller_id == buyer.id:
        raise ValidationError("You cannot reserve your own goat listing.")
    if listing.goat.status != "active" or not listing.goat.is_active:
        raise ValidationError("This goat is no longer active in inventory.")
    profile = getattr(listing.seller, "seller_profile", None)
    if not (listing.seller.is_staff or listing.seller.is_superuser) and not (
        profile and profile.status == SellerProfile.APPROVED
    ):
        raise ValidationError("This seller is not currently accepting reservations.")
    if (
        conversation.listing_id != listing.id
        or conversation.buyer_id != buyer.id
        or conversation.status != Conversation.OPEN
    ):
        raise ValidationError("An open inquiry for this goat is required.")
    if Reservation.objects.filter(
        listing=listing,
        buyer=buyer,
        status__in=[Reservation.PENDING, Reservation.ACCEPTED],
    ).exists():
        raise ValidationError("You already have an active reservation request for this goat.")

    reservation = Reservation(
        listing=listing,
        buyer=buyer,
        conversation=conversation,
        agreed_price=listing.price,
        status=Reservation.PENDING,
    )
    reservation.full_clean()
    reservation.save()
    log_user_activity(
        buyer,
        "reservation_created",
        f"Created reservation request for {listing.goat.goat_id}.",
        metadata={"reservation_id": reservation.pk, "listing_id": listing.pk},
    )
    log_activity(
        listing,
        buyer,
        "reservation_requested",
        f"Reservation requested by {buyer.username}.",
        reservation=reservation,
    )
    create_marketplace_notification(
        recipient=listing.seller,
        actor=buyer,
        notification_type=MarketplaceNotification.RESERVATION,
        title=f"Reservation request for {listing.goat.goat_id}",
        message=f"{buyer.get_full_name() or buyer.username} requested to reserve your goat.",
        listing=listing,
        conversation=conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:requested",
    )
    return reservation


# Temporary compatibility name for code integrating with the original service.
reserve_listing = request_reservation


@transaction.atomic
def accept_reservation(reservation_id, actor, expires_at=None, pickup_location=""):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__goat", "listing__seller__seller_profile", "buyer")
        .get(pk=reservation_id)
    )
    listing = MarketplaceListing.objects.select_for_update().get(pk=reservation.listing_id)
    if not _seller_can_transact(actor, reservation.listing):
        raise PermissionDenied("Only the approved listing seller can accept this request.")
    if reservation.status != Reservation.PENDING:
        raise ValidationError("Only a pending reservation request can be accepted.")
    if listing.status != MarketplaceListing.AVAILABLE:
        raise ValidationError("This goat has already been reserved or is unavailable.")
    if reservation.listing.goat.status != "active" or not reservation.listing.goat.is_active:
        raise ValidationError("This goat is no longer active in inventory.")

    now = timezone.now()
    if expires_at is None:
        expires_at = now + timedelta(
            hours=getattr(settings, "MARKETPLACE_RESERVATION_HOLD_HOURS", 72)
        )
    _validate_future(expires_at, "Reservation expiration")

    reservation.status = Reservation.ACCEPTED
    reservation.accepted_at = now
    reservation.expires_at = expires_at
    reservation.pickup_location = pickup_location.strip()[:500]
    reservation.full_clean()
    reservation.save(
        update_fields=[
            "status",
            "accepted_at",
            "expires_at",
            "pickup_location",
        ]
    )
    listing.status = MarketplaceListing.RESERVED
    listing.save(update_fields=["status", "updated_at"])

    competing = list(
        Reservation.objects.select_for_update()
        .select_related("buyer")
        .filter(listing_id=listing.pk, status=Reservation.PENDING)
        .exclude(pk=reservation.pk)
    )
    Reservation.objects.filter(pk__in=[item.pk for item in competing]).update(
        status=Reservation.REJECTED,
        rejected_at=now,
        rejected_by=actor,
        rejection_reason="Another reservation request was accepted first.",
    )
    log_activity(
        listing,
        actor,
        "reservation_accepted",
        f"Accepted reservation for {reservation.buyer.username}.",
        reservation=reservation,
        metadata={"expires_at": expires_at.isoformat()},
    )
    create_marketplace_notification(
        recipient=reservation.buyer,
        actor=actor,
        notification_type=MarketplaceNotification.RESERVATION,
        title=f"Reservation accepted for {reservation.listing.goat.goat_id}",
        message="The seller accepted your request. Arrange pickup before the hold expires.",
        listing=reservation.listing,
        conversation=reservation.conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:accepted",
    )
    for competing_reservation in competing:
        create_marketplace_notification(
            recipient=competing_reservation.buyer,
            actor=actor,
            notification_type=MarketplaceNotification.RESERVATION,
            title=f"Reservation unavailable for {reservation.listing.goat.goat_id}",
            message="Another reservation request was accepted first.",
            listing=reservation.listing,
            conversation=competing_reservation.conversation,
            reservation=competing_reservation,
            dedup_key=f"reservation:{competing_reservation.pk}:competing-rejected",
        )
    return reservation


@transaction.atomic
def reject_reservation(reservation_id, actor, reason=""):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__seller__seller_profile")
        .get(pk=reservation_id)
    )
    if not _seller_can_transact(actor, reservation.listing):
        raise PermissionDenied("Only the approved listing seller can reject this request.")
    if reservation.status != Reservation.PENDING:
        raise ValidationError("Only a pending reservation request can be rejected.")
    reservation.status = Reservation.REJECTED
    reservation.rejected_at = timezone.now()
    reservation.rejected_by = actor
    reservation.rejection_reason = reason.strip()
    reservation.save(
        update_fields=["status", "rejected_at", "rejected_by", "rejection_reason"]
    )
    log_activity(
        reservation.listing,
        actor,
        "reservation_rejected",
        reservation.rejection_reason or "Reservation request rejected.",
        reservation=reservation,
    )
    create_marketplace_notification(
        recipient=reservation.buyer,
        actor=actor,
        notification_type=MarketplaceNotification.RESERVATION,
        title=f"Reservation request declined for {reservation.listing.goat.goat_id}",
        message=reservation.rejection_reason or "The seller declined your reservation request.",
        listing=reservation.listing,
        conversation=reservation.conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:rejected",
    )
    return reservation


@transaction.atomic
def cancel_reservation(reservation_id, actor, reason=""):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__goat", "listing__seller__seller_profile")
        .get(pk=reservation_id)
    )
    listing = MarketplaceListing.objects.select_for_update().get(pk=reservation.listing_id)
    authorized = (
        reservation.buyer_id == getattr(actor, "pk", None)
        or _seller_can_transact(actor, reservation.listing)
        or getattr(actor, "is_staff", False)
    )
    if not authorized:
        raise PermissionDenied("You cannot cancel this reservation.")
    if reservation.status not in {Reservation.PENDING, Reservation.ACCEPTED}:
        raise ValidationError("Only a pending or accepted reservation can be cancelled.")

    was_accepted = reservation.status == Reservation.ACCEPTED
    reservation.status = Reservation.CANCELLED
    reservation.cancelled_at = timezone.now()
    reservation.cancelled_by = actor
    reservation.cancellation_reason = reason.strip()
    reservation.save(
        update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason"]
    )
    if was_accepted and listing.status == MarketplaceListing.RESERVED:
        listing.status = MarketplaceListing.AVAILABLE
        listing.save(update_fields=["status", "updated_at"])
    log_activity(
        listing,
        actor,
        "reservation_cancelled",
        reservation.cancellation_reason
        or "Reservation cancelled; listing returned to available when applicable.",
        reservation=reservation,
    )
    recipients = []
    if reservation.buyer_id != getattr(actor, "pk", None):
        recipients.append(reservation.buyer)
    if reservation.listing.seller_id != getattr(actor, "pk", None):
        recipients.append(reservation.listing.seller)
    for recipient in recipients:
        create_marketplace_notification(
            recipient=recipient,
            actor=actor,
            notification_type=MarketplaceNotification.RESERVATION,
            title=f"Reservation cancelled for {reservation.listing.goat.goat_id}",
            message=reservation.cancellation_reason or "The reservation was cancelled.",
            listing=reservation.listing,
            conversation=reservation.conversation,
            reservation=reservation,
            dedup_key=f"reservation:{reservation.pk}:cancelled:{recipient.pk}",
        )
    return reservation


@transaction.atomic
def expire_reservation(reservation_id):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing")
        .get(pk=reservation_id)
    )
    listing = MarketplaceListing.objects.select_for_update().get(pk=reservation.listing_id)
    if (
        reservation.status != Reservation.ACCEPTED
        or not reservation.expires_at
        or reservation.expires_at > timezone.now()
    ):
        return False
    reservation.status = Reservation.EXPIRED
    reservation.save(update_fields=["status"])
    if listing.status == MarketplaceListing.RESERVED:
        listing.status = MarketplaceListing.AVAILABLE
        listing.save(update_fields=["status", "updated_at"])
    log_activity(
        listing,
        None,
        "reservation_expired",
        "Reservation hold expired; listing returned to available.",
        reservation=reservation,
    )
    for recipient in (reservation.buyer, reservation.listing.seller):
        create_marketplace_notification(
            recipient=recipient,
            notification_type=MarketplaceNotification.RESERVATION,
            title=f"Reservation expired for {reservation.listing.goat.goat_id}",
            message="The reservation hold expired and the listing is available again.",
            listing=reservation.listing,
            conversation=reservation.conversation,
            reservation=reservation,
            dedup_key=f"reservation:{reservation.pk}:expired:{recipient.pk}",
        )
    return True


def expire_due_reservations():
    due_ids = list(
        Reservation.objects.filter(
            status=Reservation.ACCEPTED,
            expires_at__isnull=False,
            expires_at__lte=timezone.now(),
        ).values_list("pk", flat=True)
    )
    return sum(bool(expire_reservation(pk)) for pk in due_ids)


@transaction.atomic
def request_pickup(reservation_id, buyer, pickup_datetime, notes=""):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing")
        .get(pk=reservation_id)
    )
    if reservation.buyer_id != buyer.pk:
        raise PermissionDenied("Only this reservation's buyer can request pickup.")
    if reservation.status != Reservation.ACCEPTED:
        raise ValidationError("Pickup can be arranged only after the seller accepts.")
    _validate_future(pickup_datetime, "Pickup")
    reservation.pickup_datetime = pickup_datetime
    reservation.pickup_notes = notes.strip()
    reservation.pickup_status = Reservation.PICKUP_REQUESTED
    reservation.pickup_proposed_by = buyer
    reservation.pickup_confirmed_by = None
    reservation.pickup_confirmed_at = None
    reservation.save(
        update_fields=[
            "pickup_datetime",
            "pickup_notes",
            "pickup_status",
            "pickup_proposed_by",
            "pickup_confirmed_by",
            "pickup_confirmed_at",
        ]
    )
    log_activity(
        reservation.listing,
        buyer,
        "pickup_requested",
        f"Pickup requested for {timezone.localtime(pickup_datetime):%Y-%m-%d %H:%M}.",
        reservation=reservation,
    )
    create_marketplace_notification(
        recipient=reservation.listing.seller,
        actor=buyer,
        notification_type=MarketplaceNotification.PICKUP,
        title=f"Pickup proposed for {reservation.listing.goat.goat_id}",
        message=f"Buyer proposed {timezone.localtime(pickup_datetime):%b %d, %Y at %I:%M %p}.",
        listing=reservation.listing,
        conversation=reservation.conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:pickup-request:{pickup_datetime.isoformat()}",
    )
    return reservation


@transaction.atomic
def suggest_pickup(reservation_id, actor, pickup_datetime, notes="", pickup_location=""):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__seller__seller_profile")
        .get(pk=reservation_id)
    )
    if not _seller_can_transact(actor, reservation.listing):
        raise PermissionDenied("Only the approved listing seller can suggest pickup.")
    if reservation.status != Reservation.ACCEPTED:
        raise ValidationError("Pickup can be arranged only for an accepted reservation.")
    _validate_future(pickup_datetime, "Pickup")
    reservation.pickup_datetime = pickup_datetime
    reservation.pickup_notes = notes.strip()
    reservation.pickup_location = pickup_location.strip()[:500]
    reservation.pickup_status = Reservation.PICKUP_SUGGESTED
    reservation.pickup_proposed_by = actor
    reservation.pickup_confirmed_by = None
    reservation.pickup_confirmed_at = None
    reservation.save(
        update_fields=[
            "pickup_datetime",
            "pickup_notes",
            "pickup_location",
            "pickup_status",
            "pickup_proposed_by",
            "pickup_confirmed_by",
            "pickup_confirmed_at",
        ]
    )
    log_activity(
        reservation.listing,
        actor,
        "pickup_suggested",
        f"Seller suggested pickup for {timezone.localtime(pickup_datetime):%Y-%m-%d %H:%M}.",
        reservation=reservation,
    )
    create_marketplace_notification(
        recipient=reservation.buyer,
        actor=actor,
        notification_type=MarketplaceNotification.PICKUP,
        title=f"Seller suggested pickup for {reservation.listing.goat.goat_id}",
        message=f"Review the suggested schedule for {timezone.localtime(pickup_datetime):%b %d, %Y at %I:%M %p}.",
        listing=reservation.listing,
        conversation=reservation.conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:pickup-suggest:{pickup_datetime.isoformat()}",
    )
    return reservation


@transaction.atomic
def confirm_pickup(reservation_id, actor):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__seller__seller_profile")
        .get(pk=reservation_id)
    )
    if reservation.status != Reservation.ACCEPTED or not reservation.pickup_datetime:
        raise ValidationError("An accepted reservation with a pickup proposal is required.")
    if reservation.pickup_status == Reservation.PICKUP_REQUESTED:
        authorized = _seller_can_transact(actor, reservation.listing)
    elif reservation.pickup_status == Reservation.PICKUP_SUGGESTED:
        authorized = reservation.buyer_id == getattr(actor, "pk", None)
    else:
        raise ValidationError("This pickup proposal cannot be confirmed.")
    if not authorized:
        raise PermissionDenied("The other transaction participant must confirm this proposal.")

    now = timezone.now()
    reservation.pickup_status = Reservation.PICKUP_CONFIRMED
    reservation.pickup_confirmed_by = actor
    reservation.pickup_confirmed_at = now
    pickup_hold = reservation.pickup_datetime + timedelta(hours=12)
    if not reservation.expires_at or reservation.expires_at < pickup_hold:
        reservation.expires_at = pickup_hold
    reservation.save(
        update_fields=[
            "pickup_status",
            "pickup_confirmed_by",
            "pickup_confirmed_at",
            "expires_at",
        ]
    )
    log_activity(
        reservation.listing,
        actor,
        "pickup_confirmed",
        "Pickup schedule confirmed by the other participant.",
        reservation=reservation,
    )
    create_marketplace_notification(
        recipient=reservation.pickup_proposed_by,
        actor=actor,
        notification_type=MarketplaceNotification.PICKUP,
        title=f"Pickup confirmed for {reservation.listing.goat.goat_id}",
        message=f"Pickup is confirmed for {timezone.localtime(reservation.pickup_datetime):%b %d, %Y at %I:%M %p}.",
        listing=reservation.listing,
        conversation=reservation.conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:pickup-confirmed:{reservation.pickup_datetime.isoformat()}",
    )
    return reservation


@transaction.atomic
def complete_sale(reservation_id, actor):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__goat", "listing__seller__seller_profile")
        .get(pk=reservation_id)
    )
    listing = MarketplaceListing.objects.select_for_update().get(pk=reservation.listing_id)
    goat = reservation.listing.goat
    if not _seller_can_transact(actor, reservation.listing):
        raise PermissionDenied("Only the approved listing seller can complete this sale.")
    if reservation.status != Reservation.ACCEPTED or listing.status != MarketplaceListing.RESERVED:
        raise ValidationError("Only the accepted reservation can be completed.")
    if reservation.pickup_status != Reservation.PICKUP_CONFIRMED:
        raise ValidationError("Confirm the pickup schedule before completing the sale.")

    now = timezone.now()
    reservation.status = Reservation.COMPLETED
    reservation.completed_at = now
    reservation.completed_by = actor
    reservation.save(update_fields=["status", "completed_at", "completed_by"])
    listing.status = MarketplaceListing.SOLD
    listing.sold_at = now
    listing.save(update_fields=["status", "sold_at", "updated_at"])
    goat.status = "sold"
    goat.is_active = False
    goat.save(update_fields=["status", "is_active", "last_updated"])
    log_activity(
        listing,
        actor,
        "sale_completed",
        f"Pickup and manual payment confirmed. Sold to {reservation.buyer.username}.",
        reservation=reservation,
        metadata={"selling_price": str(reservation.agreed_price)},
    )
    create_marketplace_notification(
        recipient=reservation.buyer,
        actor=actor,
        notification_type=MarketplaceNotification.SALE,
        title=f"Sale completed for {reservation.listing.goat.goat_id}",
        message="The seller confirmed pickup and completion of your purchase.",
        listing=listing,
        conversation=reservation.conversation,
        reservation=reservation,
        dedup_key=f"reservation:{reservation.pk}:completed",
    )
    for favorite in (
        Favorite.objects.filter(listing=listing)
        .exclude(user=reservation.buyer)
        .select_related("user")
    ):
        create_marketplace_notification(
            recipient=favorite.user,
            actor=actor,
            notification_type=MarketplaceNotification.LISTING,
            title=f"Saved goat {listing.goat.goat_id} was sold",
            message="This listing remains in Saved Goats with its updated Sold status.",
            listing=listing,
            reservation=reservation,
            dedup_key=f"listing:{listing.pk}:sold:{favorite.user_id}",
        )
    return reservation
