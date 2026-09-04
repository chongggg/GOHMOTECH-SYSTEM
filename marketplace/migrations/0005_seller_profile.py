import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import marketplace.models
from django.conf import settings
from django.db import migrations, models


def approve_existing_marketplace_sellers(apps, schema_editor):
    SellerProfile = apps.get_model("marketplace", "SellerProfile")
    MarketplaceListing = apps.get_model("marketplace", "MarketplaceListing")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    now = django.utils.timezone.now()
    for user in User.objects.filter(
        pk__in=MarketplaceListing.objects.values_list("seller_id", flat=True).distinct()
    ):
        display_name = f"{user.first_name} {user.last_name}".strip() or user.username
        SellerProfile.objects.get_or_create(
            user=user,
            defaults={
                "farm_name": display_name,
                "municipality": "",
                "province": "",
                "contact_number": "",
                "farm_description": "Original GoHMoTech farm marketplace seller.",
                "status": "approved",
                "applied_at": now,
                "approved_at": now,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0004_enforce_unique_allauth_email"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SellerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("farm_name", models.CharField(max_length=150)),
                ("barangay", models.CharField(blank=True, max_length=100)),
                ("municipality", models.CharField(db_index=True, max_length=100)),
                ("province", models.CharField(db_index=True, max_length=100)),
                ("contact_number", models.CharField(max_length=24, validators=[django.core.validators.RegexValidator(message="Enter a valid contact number using digits, spaces, or hyphens.", regex="^\\+?[0-9][0-9 -]{7,22}$")])),
                ("profile_image", models.ImageField(blank=True, upload_to="seller_profiles/%Y/%m/", validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), marketplace.models.validate_profile_upload_size])),
                ("farm_description", models.TextField(max_length=2000)),
                ("address_details", models.TextField(blank=True, help_text="Private pickup/address details. Never displayed on the public profile.")),
                ("supporting_document", models.FileField(blank=True, upload_to="seller_documents/%Y/%m/", validators=[django.core.validators.FileExtensionValidator(["pdf", "jpg", "jpeg", "png"]), marketplace.models.validate_supporting_document_size])),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("approved", "Approved Seller"), ("rejected", "Rejected"), ("suspended", "Suspended")], db_index=True, default="pending", max_length=20)),
                ("review_reason", models.TextField(blank=True)),
                ("applied_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_seller_profiles", to=settings.AUTH_USER_MODEL)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="seller_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-applied_at"],
                "indexes": [
                    models.Index(fields=["status", "applied_at"], name="seller_status_applied_idx"),
                    models.Index(fields=["province", "municipality"], name="seller_location_idx"),
                ],
            },
        ),
        migrations.RunPython(
            approve_existing_marketplace_sellers,
            migrations.RunPython.noop,
        ),
    ]
