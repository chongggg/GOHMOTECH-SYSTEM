from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class MarketplaceListing(models.Model):
    DRAFT = "draft"
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (AVAILABLE, "Available"),
        (RESERVED, "Reserved"),
        (SOLD, "Sold"),
    ]

    # A goat remains the inventory asset. This model stores commercial data only.
    goat = models.OneToOneField(
        "iot.Goat", on_delete=models.PROTECT, related_name="marketplace_listing"
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    sales_description = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=DRAFT, db_index=True
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marketplace_listings",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    sold_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"{self.goat.goat_id} - PHP {self.price} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.status in {self.DRAFT, self.AVAILABLE, self.RESERVED}:
            if self.goat.status != "active" or not self.goat.is_active:
                raise ValidationError(
                    {"goat": "Only active inventory goats can have an unsold listing."}
                )

    @property
    def can_inquire(self):
        return self.status == self.AVAILABLE and self.goat.status == "active" and self.goat.is_active

    @property
    def can_reserve(self):
        return self.can_inquire


class Conversation(models.Model):
    listing = models.ForeignKey(
        MarketplaceListing, on_delete=models.PROTECT, related_name="conversations"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marketplace_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "buyer"], name="uniq_listing_buyer_conversation"
            )
        ]

    def __str__(self):
        return f"{self.listing.goat.goat_id} / {self.buyer.username}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marketplace_messages",
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender} at {self.created_at:%Y-%m-%d %H:%M}"


class Reservation(models.Model):
    RESERVED = "reserved"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    STATUS_CHOICES = [
        (RESERVED, "Reserved"),
        (CANCELLED, "Cancelled"),
        (COMPLETED, "Completed"),
    ]
    NO_PICKUP = "not_requested"
    PICKUP_REQUESTED = "requested"
    PICKUP_SUGGESTED = "suggested"
    PICKUP_CONFIRMED = "confirmed"
    PICKUP_STATUS_CHOICES = [
        (NO_PICKUP, "Not requested"),
        (PICKUP_REQUESTED, "Requested by buyer"),
        (PICKUP_SUGGESTED, "Alternative suggested by admin"),
        (PICKUP_CONFIRMED, "Confirmed"),
    ]

    listing = models.ForeignKey(
        MarketplaceListing, on_delete=models.PROTECT, related_name="reservations"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marketplace_reservations",
    )
    conversation = models.ForeignKey(
        Conversation, on_delete=models.PROTECT, related_name="reservations"
    )
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=RESERVED, db_index=True
    )
    reserved_at = models.DateTimeField(default=timezone.now, db_index=True)
    pickup_datetime = models.DateTimeField(null=True, blank=True)
    pickup_status = models.CharField(
        max_length=20, choices=PICKUP_STATUS_CHOICES, default=NO_PICKUP
    )
    pickup_notes = models.TextField(blank=True)
    pickup_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_marketplace_pickups",
    )
    pickup_confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_marketplace_sales",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_marketplace_reservations",
    )
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-reserved_at"]

    def __str__(self):
        return f"{self.listing.goat.goat_id} reserved by {self.buyer.username}"


class MarketplaceActivity(models.Model):
    listing = models.ForeignKey(
        MarketplaceListing, on_delete=models.PROTECT, related_name="activity_logs"
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketplace_activity",
    )
    action = models.CharField(max_length=50, db_index=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Marketplace activities"

    def __str__(self):
        return f"{self.action}: {self.listing.goat.goat_id}"

