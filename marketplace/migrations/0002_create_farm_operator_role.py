from django.conf import settings
from django.db import migrations


BUYER_GROUP_NAME = "Marketplace Buyers"
FARM_OPERATOR_GROUP_NAME = "Farm Operators"


def preserve_existing_farm_access(apps, schema_editor):
    """Translate the legacy role rule into an explicit farm-operator role.

    Before this migration, every active account outside the Marketplace Buyers
    group was routed to farm operations. Preserve that access for existing
    accounts while ensuring all future accounts are marketplace-only by default.
    """
    Group = apps.get_model("auth", "Group")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    buyer_group, _ = Group.objects.get_or_create(name=BUYER_GROUP_NAME)
    farm_group, _ = Group.objects.get_or_create(name=FARM_OPERATOR_GROUP_NAME)

    buyer_ids = buyer_group.user_set.values_list("pk", flat=True)
    existing_farm_users = User.objects.filter(is_active=True).exclude(pk__in=buyer_ids)
    farm_group.user_set.add(*existing_farm_users)


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(preserve_existing_farm_access, migrations.RunPython.noop),
    ]
