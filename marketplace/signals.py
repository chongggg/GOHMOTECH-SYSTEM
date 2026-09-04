from allauth.account.signals import user_signed_up
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .auth import BUYER_GROUP_NAME
from .models import UserAccountState, UserActivity


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def initialize_account_administration(sender, instance, created, **kwargs):
    if not created:
        return
    UserAccountState.objects.get_or_create(
        user=instance,
        defaults={
            "status": (
                UserAccountState.ACTIVE
                if instance.is_active
                else UserAccountState.DEACTIVATED
            )
        },
    )
    UserActivity.objects.get_or_create(
        user=instance,
        event="account_registered",
        defaults={"description": "Account registered."},
    )


@receiver(user_signed_up)
def assign_marketplace_role(sender, request, user, **kwargs):
    """All local and Google signups start as marketplace buyers only."""
    buyer_group, _ = Group.objects.get_or_create(name=BUYER_GROUP_NAME)
    user.groups.add(buyer_group)
