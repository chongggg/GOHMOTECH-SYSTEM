from django.contrib import messages
from django.shortcuts import redirect

from .auth import is_marketplace_buyer


class MarketplaceBuyerAccessMiddleware:
    """Keep buyer-only accounts out of farm operations and staff administration."""

    RESTRICTED_PREFIXES = (
        "/admin/",
        "/analytics/",
        "/feeding/",
        "/iot/",
        "/ml/",
        "/security/",
        "/sms/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_marketplace_buyer(request.user) and request.path.startswith(self.RESTRICTED_PREFIXES):
            messages.error(request, "Buyer accounts do not have access to farm operations.")
            return redirect("marketplace:list")
        return self.get_response(request)

