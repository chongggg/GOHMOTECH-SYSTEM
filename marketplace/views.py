from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from iot.models import Goat

from .decorators import staff_required
from .forms import BuyerRegistrationForm, ListingForm, MessageForm, PickupRequestForm
from .models import Conversation, MarketplaceActivity, MarketplaceListing, Reservation
from .services import cancel_reservation, complete_sale, log_activity, reserve_listing


def _attach_images(listings):
    for listing in listings:
        listing.display_image = listing.goat.images.order_by("-uploaded_at").first()
    return listings


def marketplace_landing(request):
    featured = MarketplaceListing.objects.select_related("goat").filter(
        status=MarketplaceListing.AVAILABLE,
        goat__status="active",
        goat__is_active=True,
    ).order_by("-published_at")[:6]
    return render(
        request,
        "marketplace/landing.html",
        {
            "featured_listings": _attach_images(list(featured)),
            "available_count": MarketplaceListing.objects.filter(
                status=MarketplaceListing.AVAILABLE,
                goat__status="active",
                goat__is_active=True,
            ).count(),
        },
    )


def marketplace_list(request):
    listings = MarketplaceListing.objects.select_related("goat", "seller").filter(
        status__in=[MarketplaceListing.AVAILABLE, MarketplaceListing.RESERVED],
        goat__status="active",
        goat__is_active=True,
    )

    breed = request.GET.get("breed", "").strip()
    gender = request.GET.get("gender", "").strip()
    query = request.GET.get("q", "").strip()
    if query:
        listings = listings.filter(
            Q(goat__goat_id__icontains=query)
            | Q(goat__tag_number__icontains=query)
            | Q(goat__name__icontains=query)
            | Q(goat__breed__icontains=query)
        )
    if breed:
        listings = listings.filter(goat__breed=breed)
    if gender:
        listings = listings.filter(goat__gender=gender)

    numeric_filters = [
        ("min_weight", "goat__weight_kg__gte"),
        ("max_weight", "goat__weight_kg__lte"),
        ("min_price", "price__gte"),
        ("max_price", "price__lte"),
    ]
    for parameter, lookup in numeric_filters:
        raw = request.GET.get(parameter, "").strip()
        if raw:
            try:
                listings = listings.filter(**{lookup: Decimal(raw)})
            except InvalidOperation:
                pass

    today = timezone.localdate()
    try:
        min_age = int(request.GET.get("min_age", ""))
        listings = listings.filter(goat__date_of_birth__lte=today - timedelta(days=min_age * 365))
    except (TypeError, ValueError):
        pass
    try:
        max_age = int(request.GET.get("max_age", ""))
        listings = listings.filter(goat__date_of_birth__gte=today - timedelta(days=(max_age + 1) * 365))
    except (TypeError, ValueError):
        pass

    sort = request.GET.get("sort", "newest")
    sort_options = {
        "newest": ("status", "-published_at"),
        "price_low": ("status", "price"),
        "price_high": ("status", "-price"),
        "weight_high": ("status", "-goat__weight_kg"),
    }
    listings = _attach_images(list(listings.order_by(*sort_options.get(sort, sort_options["newest"]))))
    return render(
        request,
        "marketplace/list.html",
        {
            "listings": listings,
            "breed_choices": Goat.BREED_CHOICES,
            "selected": request.GET,
            "sort": sort,
            "result_count": len(listings),
        },
    )


def listing_detail(request, pk):
    listing = get_object_or_404(
        MarketplaceListing.objects.select_related("goat", "seller"), pk=pk
    )
    if listing.status == MarketplaceListing.DRAFT and not (
        request.user.is_authenticated and request.user.is_staff
    ):
        return redirect("marketplace:list")
    images = listing.goat.images.order_by("-uploaded_at")
    conversation = None
    active_reservation = None
    if request.user.is_authenticated and not request.user.is_staff:
        conversation = Conversation.objects.filter(listing=listing, buyer=request.user).first()
        active_reservation = Reservation.objects.filter(
            listing=listing, buyer=request.user, status=Reservation.RESERVED
        ).first()
    return render(
        request,
        "marketplace/detail.html",
        {
            "listing": listing,
            "images": images,
            "conversation": conversation,
            "active_reservation": active_reservation,
        },
    )


def buyer_register(request):
    if request.user.is_authenticated:
        return redirect("marketplace:list")
    form = BuyerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Buyer account created. You can now inquire about a goat.")
        return redirect("marketplace:list")
    return render(request, "marketplace/register.html", {"form": form})


@login_required
@require_POST
def start_inquiry(request, pk):
    listing = get_object_or_404(MarketplaceListing.objects.select_related("goat"), pk=pk)
    if request.user.is_staff:
        messages.info(request, "Staff can reply from the marketplace administration page.")
        return redirect("marketplace:detail", pk=pk)
    if not listing.can_inquire:
        messages.error(request, "This goat is not currently accepting new inquiries.")
        return redirect("marketplace:detail", pk=pk)
    conversation, created = Conversation.objects.get_or_create(listing=listing, buyer=request.user)
    if created:
        log_activity(listing, request.user, "inquiry_started", "Buyer opened a private inquiry.")
    return redirect("marketplace:conversation", pk=conversation.pk)


@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.select_related("listing__goat", "buyer", "listing__seller"), pk=pk
    )
    if not request.user.is_staff and conversation.buyer_id != request.user.id:
        messages.error(request, "You do not have access to that conversation.")
        return redirect("marketplace:my_inquiries")

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
            return redirect("marketplace:conversation", pk=pk)
    else:
        form = MessageForm()

    conversation.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
    active_reservation = conversation.reservations.filter(status=Reservation.RESERVED).first()
    return render(
        request,
        "marketplace/conversation.html",
        {
            "conversation": conversation,
            "conversation_messages": conversation.messages.select_related("sender"),
            "form": form,
            "active_reservation": active_reservation,
        },
    )


@login_required
def my_inquiries(request):
    conversations = Conversation.objects.filter(buyer=request.user).select_related(
        "listing__goat"
    )
    return render(request, "marketplace/my_inquiries.html", {"conversations": conversations})


@login_required
@require_POST
def confirm_purchase(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, buyer=request.user)
    try:
        reservation = reserve_listing(conversation.listing_id, request.user, conversation)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Goat reserved. Please request a farm pickup schedule.")
        return redirect("marketplace:pickup", pk=reservation.pk)
    return redirect("marketplace:conversation", pk=pk)


@login_required
def pickup_request(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("listing__goat", "buyer"), pk=pk
    )
    if not request.user.is_staff and reservation.buyer_id != request.user.id:
        messages.error(request, "You do not have access to that reservation.")
        return redirect("marketplace:my_inquiries")
    if reservation.status != Reservation.RESERVED:
        messages.info(request, "This reservation is no longer active.")
        return redirect("marketplace:conversation", pk=reservation.conversation_id)

    form = PickupRequestForm(request.POST or None, instance=reservation)
    if request.method == "POST" and form.is_valid():
        pickup = form.save(commit=False)
        pickup.pickup_status = Reservation.PICKUP_REQUESTED
        pickup.pickup_confirmed_by = None
        pickup.pickup_confirmed_at = None
        pickup.save()
        log_activity(
            pickup.listing,
            request.user,
            "pickup_requested",
            f"Pickup requested for {timezone.localtime(pickup.pickup_datetime):%Y-%m-%d %H:%M}.",
            reservation=pickup,
        )
        messages.success(request, "Pickup request sent to the admin.")
        return redirect("marketplace:conversation", pk=reservation.conversation_id)
    return render(request, "marketplace/pickup_form.html", {"reservation": reservation, "form": form})


@staff_required
def admin_dashboard(request):
    listings = _attach_images(
        list(MarketplaceListing.objects.select_related("goat", "seller").all())
    )
    reservations = Reservation.objects.select_related("listing__goat", "buyer").filter(
        status=Reservation.RESERVED
    )
    return render(
        request,
        "marketplace/admin_dashboard.html",
        {
            "listings": listings,
            "reservations": reservations,
            "available_count": MarketplaceListing.objects.filter(status="available").count(),
            "reserved_count": reservations.count(),
            "sold_count": MarketplaceListing.objects.filter(status="sold").count(),
            "inquiry_count": Conversation.objects.count(),
        },
    )


@staff_required
def manage_listing(request, pk=None):
    listing = get_object_or_404(MarketplaceListing, pk=pk) if pk else None
    form = ListingForm(request.POST or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if not saved.pk:
            saved.seller = request.user
        saved.full_clean()
        saved.save()
        log_activity(saved, request.user, "listing_saved", "Marketplace listing details saved.")
        messages.success(request, "Marketplace listing saved.")
        return redirect("marketplace:admin_dashboard")
    return render(request, "marketplace/listing_form.html", {"form": form, "listing": listing})


@staff_required
@require_POST
def set_listing_publication(request, pk):
    with transaction.atomic():
        listing = get_object_or_404(
            MarketplaceListing.objects.select_for_update().select_related("goat"), pk=pk
        )
        action = request.POST.get("action")
        if action == "publish" and listing.status == MarketplaceListing.DRAFT:
            if listing.goat.status != "active" or not listing.goat.is_active:
                messages.error(request, "Only an active inventory goat can be published.")
                return redirect("marketplace:admin_dashboard")
            listing.status = MarketplaceListing.AVAILABLE
            listing.published_at = timezone.now()
            event = "listing_published"
        elif action == "unpublish" and listing.status == MarketplaceListing.AVAILABLE:
            listing.status = MarketplaceListing.DRAFT
            event = "listing_unpublished"
        else:
            messages.error(request, "That publication change is not allowed for this listing.")
            return redirect("marketplace:admin_dashboard")
        listing.save(update_fields=["status", "published_at", "updated_at"])
        log_activity(listing, request.user, event)
    messages.success(request, "Listing status updated.")
    return redirect("marketplace:admin_dashboard")


@staff_required
def admin_inquiries(request):
    conversations = Conversation.objects.select_related("listing__goat", "buyer").all()
    return render(request, "marketplace/admin_inquiries.html", {"conversations": conversations})


@staff_required
@require_POST
def admin_reservation_action(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("listing"), pk=pk)
    action = request.POST.get("action")
    try:
        if action == "cancel":
            cancel_reservation(pk, request.user, request.POST.get("reason", "").strip())
            messages.success(request, "Reservation cancelled and goat returned to Available.")
        elif action == "confirm_pickup":
            if reservation.status != Reservation.RESERVED or not reservation.pickup_datetime:
                raise ValidationError("A pickup request is required before confirmation.")
            reservation.pickup_status = Reservation.PICKUP_CONFIRMED
            reservation.pickup_confirmed_by = request.user
            reservation.pickup_confirmed_at = timezone.now()
            reservation.save(
                update_fields=["pickup_status", "pickup_confirmed_by", "pickup_confirmed_at"]
            )
            log_activity(reservation.listing, request.user, "pickup_confirmed", reservation=reservation)
            messages.success(request, "Pickup schedule confirmed.")
        elif action == "suggest_pickup":
            form = PickupRequestForm(request.POST, instance=reservation)
            if not form.is_valid():
                raise ValidationError("Enter a valid alternative pickup date and time.")
            reservation = form.save(commit=False)
            reservation.pickup_status = Reservation.PICKUP_SUGGESTED
            reservation.pickup_confirmed_by = None
            reservation.pickup_confirmed_at = None
            reservation.save()
            log_activity(reservation.listing, request.user, "pickup_suggested", reservation=reservation)
            messages.success(request, "Alternative pickup schedule suggested.")
        elif action == "complete":
            complete_sale(pk, request.user)
            messages.success(request, "Sale completed and inventory goat marked Sold.")
        else:
            messages.error(request, "Unknown reservation action.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("marketplace:admin_dashboard")


@staff_required
def sales_history(request):
    sales = Reservation.objects.filter(status=Reservation.COMPLETED).select_related(
        "listing__goat", "buyer", "completed_by"
    )
    activity = MarketplaceActivity.objects.select_related("listing__goat", "actor")[:100]
    return render(request, "marketplace/sales_history.html", {"sales": sales, "activity": activity})
