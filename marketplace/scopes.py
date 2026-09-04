from django.db.models import Q

from iot.models import Goat

from .auth import can_manage_farm


def manageable_goat_q(user):
    """Goats the account may use in its marketplace management workflow."""
    if can_manage_farm(user):
        return Q(record_source=Goat.SMART_FARM)
    return Q(owner=user, record_source=Goat.COMMUNITY)


def manageable_goats(user, queryset=None):
    queryset = queryset if queryset is not None else Goat.all_objects.all()
    return queryset.filter(manageable_goat_q(user))


def manageable_listing_q(user, prefix=""):
    """Listing scope, optionally rooted through a relation prefix."""
    if can_manage_farm(user):
        return Q(**{f"{prefix}goat__record_source": Goat.SMART_FARM})
    return Q(**{f"{prefix}seller": user})


def manageable_listings(user, queryset=None):
    from .models import MarketplaceListing

    queryset = queryset if queryset is not None else MarketplaceListing.objects.all()
    return queryset.filter(manageable_listing_q(user))


def can_manage_listing(user, listing):
    if not getattr(user, "is_authenticated", False):
        return False
    if can_manage_farm(user):
        return listing.goat.record_source == Goat.SMART_FARM
    return listing.seller_id == user.pk
