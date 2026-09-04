from django.conf import settings

from .auth import (
    can_manage_farm,
    get_system_role,
    has_farm_access,
    is_admin,
    is_farm_operator,
    is_farm_owner,
    is_approved_seller,
    is_marketplace_buyer,
    is_marketplace_user,
    seller_profile_for,
)
from .models import MarketplaceNotification


def marketplace_role(request):
    seller_profile = seller_profile_for(request.user)
    return {
        "system_role": get_system_role(request.user),
        "is_system_admin": is_admin(request.user),
        "is_farm_owner": is_farm_owner(request.user),
        "is_farm_operator": is_farm_operator(request.user),
        "can_manage_farm": can_manage_farm(request.user),
        "has_farm_access": has_farm_access(request.user),
        "is_marketplace_user": is_marketplace_user(request.user),
        "is_marketplace_buyer": is_marketplace_buyer(request.user),
        "seller_profile": seller_profile,
        "is_approved_seller": is_approved_seller(request.user),
        "google_oauth_configured": bool(
            settings.GOOGLE_OAUTH_CLIENT_ID
            and settings.GOOGLE_OAUTH_CLIENT_SECRET
        ),
        "marketplace_unread_notification_count": (
            MarketplaceNotification.objects.filter(
                recipient=request.user,
                is_read=False,
            ).count()
            if getattr(request.user, "is_authenticated", False)
            else 0
        ),
    }
