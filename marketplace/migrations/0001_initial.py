import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("iot", "0013_alter_actuationlog_result_alter_actuationlog_source"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="MarketplaceListing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
                ("sales_description", models.TextField()),
                ("status", models.CharField(choices=[("draft", "Draft"), ("available", "Available"), ("reserved", "Reserved"), ("sold", "Sold")], db_index=True, default="draft", max_length=20)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("sold_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("goat", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="marketplace_listing", to="iot.goat")),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="marketplace_listings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-published_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="marketplace_conversations", to=settings.AUTH_USER_MODEL)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conversations", to="marketplace.marketplacelisting")),
            ],
            options={"ordering": ["-updated_at"], "constraints": [models.UniqueConstraint(fields=("listing", "buyer"), name="uniq_listing_buyer_conversation")]},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="marketplace.conversation")),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="marketplace_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("agreed_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("reserved", "Reserved"), ("cancelled", "Cancelled"), ("completed", "Completed")], db_index=True, default="reserved", max_length=20)),
                ("reserved_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("pickup_datetime", models.DateTimeField(blank=True, null=True)),
                ("pickup_status", models.CharField(choices=[("not_requested", "Not requested"), ("requested", "Requested by buyer"), ("suggested", "Alternative suggested by admin"), ("confirmed", "Confirmed")], default="not_requested", max_length=20)),
                ("pickup_notes", models.TextField(blank=True)),
                ("pickup_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancellation_reason", models.TextField(blank=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="marketplace_reservations", to=settings.AUTH_USER_MODEL)),
                ("cancelled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cancelled_marketplace_reservations", to=settings.AUTH_USER_MODEL)),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="completed_marketplace_sales", to=settings.AUTH_USER_MODEL)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="marketplace.conversation")),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="marketplace.marketplacelisting")),
                ("pickup_confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_marketplace_pickups", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-reserved_at"]},
        ),
        migrations.CreateModel(
            name="MarketplaceActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(db_index=True, max_length=50)),
                ("description", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketplace_activity", to=settings.AUTH_USER_MODEL)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="activity_logs", to="marketplace.marketplacelisting")),
                ("reservation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_logs", to="marketplace.reservation")),
            ],
            options={"verbose_name_plural": "Marketplace activities", "ordering": ["-created_at"]},
        ),
    ]

