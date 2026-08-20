from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import MarketplaceActivity, MarketplaceListing, Reservation


def log_activity(listing, actor, action, description="", reservation=None, metadata=None):
    return MarketplaceActivity.objects.create(
        listing=listing,
        reservation=reservation,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        description=description,
        metadata=metadata or {},
    )


@transaction.atomic
def reserve_listing(listing_id, buyer, conversation):
    listing = (
        MarketplaceListing.objects.select_for_update()
        .select_related("goat")
        .get(pk=listing_id)
    )
    if listing.status != MarketplaceListing.AVAILABLE:
        raise ValidationError("This goat is no longer available.")
    if listing.goat.status != "active" or not listing.goat.is_active:
        raise ValidationError("This goat is no longer active in inventory.")
    if conversation.listing_id != listing.id or conversation.buyer_id != buyer.id:
        raise ValidationError("A valid inquiry for this goat is required.")

    reservation = Reservation.objects.create(
        listing=listing,
        buyer=buyer,
        conversation=conversation,
        agreed_price=listing.price,
    )
    listing.status = MarketplaceListing.RESERVED
    listing.save(update_fields=["status", "updated_at"])
    log_activity(
        listing,
        buyer,
        "reserved",
        f"Reserved by {buyer.username}.",
        reservation=reservation,
    )
    return reservation


@transaction.atomic
def cancel_reservation(reservation_id, actor, reason=""):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__goat")
        .get(pk=reservation_id)
    )
    listing = MarketplaceListing.objects.select_for_update().get(pk=reservation.listing_id)
    if reservation.status != Reservation.RESERVED or listing.status != MarketplaceListing.RESERVED:
        raise ValidationError("Only the current reservation can be cancelled.")

    reservation.status = Reservation.CANCELLED
    reservation.cancelled_at = timezone.now()
    reservation.cancelled_by = actor
    reservation.cancellation_reason = reason
    reservation.save(
        update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason"]
    )
    listing.status = MarketplaceListing.AVAILABLE
    listing.save(update_fields=["status", "updated_at"])
    log_activity(
        listing,
        actor,
        "reservation_cancelled",
        reason or "Reservation cancelled; listing returned to available.",
        reservation=reservation,
    )
    return reservation


@transaction.atomic
def complete_sale(reservation_id, actor):
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("listing__goat")
        .get(pk=reservation_id)
    )
    listing = MarketplaceListing.objects.select_for_update().get(pk=reservation.listing_id)
    goat = listing.goat
    if reservation.status != Reservation.RESERVED or listing.status != MarketplaceListing.RESERVED:
        raise ValidationError("Only the current reservation can be completed.")
    if reservation.pickup_status != Reservation.PICKUP_CONFIRMED:
        raise ValidationError("Confirm the farm pickup schedule before completing the sale.")

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
    return reservation
