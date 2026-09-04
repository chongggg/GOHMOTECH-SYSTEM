from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .auth import can_manage_farm, has_farm_access, is_approved_seller, is_marketplace_user


def farm_access_required(view_func):
    """Require explicit access to the client's smart-farm modules."""
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_farm_access(request.user):
            raise PermissionDenied("You do not have permission to access this feature.")
        return view_func(request, *args, **kwargs)

    return wrapped


def staff_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("You do not have permission to access this feature.")
        return view_func(request, *args, **kwargs)

    return wrapped


def farm_owner_required(view_func):
    """Allow farm mutations to Admin and Farm Owner, never Farm Operator."""
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not can_manage_farm(request.user):
            raise PermissionDenied("You do not have permission to modify farm data.")
        return view_func(request, *args, **kwargs)

    return wrapped


def seller_applicant_required(view_func):
    """Allow seller applications only from regular marketplace accounts."""
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_marketplace_user(request.user):
            messages.error(
                request,
                "Administrator and farm-operator accounts cannot apply as community sellers.",
            )
            if request.user.is_staff or request.user.is_superuser:
                return redirect("marketplace:admin_dashboard")
            return redirect("marketplace:list")
        return view_func(request, *args, **kwargs)

    return wrapped


def approved_seller_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_approved_seller(request.user):
            messages.error(request, "An approved seller account is required.")
            return redirect("marketplace:seller_application")
        return view_func(request, *args, **kwargs)

    return wrapped
