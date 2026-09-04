from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("iot", "0017_goat_owner_goat_record_source_and_more")]

    operations = [
        migrations.AddIndex(
            model_name="goat",
            index=models.Index(
                fields=["record_source", "status", "is_active"],
                name="goat_source_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="goat",
            index=models.Index(
                fields=["breed", "gender"],
                name="goat_breed_gender_idx",
            ),
        ),
    ]
