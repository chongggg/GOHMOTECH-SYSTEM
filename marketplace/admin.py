from django.contrib import admin

from .forms import ListingForm
from .models import (
    Conversation,
    Favorite,
    MarketplaceActivity,
    MarketplaceListing,
    MarketplaceNotification,
    MarketplaceReport,
    Message,
    Reservation,
    SellerProfile,
    SupportAttachment,
    SupportMessage,
    SupportTicket,
    UserAccountState,
    UserActivity,
)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "farm_name",
        "user",
        "municipality",
        "province",
        "status",
        "applied_at",
        "reviewed_by",
    )
    list_filter = ("status", "province", "applied_at", "reviewed_at")
    search_fields = (
        "farm_name",
        "user__first_name",
        "user__last_name",
        "user__email",
        "municipality",
        "province",
    )
    readonly_fields = (
        "user",
        "status",
        "review_reason",
        "applied_at",
        "reviewed_at",
        "reviewed_by",
        "approved_at",
        "updated_at",
    )


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "is_read", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    form = ListingForm
    list_display = ("goat", "price", "status", "is_featured", "seller", "published_at", "sold_at")
    list_filter = ("status", "is_featured", "published_at", "sold_at")
    search_fields = ("goat__goat_id", "goat__name", "sales_description", "seller__username")
    readonly_fields = ("status", "sold_at", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.seller = obj.goat.owner or request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("listing", "buyer", "seller", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = (
        "listing__goat__goat_id",
        "buyer__username",
        "listing__seller__username",
    )
    readonly_fields = (
        "listing",
        "buyer",
        "status",
        "closed_at",
        "closed_by",
        "created_at",
        "updated_at",
    )
    inlines = (MessageInline,)

    @admin.display(description="Seller")
    def seller(self, obj):
        return obj.listing.seller


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "listing",
        "buyer",
        "seller",
        "status",
        "agreed_price",
        "pickup_status",
        "reserved_at",
        "expires_at",
        "completed_at",
    )
    list_filter = (
        "status",
        "pickup_status",
        "reserved_at",
        "accepted_at",
        "expires_at",
        "completed_at",
    )
    search_fields = (
        "listing__goat__goat_id",
        "buyer__username",
        "listing__seller__username",
    )
    readonly_fields = (
        "listing", "buyer", "conversation", "agreed_price", "status", "reserved_at",
        "accepted_at", "expires_at", "rejected_at", "rejected_by",
        "rejection_reason", "pickup_datetime", "pickup_status", "pickup_notes",
        "pickup_location", "pickup_proposed_by", "pickup_confirmed_by",
        "pickup_confirmed_at", "completed_at", "completed_by", "cancelled_at",
        "cancelled_by", "cancellation_reason",
    )

    @admin.display(description="Seller")
    def seller(self, obj):
        return obj.listing.seller


@admin.register(MarketplaceActivity)
class MarketplaceActivityAdmin(admin.ModelAdmin):
    list_display = ("listing", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("listing__goat__goat_id", "actor__username", "description")
    readonly_fields = ("listing", "reservation", "actor", "action", "description", "metadata", "created_at")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")
    search_fields = ("user__username", "listing__goat__goat_id")
    readonly_fields = ("user", "listing", "created_at")


@admin.register(MarketplaceReport)
class MarketplaceReportAdmin(admin.ModelAdmin):
    list_display = ("listing", "reporter", "reason", "status", "created_at", "reviewed_by")
    list_filter = ("status", "reason", "created_at")
    search_fields = (
        "listing__goat__goat_id",
        "reporter__username",
        "description",
    )
    readonly_fields = (
        "reporter",
        "listing",
        "reason",
        "description",
        "status",
        "created_at",
        "reviewed_at",
        "reviewed_by",
        "resolution_notes",
    )


@admin.register(MarketplaceNotification)
class MarketplaceNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "notification_type",
        "title",
        "is_read",
        "created_at",
    )
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("recipient__username", "title", "message")
    readonly_fields = (
        "recipient",
        "actor",
        "notification_type",
        "title",
        "message",
        "listing",
        "conversation",
        "reservation",
        "report",
        "support_ticket",
        "dedup_key",
        "is_read",
        "read_at",
        "created_at",
    )


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ("sender", "body", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number", "user", "subject", "category", "status",
        "priority", "created_at", "updated_at",
    )
    list_filter = ("status", "category", "priority", "created_at")
    search_fields = (
        "ticket_number", "subject", "user__first_name",
        "user__last_name", "user__email",
    )
    readonly_fields = (
        "ticket_number", "user", "subject", "category", "description",
        "status", "priority", "assigned_to",
        "related_listing", "related_conversation", "related_reservation",
        "created_at", "updated_at", "resolved_at", "closed_at",
    )
    inlines = (SupportMessageInline,)


@admin.register(SupportAttachment)
class SupportAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "message", "content_type", "size", "created_at")
    readonly_fields = (
        "message", "file", "original_name", "content_type", "size", "created_at"
    )


@admin.register(UserAccountState)
class UserAccountStateAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "changed_by", "changed_at")
    list_filter = ("status", "changed_at")
    readonly_fields = ("user", "status", "reason", "changed_by", "changed_at")


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "actor", "created_at")
    list_filter = ("event", "created_at")
    readonly_fields = ("user", "event", "description", "actor", "metadata", "created_at")
