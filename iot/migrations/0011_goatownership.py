from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("iot", "0010_goatdetectionhistory_notificationlog_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GoatOwnership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_primary", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "goat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ownerships",
                        to="iot.goat",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_goats",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Goat Ownership",
                "verbose_name_plural": "Goat Ownerships",
            },
        ),
        migrations.AddIndex(
            model_name="goatownership",
            index=models.Index(fields=["owner"], name="iot_goatown_owner_i_31f6c1_idx"),
        ),
        migrations.AddIndex(
            model_name="goatownership",
            index=models.Index(fields=["goat"], name="iot_goatown_goat_id_95ff8f_idx"),
        ),
        migrations.AddConstraint(
            model_name="goatownership",
            constraint=models.UniqueConstraint(fields=("goat", "owner"), name="unique_goat_owner_pair"),
        ),
    ]
