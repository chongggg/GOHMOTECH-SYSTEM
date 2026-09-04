from rest_framework.permissions import BasePermission, SAFE_METHODS

from .auth import can_manage_farm, has_farm_access, is_admin


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsFarmOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return can_manage_farm(request.user)


class FarmRolePermission(BasePermission):
    """Admin/Owner may write; Operator may only issue safe requests."""
    def has_permission(self, request, view):
        if not has_farm_access(request.user):
            return False
        return request.method in SAFE_METHODS or can_manage_farm(request.user)
