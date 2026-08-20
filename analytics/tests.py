from datetime import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from analytics import report_data
from iot.models import Goat
from marketplace.models import Conversation, MarketplaceListing, Reservation


class MonthlyAggregationTests(SimpleTestCase):
    def test_monthly_counts_handle_timezone_aware_dates(self):
        now = timezone.make_aware(datetime(2024, 2, 15, 12, 0, 0))
        values = [
            timezone.make_aware(datetime(2024, 1, 5, 10, 0, 0)),
            timezone.make_aware(datetime(2023, 12, 20, 8, 0, 0)),
        ]

        labels, counts = report_data._monthly_counts_for_last_year(values, now=now)

        self.assertEqual(labels[0], "Mar 2023")
        self.assertEqual(labels[-1], "Feb 2024")
        self.assertEqual(counts[10], 1)
        self.assertEqual(counts[11], 0)
        self.assertEqual(counts[9], 1)
        self.assertEqual(len(labels), 12)


class MarketplaceReportTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            "reportadmin", password="testpass123", is_staff=True
        )
        self.buyer = User.objects.create_user("reportbuyer", password="testpass123")
        self.goat = Goat.objects.create(
            goat_id="REPORT-GOAT-001",
            breed="native",
            gender="female",
            status="sold",
            is_active=False,
        )
        self.listing = MarketplaceListing.objects.create(
            goat=self.goat,
            seller=self.staff,
            price=Decimal("15000.00"),
            sales_description="Report test listing",
            status=MarketplaceListing.SOLD,
            sold_at=timezone.now(),
        )
        self.conversation = Conversation.objects.create(
            listing=self.listing, buyer=self.buyer
        )
        self.reservation = Reservation.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            conversation=self.conversation,
            agreed_price=Decimal("15000.00"),
            status=Reservation.COMPLETED,
            pickup_status=Reservation.PICKUP_CONFIRMED,
            pickup_datetime=timezone.now(),
            completed_at=timezone.now(),
            completed_by=self.staff,
        )

    def test_marketplace_builder_uses_completed_sale_revenue(self):
        data = report_data.build_marketplace(days=30)
        summary = {card["label"]: card["value"] for card in data["summary"]}
        self.assertEqual(summary["Completed Sales"], 1)
        self.assertEqual(summary["Sales Revenue"], "PHP 15,000.00")
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0][1], "REPORT-GOAT-001")

    def test_marketplace_report_is_in_report_center_and_renders(self):
        self.client.force_login(self.staff)
        center = self.client.get(reverse("analytics:dashboard"))
        self.assertEqual(center.status_code, 200)
        self.assertContains(center, "Marketplace Report")

        detail = self.client.get(reverse("analytics:report_marketplace"))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "PHP 15,000.00")
        self.assertContains(detail, "REPORT-GOAT-001")

    def test_marketplace_csv_export_uses_same_report_data(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("analytics:report_marketplace_export"),
            {"format": "csv", "days": "30", "status": "completed"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("Marketplace Report", content)
        self.assertIn("REPORT-GOAT-001", content)
        self.assertIn("PHP 15,000.00", content)
