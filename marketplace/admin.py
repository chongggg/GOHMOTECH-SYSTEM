from django.contrib import admin

from .forms import ListingForm
from .models import Conversation, MarketplaceActivity, MarketplaceListing, Message, Reservation


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "is_read", "created_at")


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    form = ListingForm
    list_display = ("goat", "price", "status", "seller", "published_at", "sold_at")
    list_filter = ("status", "published_at", "sold_at")
    search_fields = ("goat__goat_id", "goat__name", "sales_description", "seller__username")
    readonly_fields = ("status", "sold_at", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.seller = request.user
        super().save_model(request, obj, form, change)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("listing", "buyer", "created_at", "updated_at")
    search_fields = ("listing__goat__goat_id", "buyer__username")
    readonly_fields = ("listing", "buyer", "created_at", "updated_at")
    inlines = (MessageInline,)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("listing", "buyer", "status", "agreed_price", "pickup_status", "reserved_at", "completed_at")
    list_filter = ("status", "pickup_status", "reserved_at", "completed_at")
    search_fields = ("listing__goat__goat_id", "buyer__username")
    readonly_fields = (
        "listing", "buyer", "conversation", "agreed_price", "status", "reserved_at",
        "completed_at", "completed_by", "cancelled_at", "cancelled_by",
    )


@admin.register(MarketplaceActivity)
class MarketplaceActivityAdmin(admin.ModelAdmin):
    list_display = ("listing", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("listing__goat__goat_id", "actor__username", "description")
    readonly_fields = ("listing", "reservation", "actor", "action", "description", "metadata", "created_at")
