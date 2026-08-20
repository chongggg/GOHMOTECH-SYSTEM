from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from iot.models import Goat, GoatImage

from .models import Conversation, MarketplaceListing, Reservation
from .services import cancel_reservation, complete_sale, reserve_listing


class MarketplaceWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="testpass123", is_staff=True)
        self.buyer = User.objects.create_user("buyer", password="testpass123")
        self.other_buyer = User.objects.create_user("other", password="testpass123")
        self.goat = Goat.objects.create(
            goat_id="GT-MKT-001",
            name="Market Goat",
            breed="native",
            gender="female",
            health_status="healthy",
            status="active",
            is_active=True,
        )
        self.listing = MarketplaceListing.objects.create(
            goat=self.goat,
            seller=self.admin,
            price=Decimal("12500.00"),
            sales_description="Healthy farm goat.",
            status=MarketplaceListing.AVAILABLE,
            published_at=timezone.now(),
        )
        self.conversation = Conversation.objects.create(listing=self.listing, buyer=self.buyer)

    def test_inquiry_does_not_reserve_goat(self):
        self.client.force_login(self.other_buyer)
        response = self.client.post(reverse("marketplace:start_inquiry", args=[self.listing.pk]))
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db()
        self.goat.refresh_from_db()
        self.assertEqual(self.listing.status, MarketplaceListing.AVAILABLE)
        self.assertEqual(self.goat.status, "active")

    def test_reservation_is_single_and_does_not_sell_inventory_goat(self):
        reservation = reserve_listing(self.listing.pk, self.buyer, self.conversation)
        self.listing.refresh_from_db()
        self.goat.refresh_from_db()
        self.assertEqual(reservation.agreed_price, Decimal("12500.00"))
        self.assertEqual(self.listing.status, MarketplaceListing.RESERVED)
        self.assertEqual(self.goat.status, "active")
        self.assertTrue(self.goat.is_active)

        other_conversation = Conversation.objects.create(listing=self.listing, buyer=self.other_buyer)
        with self.assertRaises(ValidationError):
            reserve_listing(self.listing.pk, self.other_buyer, other_conversation)

    def test_cancel_returns_listing_to_available(self):
        reservation = reserve_listing(self.listing.pk, self.buyer, self.conversation)
        cancel_reservation(reservation.pk, self.admin, "Buyer cancelled")
        reservation.refresh_from_db()
        self.listing.refresh_from_db()
        self.goat.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.CANCELLED)
        self.assertEqual(self.listing.status, MarketplaceListing.AVAILABLE)
        self.assertEqual(self.goat.status, "active")

    def test_completion_requires_confirmed_pickup_and_marks_existing_goat_sold(self):
        reservation = reserve_listing(self.listing.pk, self.buyer, self.conversation)
        with self.assertRaises(ValidationError):
            complete_sale(reservation.pk, self.admin)

        reservation.pickup_datetime = timezone.now() + timedelta(days=1)
        reservation.pickup_status = Reservation.PICKUP_CONFIRMED
        reservation.save(update_fields=["pickup_datetime", "pickup_status"])
        complete_sale(reservation.pk, self.admin)

        reservation.refresh_from_db()
        self.listing.refresh_from_db()
        self.goat.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.COMPLETED)
        self.assertEqual(self.listing.status, MarketplaceListing.SOLD)
        self.assertEqual(self.goat.status, "sold")
        self.assertFalse(self.goat.is_active)

    def test_private_conversation_is_not_visible_to_another_buyer(self):
        self.client.force_login(self.other_buyer)
        response = self.client.get(reverse("marketplace:conversation", args=[self.conversation.pk]))
        self.assertRedirects(response, reverse("marketplace:my_inquiries"))

    def test_non_staff_cannot_open_marketplace_admin(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("marketplace:admin_dashboard"))
        self.assertRedirects(response, reverse("marketplace:list"))

    def test_public_and_staff_pages_render(self):
        self.assertEqual(self.client.get(reverse("marketplace:landing")).status_code, 200)
        self.assertEqual(self.client.get(reverse("marketplace:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("marketplace:buyer_login")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("marketplace:detail", args=[self.listing.pk])).status_code,
            200,
        )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("marketplace:admin_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("marketplace:listing_add")).status_code, 200)

    def test_registered_buyer_is_separated_from_farm_dashboard(self):
        response = self.client.post(
            reverse("marketplace:register"),
            {
                "username": "newbuyer",
                "first_name": "New",
                "last_name": "Buyer",
                "email": "buyer@example.com",
                "password1": "A-strong-test-password-123",
                "password2": "A-strong-test-password-123",
            },
        )
        self.assertRedirects(response, reverse("marketplace:list"))
        response = self.client.get("/iot/")
        self.assertRedirects(response, reverse("marketplace:list"))
        response = self.client.get("/")
        self.assertRedirects(response, "/marketplace/")

    def test_catalog_search_filter_and_sort(self):
        response = self.client.get(
            reverse("marketplace:list"),
            {"q": "GT-MKT", "breed": "native", "sort": "price_high"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GT-MKT-001")
        self.assertEqual(response.context["result_count"], 1)

    def test_detail_renders_slider_for_multiple_goat_images(self):
        GoatImage.objects.create(
            goat=self.goat,
            image="goat_images/report-front.jpg",
            image_type="profile",
            description="Front view",
        )
        GoatImage.objects.create(
            goat=self.goat,
            image="goat_images/report-side.jpg",
            image_type="full_body",
            description="Side view",
        )
        response = self.client.get(reverse("marketplace:detail", args=[self.listing.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-goat-gallery")
        self.assertContains(response, 'class="gallery-slide', count=2)
        self.assertContains(response, 'class="gallery-thumbnail', count=2)
        self.assertContains(response, "data-gallery-next")
        self.assertContains(response, "data-gallery-lightbox")

    def test_storefront_includes_mobile_navigation_and_catalog_filters(self):
        landing = self.client.get(reverse("marketplace:landing"))
        self.assertContains(landing, 'name="viewport"')
        self.assertContains(landing, "mobile-nav-actions")
        self.assertContains(landing, "data-nav-toggle")
        self.assertContains(landing, "images/gohmotech-logo.png", count=4)

        catalog = self.client.get(reverse("marketplace:list"))
        self.assertContains(catalog, "data-filter-toggle")
        self.assertContains(catalog, "marketplaceFilters")

    def test_main_login_page_renders_enhanced_authentication_layout(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connected farm platform")
        self.assertContains(response, "data-password-toggle")
        self.assertContains(response, "Browse the public marketplace")
        self.assertContains(response, 'name="viewport"')

    def test_main_login_preserves_username_and_next_after_error(self):
        response = self.client.post(
            reverse("login") + "?next=/analytics/",
            {"username": "wrong-user", "password": "wrong-password", "next": "/analytics/"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="wrong-user"')
        self.assertContains(response, 'name="next" value="/analytics/"')
        self.assertContains(response, "We couldn't sign you in")
