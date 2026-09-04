import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0006_listing_search_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="status",
            field=models.CharField(
                choices=[("open", "Open"), ("closed", "Closed")],
                db_index=True,
                default="open",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="conversation",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="closed_marketplace_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="body",
            field=models.TextField(max_length=2000),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(
                fields=["buyer", "status", "-updated_at"],
                name="conversation_buyer_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(
                fields=["listing", "status", "-updated_at"],
                name="conversation_listing_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["conversation", "is_read", "created_at"],
                name="message_unread_idx",
            ),
        ),
    ]
