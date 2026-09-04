from django.db import migrations
from django.db.models import F


def backfill_completed_acceptance(apps, schema_editor):
    Reservation = apps.get_model("marketplace", "Reservation")
    Reservation.objects.filter(
        status="completed", accepted_at__isnull=True
    ).update(accepted_at=F("reserved_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0008_reservation_request_workflow"),
    ]

    operations = [
        migrations.RunPython(
            backfill_completed_acceptance,
            migrations.RunPython.noop,
        ),
    ]
