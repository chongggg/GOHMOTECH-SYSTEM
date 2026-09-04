from django.conf import settings
from django.db import migrations


def seed_existing_email_addresses(apps, schema_editor):
    """Register existing local emails with allauth without claiming verification."""
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    EmailAddress = apps.get_model("account", "EmailAddress")

    for user in User.objects.exclude(email="").iterator():
        email = user.email.strip().lower()
        if not email:
            continue
        EmailAddress.objects.get_or_create(
            user_id=user.pk,
            email=email,
            defaults={"primary": True, "verified": False},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0009_emailaddress_unique_primary_email"),
        ("marketplace", "0002_create_farm_operator_role"),
    ]

    operations = [
        migrations.RunPython(seed_existing_email_addresses, migrations.RunPython.noop),
    ]
