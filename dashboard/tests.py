from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from marketplace.auth import FARM_OWNER_GROUP_NAME


class RootLandingTests(TestCase):
    def test_public_visitor_is_sent_to_marketplace(self):
        response = self.client.get("/")

        self.assertRedirects(
            response,
            "/marketplace/",
            fetch_redirect_response=False,
        )

    def test_marketplace_user_is_sent_to_marketplace(self):
        user = get_user_model().objects.create_user(
            username="marketplace-user",
            password="test-pass",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            "/marketplace/",
            fetch_redirect_response=False,
        )

    def test_staff_user_is_sent_to_admin_dashboard(self):
        user = get_user_model().objects.create_user(
            username="staff-user",
            password="test-pass",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(response, "/iot/", fetch_redirect_response=False)

    def test_farm_owner_is_sent_to_owner_dashboard(self):
        user = get_user_model().objects.create_user(
            username="farm-owner",
            password="test-pass",
        )
        owner_group, _ = Group.objects.get_or_create(name=FARM_OWNER_GROUP_NAME)
        user.groups.add(owner_group)
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            "/iot/owner/",
            fetch_redirect_response=False,
        )
