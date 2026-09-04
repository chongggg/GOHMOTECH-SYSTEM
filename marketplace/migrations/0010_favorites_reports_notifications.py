import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0009_backfill_completed_reservation_acceptance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Favorite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorites", to="marketplace.marketplacelisting")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="marketplace_favorites", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["user", "-created_at"], name="favorite_user_date_idx")],
                "constraints": [models.UniqueConstraint(fields=("user", "listing"), name="uniq_marketplace_favorite")],
            },
        ),
        migrations.CreateModel(
            name="MarketplaceReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(choices=[("suspicious", "Suspicious listing"), ("incorrect", "Incorrect information"), ("unavailable", "Goat no longer available"), ("inappropriate", "Inappropriate content"), ("scam", "Possible scam"), ("duplicate", "Duplicate listing"), ("other", "Other")], max_length=24)),
                ("description", models.TextField(blank=True, max_length=2000)),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("reviewing", "Under review"), ("resolved", "Resolved"), ("dismissed", "Dismissed")], db_index=True, default="pending", max_length=20)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_notes", models.TextField(blank=True)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reports", to="marketplace.marketplacelisting")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="marketplace_reports", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_marketplace_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "-created_at"], name="report_status_date_idx"),
                    models.Index(fields=["listing", "status"], name="report_listing_status_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("reporter", "listing"), name="uniq_reporter_listing_report")],
            },
        ),
        migrations.CreateModel(
            name="MarketplaceNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notification_type", models.CharField(choices=[("inquiry", "Inquiry"), ("message", "Message"), ("reservation", "Reservation"), ("pickup", "Pickup"), ("sale", "Sale"), ("seller_review", "Seller review"), ("report", "Listing report"), ("listing", "Listing")], db_index=True, max_length=24)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField(blank=True, max_length=1000)),
                ("dedup_key", models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggered_marketplace_notifications", to=settings.AUTH_USER_MODEL)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="marketplace.conversation")),
                ("listing", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="marketplace.marketplacelisting")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="marketplace_notifications", to=settings.AUTH_USER_MODEL)),
                ("report", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="marketplace.marketplacereport")),
                ("reservation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="marketplace.reservation")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["recipient", "is_read", "-created_at"], name="marketnotif_recipient_idx"),
                    models.Index(fields=["recipient", "notification_type", "-created_at"], name="marketnotif_type_idx"),
                ],
            },
        ),
    ]
