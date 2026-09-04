from django.db import migrations


FARM_OWNER_GROUP_NAME = "Farm Owners"
FARM_OPERATOR_GROUP_NAME = "Farm Operators"


def create_owner_role_and_preserve_operations(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    owner_group, _ = Group.objects.get_or_create(name=FARM_OWNER_GROUP_NAME)
    operator_group, _ = Group.objects.get_or_create(name=FARM_OPERATOR_GROUP_NAME)

    # The legacy group had full operational control. Preserve those accounts'
    # abilities by moving them to Farm Owner; newly assigned operators are read-only.
    existing_users = list(operator_group.user_set.all())
    if existing_users:
        owner_group.user_set.add(*existing_users)
        operator_group.user_set.remove(*existing_users)


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0012_alter_marketplacenotification_notification_type_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_owner_role_and_preserve_operations,
            migrations.RunPython.noop,
        ),
    ]
