import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_reserved_to_accepted(apps, schema_editor):
    Reservation = apps.get_model("marketplace", "Reservation")
    for reservation in Reservation.objects.filter(status="reserved").iterator():
        reservation.status = "accepted"
        reservation.accepted_at = reservation.reserved_at
        reservation.save(update_fields=["status", "accepted_at"])


def reverse_accepted_to_reserved(apps, schema_editor):
    Reservation = apps.get_model("marketplace", "Reservation")
    Reservation.objects.filter(status="accepted").update(status="reserved")


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0007_conversation_status_and_message_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="accepted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="pickup_location",
            field=models.CharField(
                blank=True,
                help_text="Private pickup location shown only to transaction participants.",
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="pickup_proposed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="proposed_marketplace_pickups",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="rejected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservation",
            name="rejected_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rejected_marketplace_reservations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="rejection_reason",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(migrate_reserved_to_accepted, reverse_accepted_to_reserved),
        migrations.AlterField(
            model_name="reservation",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending seller response"),
                    ("accepted", "Accepted / Reserved"),
                    ("rejected", "Rejected"),
                    ("cancelled", "Cancelled"),
                    ("completed", "Completed"),
                    ("expired", "Expired"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="pickup_status",
            field=models.CharField(
                choices=[
                    ("not_requested", "Not requested"),
                    ("requested", "Requested by buyer"),
                    ("suggested", "Alternative suggested by seller"),
                    ("confirmed", "Confirmed"),
                ],
                default="not_requested",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.CheckConstraint(
                condition=models.Q(("agreed_price__gte", 0)),
                name="reservation_price_nonnegative",
            ),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(
                fields=["buyer", "status", "-reserved_at"],
                name="reservation_buyer_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(
                fields=["listing", "status", "-reserved_at"],
                name="reservation_listing_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(
                fields=["status", "expires_at"],
                name="reservation_expiry_idx",
            ),
        ),
    ]
