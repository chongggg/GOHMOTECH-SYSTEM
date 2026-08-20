"""
Daily-summary text builder for the SMS subsystem.

The daily SMS must be a *short* digest of the same real data the dashboard and
Reports module already show — so it reuses
``analytics.report_data.build_center_summary`` (herd + automation KPIs) rather
than re-querying, adds the latest environmental reading and a count of open
high/critical notifications, and formats it to fit comfortably in one or two SMS
segments. Nothing here is fabricated: every line comes from an existing record,
and missing data is shown as such instead of invented.
"""

from django.utils import timezone

from analytics.report_data import build_center_summary
from iot.models import SensorReading
from security.models import Notification


def _card_map(cards):
    """Turn the list-of-cards from build_center_summary into {label: value}."""
    return {c['label']: c['value'] for c in cards}


def build_daily_summary_text():
    """Return a short, multi-line daily summary string for SMS.

    Reuses the Report Center KPI builder (trailing 24h window) so the SMS and
    the on-screen reports never disagree.
    """
    cards = _card_map(build_center_summary(days=1))

    now = timezone.localtime(timezone.now())
    lines = [f"GoHMoTech Daily Summary {now:%b %d %H:%M}"]

    # --- Herd snapshot ---
    lines.append(
        f"Goats: {cards.get('Total Goats', 0)} "
        f"(healthy {cards.get('Healthy', 0)}, sick {cards.get('Sick', 0)})"
    )

    # --- Automation activity (last 24h) ---
    lines.append(
        f"24h: feed {cards.get('Feeding Events', 0)}, "
        f"door {cards.get('Door Operations', 0)}, "
        f"light {cards.get('Lighting Operations', 0)}"
    )

    # --- Latest environmental reading ---
    latest = SensorReading.objects.order_by('-timestamp').first()
    if latest is not None:
        parts = []
        if latest.temperature is not None:
            parts.append(f"{round(latest.temperature, 1)}C")
        if latest.humidity is not None:
            parts.append(f"{round(latest.humidity)}%RH")
        if latest.soil_moisture is not None:
            parts.append(f"soil {round(latest.soil_moisture)}%")
        lines.append("Env: " + (", ".join(parts) if parts else "no values"))
    else:
        lines.append("Env: no readings")

    # --- Open high/critical notifications ---
    open_alerts = Notification.objects.filter(
        is_resolved=False, severity__in=['critical', 'high']
    ).count()
    lines.append(f"Open alerts (high/critical): {open_alerts}")

    return "\n".join(lines)
