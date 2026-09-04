from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0013_create_farm_owner_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketplacelisting",
            name="is_featured",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Preferred homepage feature; displayed while this listing is available.",
            ),
        ),
    ]
