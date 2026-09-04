from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0018_goat_marketplace_search_indexes"),
        ("marketplace", "0005_seller_profile"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="marketplacelisting",
            index=models.Index(
                fields=["status", "-published_at"],
                name="listing_status_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="marketplacelisting",
            index=models.Index(
                fields=["status", "price"],
                name="listing_status_price_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="marketplacelisting",
            index=models.Index(
                fields=["seller", "status"],
                name="listing_seller_status_idx",
            ),
        ),
    ]
