"""
Report data layer — single source of truth for the Reports module.

Every report is produced by a pure builder function that returns a consistent
``ReportData`` dict. Both the HTML report pages and the CSV/Excel exporters call
these builders, so the on-screen report and its exported file are always
identical (this is what makes the "verify data accuracy" step trustworthy).

Design rules honoured here:
  * Only real, existing data is queried — nothing is fabricated. Where the
    hardware/schema cannot supply something (e.g. a dedicated "physical button"
    source for doors/lights, or true lighting ON-duration), we say so in the
    report meta instead of inventing numbers.
  * Queries use aggregate()/annotate()/values() and select_related() to stay
    efficient (no per-row extra queries).
"""

from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Count, Avg, Sum, Max, Min, Q
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncDate

from iot.models import SensorReading, ActuationLog
from iot.goat_models import Goat
from feeding.models import FeedLog, FeedSchedule
from ml_models.models import Detection
from marketplace.auth import BUYER_GROUP_NAME
from marketplace.models import (
    Conversation,
    MarketplaceListing,
    MarketplaceReport,
    Reservation,
    SellerProfile,
)


User = get_user_model()


SYSTEM_NAME = "GoHMoTech — Smart Goat House Monitoring System"

# Time-period options shared by all time-based reports.
PERIOD_OPTIONS = [
    (1, "Last 24 hours"),
    (7, "Last 7 days"),
    (30, "Last 30 days"),
    (90, "Last 90 days"),
    (365, "Last 12 months"),
]


# ---------------------------------------------------------------------------
# Report registry — drives the Report Center cards and the export dispatcher.
# ---------------------------------------------------------------------------
REPORTS = {
    "inventory": {
        "title": "Goat Inventory Report",
        "description": "Herd headcount, breed, sex, age, weight, health and vaccination status.",
        "icon": "bi-clipboard-data",
        "color": "blue",
        "category": "Livestock",
        "url_name": "analytics:report_inventory",
        "time_based": False,
    },
    "vaccination": {
        "title": "Vaccination Report",
        "description": "Vaccinated, partially vaccinated, pending, upcoming and overdue vaccinations.",
        "icon": "bi-shield-plus",
        "color": "green",
        "category": "Livestock",
        "url_name": "analytics:report_vaccination",
        "time_based": False,
    },
    "health": {
        "title": "Health Report",
        "description": "Healthy, under monitoring, sick and quarantined goats with medical notes.",
        "icon": "bi-heart-pulse",
        "color": "red",
        "category": "Livestock",
        "url_name": "analytics:report_health",
        "time_based": False,
    },
    "feeder": {
        "title": "Automated Feeder Report",
        "description": "Feeding events, schedules, manual overrides and success/missed events.",
        "icon": "bi-basket",
        "color": "yellow",
        "category": "Automation",
        "url_name": "analytics:report_feeder",
        "time_based": True,
    },
    "door": {
        "title": "Automated Door Report",
        "description": "Open/close events, manual vs automatic operations and device status history.",
        "icon": "bi-door-open",
        "color": "purple",
        "category": "Automation",
        "url_name": "analytics:report_door",
        "time_based": True,
    },
    "lighting": {
        "title": "Automated Lighting Report",
        "description": "ON/OFF history, manual vs automatic activations and estimated lit time.",
        "icon": "bi-lightbulb",
        "color": "yellow",
        "category": "Automation",
        "url_name": "analytics:report_lighting",
        "time_based": True,
    },
    "environmental": {
        "title": "Environmental Monitoring Report",
        "description": "Temperature, humidity, soil moisture and light with daily trends.",
        "icon": "bi-thermometer-half",
        "color": "blue",
        "category": "Environment",
        "url_name": "analytics:report_environmental",
        "time_based": True,
    },
    "detection": {
        "title": "AI Detection Activity Report",
        "description": "Camera goat-detection activity and confidence (camera events, not herd size).",
        "icon": "bi-camera-video",
        "color": "purple",
        "category": "AI Monitoring",
        "url_name": "analytics:report_detection",
        "time_based": True,
    },
    "marketplace": {
        "title": "Marketplace Report",
        "description": "Listings, buyer inquiries, reservations, pickup status, completed sales and revenue.",
        "icon": "bi-shop",
        "color": "green",
        "category": "Marketplace",
        "url_name": "analytics:report_marketplace",
        "time_based": True,
    },
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _pct(part, whole):
    """Safe percentage, rounded to 1 dp."""
    return round((part / whole * 100), 1) if whole else 0.0


def _date_range(days):
    """Return (start, end) datetimes for a trailing ``days`` window."""
    end = timezone.now()
    start = end - timedelta(days=days)
    return start, end


def _period_label(days):
    for value, label in PERIOD_OPTIONS:
        if value == days:
            return label
    return f"Last {days} days"


def _monthly_counts_for_last_year(values, now=None):
    """Return month labels and counts for the last 12 months from a list of dates."""
    if now is None:
        now = timezone.now()

    if getattr(now, "tzinfo", None) is not None:
        now = timezone.localtime(now)
    elif not isinstance(now, datetime):
        now = datetime.combine(now, datetime.min.time())

    month_labels = []
    month_counts = []
    current_year, current_month = now.year, now.month

    buckets = {}
    for value in values or []:
        if value is None:
            continue
        if getattr(value, "tzinfo", None) is None:
            value = timezone.make_aware(value, timezone.get_default_timezone())
        bucket = (value.year, value.month)
        buckets[bucket] = buckets.get(bucket, 0) + 1

    for offset in range(11, -1, -1):
        month = current_month - offset
        year = current_year
        while month <= 0:
            month += 12
            year -= 1
        label = datetime(year, month, 1).strftime("%b %Y")
        month_labels.append(label)
        month_counts.append(buckets.get((year, month), 0))

    return month_labels, month_counts


def _card(label, value, icon, color):
    return {"label": label, "value": value, "icon": icon, "color": color}


# Palette used consistently across every chart (design-system aligned).
CHART_PALETTE = ["#1F6F3D", "#0EA5E9", "#EAB308", "#8B5CF6", "#EF4444",
                 "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#EC4899"]


def _chart(chart_id, ctype, title, labels, datasets):
    """A self-describing chart descriptor the generic template can render.

    ``datasets`` is a list of ``{"label": str, "data": [numbers]}``.
    ``ctype`` is one of: doughnut, bar, line.
    """
    return {"id": chart_id, "type": ctype, "title": title,
            "labels": labels, "datasets": datasets}


def _select(name, label, options, value):
    """A filter-form control descriptor. ``options`` is [(value, label)]."""
    return {"kind": "select", "name": name, "label": label,
            "options": options, "value": value}


def _search(name, label, value):
    return {"kind": "search", "name": name, "label": label, "value": value}


def _period_control(value):
    return {"kind": "select", "name": "days", "label": "Period",
            "options": [(str(v), l) for v, l in PERIOD_OPTIONS], "value": str(value)}


def _base(report_type, filters, extra_note=""):
    """Common envelope fields for every report."""
    meta = REPORTS[report_type]
    return {
        "report_type": report_type,
        "title": meta["title"],
        "description": meta["description"],
        "category": meta["category"],
        "icon": meta["icon"],
        "color": meta["color"],
        "system_name": SYSTEM_NAME,
        "generated_at": timezone.now(),
        "filters": filters,          # applied filters: list of (label, value)
        "filter_form": [],           # filter controls: list of descriptors
        "note": extra_note,          # honest caveats about data availability
        "summary": [],               # list of KPI cards
        "charts": [],                # list of chart descriptors
        "columns": [],               # detail-table headers
        "rows": [],                  # list of lists (export-ready, ordered)
        "time_based": meta["time_based"],
    }


# ---------------------------------------------------------------------------
# LIVESTOCK REPORTS  (snapshot of current herd — Goat model)
# ---------------------------------------------------------------------------
def _display_map(choices):
    return dict(choices)


def build_inventory(status="all", breed="all", gender="all",
                    health="all", vaccination="all", search=""):
    filters = [
        ("Status", dict(Goat.STATUS_CHOICES).get(status, "All")),
        ("Breed", dict(Goat.BREED_CHOICES).get(breed, "All")),
        ("Sex", dict(Goat.GENDER_CHOICES).get(gender, "All")),
        ("Health", dict(Goat.HEALTH_STATUS_CHOICES).get(health, "All")),
        ("Vaccination", dict(Goat.VACCINATION_STATUS_CHOICES).get(vaccination, "All")),
    ]
    if search:
        filters.append(("Search", search))

    qs = Goat.objects.all()
    if status != "all":
        qs = qs.filter(status=status)
    if breed != "all":
        qs = qs.filter(breed=breed)
    if gender != "all":
        qs = qs.filter(gender=gender)
    if health != "all":
        qs = qs.filter(health_status=health)
    if vaccination != "all":
        qs = qs.filter(vaccination_status=vaccination)
    if search:
        qs = qs.filter(Q(goat_id__icontains=search) | Q(name__icontains=search))

    data = _base("inventory", filters)
    data["filter_form"] = [
        _select("status", "Status", [("all", "All")] + list(Goat.STATUS_CHOICES), status),
        _select("breed", "Breed", [("all", "All")] + list(Goat.BREED_CHOICES), breed),
        _select("gender", "Sex", [("all", "All")] + list(Goat.GENDER_CHOICES), gender),
        _select("health", "Health", [("all", "All")] + list(Goat.HEALTH_STATUS_CHOICES), health),
        _select("vaccination", "Vaccination",
                [("all", "All")] + list(Goat.VACCINATION_STATUS_CHOICES), vaccination),
        _search("search", "Search ID / name", search),
    ]

    total = qs.count()
    # Status split is computed on the *unfiltered* herd for the herd-wide KPIs,
    # but the table + distributions reflect the filtered selection.
    herd = Goat.objects.all()
    active = herd.filter(status="active").count()
    sold = herd.filter(status="sold").count()
    dead = herd.filter(status="dead").count()
    missing = herd.filter(status="missing").count()
    thirty_days_ago = timezone.now() - timedelta(days=30)
    newly_added = herd.filter(date_added__gte=thirty_days_ago).count()

    data["summary"] = [
        _card("Goats (in view)", total, "bi-collection", "blue"),
        _card("Active", active, "bi-check-circle", "green"),
        _card("Sold", sold, "bi-tag", "purple"),
        _card("Dead", dead, "bi-x-octagon", "red"),
        _card("Missing", missing, "bi-question-octagon", "yellow"),
        _card("New (30 days)", newly_added, "bi-plus-circle", "green"),
    ]

    # --- Distributions (charts) ---
    breed_names = _display_map(Goat.BREED_CHOICES)
    breed_rows = qs.values("breed").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "breed", "bar", "Population by Breed",
        [breed_names.get(r["breed"], r["breed"]) for r in breed_rows],
        [{"label": "Goats", "data": [r["c"] for r in breed_rows]}],
    ))

    gender_names = _display_map(Goat.GENDER_CHOICES)
    gender_rows = qs.values("gender").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "gender", "doughnut", "Sex Distribution",
        [gender_names.get(r["gender"], r["gender"] or "Unspecified") for r in gender_rows],
        [{"label": "Goats", "data": [r["c"] for r in gender_rows]}],
    ))

    # Age groups (computed in Python from date_of_birth)
    age_buckets = {"Kid (<6 mo)": 0, "Young (6–12 mo)": 0, "Adult (1–3 yr)": 0,
                   "Senior (>3 yr)": 0, "Unknown": 0}
    weights = []
    for g in qs.only("date_of_birth", "weight_kg"):
        days = g.age_days
        if days is None:
            age_buckets["Unknown"] += 1
        elif days < 182:
            age_buckets["Kid (<6 mo)"] += 1
        elif days < 365:
            age_buckets["Young (6–12 mo)"] += 1
        elif days < 1095:
            age_buckets["Adult (1–3 yr)"] += 1
        else:
            age_buckets["Senior (>3 yr)"] += 1
        if g.weight_kg:
            weights.append(float(g.weight_kg))
    data["charts"].append(_chart(
        "age", "bar", "Age Groups",
        list(age_buckets.keys()),
        [{"label": "Goats", "data": list(age_buckets.values())}],
    ))

    health_names = _display_map(Goat.HEALTH_STATUS_CHOICES)
    health_rows = qs.values("health_status").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "health", "doughnut", "Health Distribution",
        [health_names.get(r["health_status"], r["health_status"]) for r in health_rows],
        [{"label": "Goats", "data": [r["c"] for r in health_rows]}],
    ))

    vacc_names = _display_map(Goat.VACCINATION_STATUS_CHOICES)
    vacc_rows = qs.values("vaccination_status").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "vaccination", "doughnut", "Vaccination Status",
        [vacc_names.get(r["vaccination_status"], r["vaccination_status"]) for r in vacc_rows],
        [{"label": "Goats", "data": [r["c"] for r in vacc_rows]}],
    ))

    # Monthly registrations (last 12 months) — trend line
    year_ago = timezone.now() - timedelta(days=365)
    monthly_values = list(
        herd.filter(date_added__gte=year_ago).values_list("date_added", flat=True)
    )
    labels, counts = _monthly_counts_for_last_year(monthly_values, now=timezone.now())
    data["charts"].append(_chart(
        "monthly", "line", "New Registrations (12 months)",
        labels,
        [{"label": "Goats added", "data": counts}],
    ))

    # Weight summary note
    if weights:
        data["note"] = (
            f"Weight recorded for {len(weights)} of {total} goats in view — "
            f"avg {round(sum(weights) / len(weights), 1)} kg "
            f"(min {round(min(weights), 1)} kg, max {round(max(weights), 1)} kg)."
        )
    else:
        data["note"] = "No weights recorded for goats in the current view."

    # --- Detail table ---
    data["columns"] = ["Goat ID", "Name", "Breed", "Sex", "Age", "Weight (kg)",
                       "Health", "Vaccination", "Status", "Date Added"]
    data["rows"] = [
        [
            g.goat_id,
            g.name or "—",
            g.get_breed_display(),
            g.get_gender_display(),
            g.age_display,
            g.weight_kg if g.weight_kg is not None else "—",
            g.get_health_status_display(),
            g.get_vaccination_status_display(),
            g.get_status_display(),
            g.date_added.strftime("%Y-%m-%d"),
        ]
        for g in qs.order_by("goat_id")
    ]
    return data


def build_vaccination(vaccination="all"):
    filters = [("Vaccination status",
                dict(Goat.VACCINATION_STATUS_CHOICES).get(vaccination, "All"))]

    # Vaccination reporting concerns living stock; exclude sold/dead animals.
    qs = Goat.objects.exclude(status__in=["sold", "dead"])
    if vaccination != "all":
        qs = qs.filter(vaccination_status=vaccination)

    data = _base("vaccination", filters)
    data["filter_form"] = [
        _select("vaccination", "Vaccination status",
                [("all", "All")] + list(Goat.VACCINATION_STATUS_CHOICES), vaccination),
    ]

    today = timezone.now().date()
    soon = today + timedelta(days=30)
    fully = qs.filter(vaccination_status="fully_vaccinated").count()
    partially = qs.filter(vaccination_status="partially_vaccinated").count()
    not_vacc = qs.filter(vaccination_status="not_vaccinated").count()
    unknown = qs.filter(vaccination_status="unknown").count()
    upcoming = qs.filter(next_due_date__gte=today, next_due_date__lte=soon).count()
    overdue = qs.filter(next_due_date__lt=today).count()

    data["summary"] = [
        _card("Fully Vaccinated", fully, "bi-shield-check", "green"),
        _card("Partially", partially, "bi-shield-exclamation", "yellow"),
        _card("Not Vaccinated", not_vacc, "bi-shield-x", "red"),
        _card("Unknown", unknown, "bi-shield", "blue"),
        _card("Upcoming (30 days)", upcoming, "bi-calendar-check", "purple"),
        _card("Overdue", overdue, "bi-calendar-x", "red"),
    ]

    vacc_names = _display_map(Goat.VACCINATION_STATUS_CHOICES)
    rows = qs.values("vaccination_status").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "status", "doughnut", "Vaccination Status",
        [vacc_names.get(r["vaccination_status"], r["vaccination_status"]) for r in rows],
        [{"label": "Goats", "data": [r["c"] for r in rows]}],
    ))

    data["note"] = (
        "Vaccination history shows the most recent vaccine on record per goat. "
        "A dedicated per-dose vaccination log is recommended for full history "
        "(see report recommendations)."
    )

    data["columns"] = ["Goat ID", "Name", "Vaccination Status", "Last Vaccine",
                       "Vaccinated On", "Next Due", "Due State"]
    detail = []
    for g in qs.order_by("next_due_date"):
        if g.next_due_date and g.next_due_date < today:
            due_state = "Overdue"
        elif g.next_due_date and g.next_due_date <= soon:
            due_state = "Upcoming"
        elif g.next_due_date:
            due_state = "Scheduled"
        else:
            due_state = "—"
        detail.append([
            g.goat_id,
            g.name or "—",
            g.get_vaccination_status_display(),
            g.vaccine_name or "—",
            g.vaccination_date.strftime("%Y-%m-%d") if g.vaccination_date else "—",
            g.next_due_date.strftime("%Y-%m-%d") if g.next_due_date else "—",
            due_state,
        ])
    data["rows"] = detail
    return data


def build_health(health="all"):
    filters = [("Health status",
                dict(Goat.HEALTH_STATUS_CHOICES).get(health, "All"))]

    qs = Goat.objects.exclude(status__in=["sold", "dead"])
    if health != "all":
        qs = qs.filter(health_status=health)

    data = _base("health", filters)
    data["filter_form"] = [
        _select("health", "Health status",
                [("all", "All")] + list(Goat.HEALTH_STATUS_CHOICES), health),
    ]

    healthy = qs.filter(health_status="healthy").count()
    monitoring = qs.filter(health_status="monitoring").count()
    sick = qs.filter(health_status="sick").count()
    quarantine = qs.filter(health_status="quarantine").count()

    data["summary"] = [
        _card("Healthy", healthy, "bi-heart", "green"),
        _card("Under Monitoring", monitoring, "bi-eye", "yellow"),
        _card("Sick", sick, "bi-thermometer-high", "red"),
        _card("Quarantined", quarantine, "bi-shield-lock", "purple"),
    ]

    health_names = _display_map(Goat.HEALTH_STATUS_CHOICES)
    rows = qs.values("health_status").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "distribution", "doughnut", "Health Distribution",
        [health_names.get(r["health_status"], r["health_status"]) for r in rows],
        [{"label": "Goats", "data": [r["c"] for r in rows]}],
    ))

    data["note"] = (
        "Health status is the current per-goat status on record. Historical "
        "health trends require a dated health-event log (recommended enhancement)."
    )

    # Detail focuses on goats needing attention first.
    data["columns"] = ["Goat ID", "Name", "Breed", "Health Status", "Medical Notes"]
    priority = {"sick": 0, "quarantine": 1, "monitoring": 2, "healthy": 3}
    goats = sorted(qs, key=lambda g: (priority.get(g.health_status, 9), g.goat_id))
    data["rows"] = [
        [
            g.goat_id,
            g.name or "—",
            g.get_breed_display(),
            g.get_health_status_display(),
            (g.health_notes or "—").replace("\n", " ").strip()[:200] or "—",
        ]
        for g in goats
    ]
    return data


# ---------------------------------------------------------------------------
# AUTOMATION REPORTS (event logs)
# ---------------------------------------------------------------------------
def build_feeder(days=7):
    start, end = _date_range(days)
    filters = [("Period", _period_label(days))]
    data = _base("feeder", filters)
    data["filter_form"] = [_period_control(days)]

    logs = FeedLog.objects.filter(timestamp__gte=start).select_related("feeder", "schedule")

    total = logs.count()
    dispensed = logs.aggregate(s=Sum("amount_dispensed"))["s"] or 0
    successful = logs.filter(status="success").count()
    failed = logs.filter(status__in=["failed", "partial"]).count()
    manual = logs.filter(trigger_reason="manual_override").count()
    scheduled = logs.filter(trigger_reason="time_based").count()

    data["summary"] = [
        _card("Total Feedings", total, "bi-basket", "yellow"),
        _card("Feed Dispensed (g)", dispensed, "bi-droplet", "blue"),
        _card("Successful", successful, "bi-check-circle", "green"),
        _card("Failed / Partial", failed, "bi-exclamation-triangle", "red"),
        _card("Manual Overrides", manual, "bi-hand-index", "purple"),
        _card("Scheduled", scheduled, "bi-clock", "green"),
    ]

    # By feeding mode (chart)
    mode_names = _display_map(FeedLog.FEEDING_MODE_CHOICES)
    mode_rows = logs.values("feeding_mode").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "mode", "doughnut", "Feedings by Mode",
        [mode_names.get(r["feeding_mode"], r["feeding_mode"]) for r in mode_rows],
        [{"label": "Feedings", "data": [r["c"] for r in mode_rows]}],
    ))

    # Daily feeding activity (chart)
    daily = (
        logs.annotate(d=TruncDate("timestamp")).values("d")
        .annotate(count=Count("id"), grams=Sum("amount_dispensed")).order_by("d")
    )
    day_labels = [r["d"].strftime("%b %d") for r in daily if r["d"]]
    data["charts"].append(_chart(
        "daily", "bar", "Daily Feeding Activity", day_labels,
        [
            {"label": "Feedings", "data": [r["count"] for r in daily if r["d"]]},
            {"label": "Grams dispensed", "data": [r["grams"] or 0 for r in daily if r["d"]]},
        ],
    ))

    active_schedules = FeedSchedule.objects.filter(is_active=True).count()
    data["note"] = (
        f"Success rate {_pct(successful, total)}%. "
        f"{active_schedules} active feeding schedule(s) configured. "
        "A missed feeding is reported as a failed/partial log; scheduled feeds "
        "with no log are not yet tracked (recommended enhancement)."
    )

    trig_names = _display_map(FeedLog.TRIGGER_REASON_CHOICES)
    mode_names_full = _display_map(FeedLog.FEEDING_MODE_CHOICES)
    status_names = _display_map(FeedLog.STATUS_CHOICES)
    data["columns"] = ["Date & Time", "Feeder", "Amount (g)", "Mode", "Trigger", "Status"]
    data["rows"] = [
        [
            l.timestamp.strftime("%Y-%m-%d %H:%M"),
            l.feeder.name if l.feeder else "—",
            l.amount_dispensed,
            mode_names_full.get(l.feeding_mode, l.feeding_mode),
            trig_names.get(l.trigger_reason, l.trigger_reason),
            status_names.get(l.status, l.status),
        ]
        for l in logs.order_by("-timestamp")
    ]
    return data


def _actuation_report(report_type, actions, days):
    """Shared builder for door (open/close) and lighting (turn_on/turn_off)."""
    start, end = _date_range(days)
    filters = [("Period", _period_label(days))]
    data = _base(report_type, filters)
    data["filter_form"] = [_period_control(days)]

    logs = (
        ActuationLog.objects.filter(timestamp__gte=start, action__in=actions)
        .select_related("device")
    )

    total = logs.count()
    successful = logs.filter(result="success").count()
    manual = logs.filter(source="manual").count()
    automatic = logs.exclude(source="manual").count()  # rule/system/api
    act_a, act_b = actions
    count_a = logs.filter(action=act_a).count()
    count_b = logs.filter(action=act_b).count()

    action_names = _display_map(ActuationLog.ACTION_TYPES)
    source_names = _display_map(ActuationLog.SOURCE_TYPES)

    data["summary"] = [
        _card("Total Operations", total, "bi-arrow-repeat", "purple"),
        _card(action_names[act_a], count_a, "bi-box-arrow-up", "green"),
        _card(action_names[act_b], count_b, "bi-box-arrow-down", "blue"),
        _card("Manual", manual, "bi-hand-index", "yellow"),
        _card("Automatic", automatic, "bi-robot", "green"),
    ]

    # Source distribution (chart) — real sources only: manual/rule/system/api
    src_rows = logs.values("source").annotate(c=Count("id")).order_by("-c")
    data["charts"].append(_chart(
        "source", "doughnut", "Operations by Source",
        [source_names.get(r["source"], r["source"]) for r in src_rows],
        [{"label": "Operations", "data": [r["c"] for r in src_rows]}],
    ))

    # Daily operations split by action (chart)
    daily = (
        logs.annotate(d=TruncDate("timestamp")).values("d").annotate(
            a=Count("id", filter=Q(action=act_a)),
            b=Count("id", filter=Q(action=act_b)),
        ).order_by("d")
    )
    day_labels = [r["d"].strftime("%b %d") for r in daily if r["d"]]
    data["charts"].append(_chart(
        "daily", "bar", "Daily Operations", day_labels,
        [
            {"label": action_names[act_a], "data": [r["a"] for r in daily if r["d"]]},
            {"label": action_names[act_b], "data": [r["b"] for r in daily if r["d"]]},
        ],
    ))

    note = f"Success rate {_pct(successful, total)}%. "
    if report_type == "lighting":
        # Estimate lit time by pairing turn_on -> turn_off per device.
        lit = _estimate_on_duration(logs, on_action="turn_on", off_action="turn_off")
        data["summary"].append(
            _card("Est. Lit Time (h)", round(lit, 1), "bi-hourglass-split", "yellow")
        )
        note += ("Estimated lit time is derived by pairing ON→OFF events; only "
                 "ON/OFF events are stored, so true duration is an estimate. ")
    note += ("Trigger sources are Manual, Automation Rule, System or API — a "
             "dedicated 'physical button' source is not recorded by the firmware "
             "(recommended enhancement).")
    data["note"] = note

    data["columns"] = ["Date & Time", "Device", "Action", "Source", "Triggered By", "Result"]
    data["rows"] = [
        [
            l.timestamp.strftime("%Y-%m-%d %H:%M"),
            l.device.name if l.device else "—",
            action_names.get(l.action, l.action),
            source_names.get(l.source, l.source),
            l.triggered_by or "—",
            l.result.title(),
        ]
        for l in logs.order_by("-timestamp")
    ]
    return data


def _estimate_on_duration(logs, on_action, off_action):
    """Estimate total ON hours by pairing ON→OFF events per device (asc time)."""
    total_seconds = 0.0
    by_device = {}
    for l in logs.order_by("timestamp"):
        dev = l.device_id
        if l.action == on_action:
            by_device[dev] = l.timestamp
        elif l.action == off_action and by_device.get(dev):
            total_seconds += (l.timestamp - by_device[dev]).total_seconds()
            by_device[dev] = None
    return total_seconds / 3600.0


def build_door(days=7):
    return _actuation_report("door", ("open", "close"), days)


def build_lighting(days=7):
    return _actuation_report("lighting", ("turn_on", "turn_off"), days)


# ---------------------------------------------------------------------------
# ENVIRONMENT REPORT (SensorReading)
# ---------------------------------------------------------------------------
def build_environmental(days=7):
    start, end = _date_range(days)
    filters = [("Period", _period_label(days))]
    data = _base("environmental", filters)
    data["filter_form"] = [_period_control(days)]

    readings = SensorReading.objects.filter(timestamp__gte=start).select_related("device")
    total = readings.count()

    agg = readings.aggregate(
        t_avg=Avg("temperature"), t_min=Min("temperature"), t_max=Max("temperature"),
        h_avg=Avg("humidity"), h_min=Min("humidity"), h_max=Max("humidity"),
        s_avg=Avg("soil_moisture"), l_avg=Avg("light_level_percentage"),
        aq_raw_avg=Avg("air_quality_raw"), aq_ppm_avg=Avg("air_quality_ppm"),
    )

    def _r(v, unit=""):
        return f"{round(v, 1)}{unit}" if v is not None else "—"

    data["summary"] = [
        _card("Total Readings", total, "bi-clipboard-data", "blue"),
        _card("Avg Temp", _r(agg["t_avg"], "°C"), "bi-thermometer-half", "red"),
        _card("Avg Humidity", _r(agg["h_avg"], "%"), "bi-droplet-half", "blue"),
        _card("Avg Soil Moisture", _r(agg["s_avg"], "%"), "bi-moisture", "green"),
        _card("Avg Indoor Light", _r(agg["l_avg"], "%"), "bi-brightness-high", "yellow"),
        _card("Avg MQ-135 Raw", _r(agg["aq_raw_avg"]), "bi-wind", "purple"),
        _card("Avg Calibrated Air", _r(agg["aq_ppm_avg"], " ppm"), "bi-cloud-haze2", "green"),
    ]

    # Daily temp/humidity trend (chart)
    daily = (
        readings.annotate(d=TruncDate("timestamp")).values("d").annotate(
            t=Avg("temperature"), h=Avg("humidity"),
        ).order_by("d")
    )
    day_labels = [r["d"].strftime("%b %d") for r in daily if r["d"]]
    data["charts"].append(_chart(
        "daily", "line", "Daily Temperature & Humidity", day_labels,
        [
            {"label": "Avg Temp (°C)",
             "data": [round(r["t"], 1) if r["t"] is not None else None for r in daily if r["d"]]},
            {"label": "Avg Humidity (%)",
             "data": [round(r["h"], 1) if r["h"] is not None else None for r in daily if r["d"]]},
        ],
    ))

    daily_environment = (
        readings.annotate(d=TruncDate("timestamp")).values("d").annotate(
            light=Avg("light_level_percentage"), air=Avg("air_quality_ppm"),
        ).order_by("d")
    )
    env_labels = [r["d"].strftime("%b %d") for r in daily_environment if r["d"]]
    data["charts"].append(_chart(
        "indoor_environment", "line", "Indoor Light & Calibrated Air Quality", env_labels,
        [
            {"label": "Avg light (%)", "data": [round(r["light"], 1) if r["light"] is not None else None for r in daily_environment if r["d"]]},
            {"label": "Avg MQ-135 estimate (ppm)", "data": [round(r["air"], 1) if r["air"] is not None else None for r in daily_environment if r["d"]]},
        ],
    ))

    if agg["t_avg"] is not None:
        data["note"] = (
            f"Temperature range {_r(agg['t_min'], '°C')} – {_r(agg['t_max'], '°C')}, "
            f"humidity range {_r(agg['h_min'], '%')} – {_r(agg['h_max'], '%')} "
            f"over {_period_label(days).lower()}."
        )
    else:
        data["note"] = "No environmental sensor readings recorded for this period."

    data["columns"] = ["Date & Time", "Device", "Temp (°C)", "Humidity (%)",
                       "Soil Moisture (%)", "Light (%)", "Light Raw",
                       "MQ-135 Raw", "MQ-135 Voltage", "Air Estimate (ppm)", "Calibrated", "Rain"]
    data["rows"] = [
        [
            r.timestamp.strftime("%Y-%m-%d %H:%M"),
            r.device.name if r.device else "—",
            round(r.temperature, 1) if r.temperature is not None else "—",
            round(r.humidity, 1) if r.humidity is not None else "—",
            round(r.soil_moisture, 1) if r.soil_moisture is not None else "—",
            round(r.light_level_percentage, 1) if r.light_level_percentage is not None else "—",
            r.light_raw if r.light_raw is not None else "—",
            r.air_quality_raw if r.air_quality_raw is not None else "—",
            round(r.air_quality_voltage, 3) if r.air_quality_voltage is not None else "—",
            round(r.air_quality_ppm, 1) if r.air_quality_ppm is not None else "—",
            "Yes" if r.air_quality_calibrated else "No",
            "Yes" if r.rain_detected else "No",
        ]
        for r in readings.order_by("-timestamp")[:500]
    ]
    return data


# ---------------------------------------------------------------------------
# AI DETECTION REPORT (Detection) — kept separate and clearly labelled
# ---------------------------------------------------------------------------
def build_detection(days=7):
    start, end = _date_range(days)
    filters = [("Period", _period_label(days))]
    data = _base("detection", filters)
    data["filter_form"] = [_period_control(days)]

    detections = Detection.objects.filter(timestamp__gte=start).select_related("camera", "model")
    total = detections.count()
    agg = detections.aggregate(
        avg_count=Avg("goat_count"), max_count=Max("goat_count"),
        avg_conf=Avg("confidence"),
    )

    data["summary"] = [
        _card("Detections", total, "bi-camera-video", "purple"),
        _card("Avg Goats / Frame", round(agg["avg_count"], 1) if agg["avg_count"] else 0,
              "bi-collection", "blue"),
        _card("Peak Count", agg["max_count"] or 0, "bi-graph-up-arrow", "green"),
        _card("Avg Confidence", f"{round((agg['avg_conf'] or 0) * 100, 1)}%",
              "bi-bullseye", "yellow"),
    ]

    daily = (
        detections.annotate(d=TruncDate("timestamp")).values("d").annotate(
            avg=Avg("goat_count"), c=Count("id"),
        ).order_by("d")
    )
    day_labels = [r["d"].strftime("%b %d") for r in daily if r["d"]]
    data["charts"].append(_chart(
        "daily", "line", "Daily Detection Activity", day_labels,
        [
            {"label": "Avg goats / frame",
             "data": [round(r["avg"], 1) if r["avg"] is not None else 0 for r in daily if r["d"]]},
            {"label": "Detections", "data": [r["c"] for r in daily if r["d"]]},
        ],
    ))

    data["note"] = (
        "These are camera detection events from the AI model — they reflect how "
        "many goats the cameras saw per frame, NOT the registered herd size. Use "
        "the Goat Inventory report for authoritative headcount."
    )

    data["columns"] = ["Date & Time", "Camera", "Goats Detected", "Confidence", "Model"]
    data["rows"] = [
        [
            d.timestamp.strftime("%Y-%m-%d %H:%M"),
            d.camera.name if d.camera else "Test Upload",
            d.goat_count,
            f"{round(d.confidence * 100, 1)}%" if d.confidence is not None else "—",
            d.model.name if d.model else "—",
        ]
        for d in detections.order_by("-timestamp")[:500]
    ]
    return data


# ---------------------------------------------------------------------------
# MARKETPLACE REPORT — current listings plus period-based buyer transactions
# ---------------------------------------------------------------------------
def build_marketplace(days=30, status="all", search=""):
    start, end = _date_range(days)
    status_names = _display_map(Reservation.STATUS_CHOICES)
    filters = [("Period", _period_label(days))]
    if status != "all":
        filters.append(("Transaction status", status_names.get(status, status)))
    if search:
        filters.append(("Search", search))

    data = _base("marketplace", filters)
    data["filter_form"] = [
        _period_control(days),
        _select(
            "status",
            "Transaction status",
            [("all", "All")] + list(Reservation.STATUS_CHOICES),
            status,
        ),
        _search("search", "Search goat / buyer", search),
    ]

    listings = MarketplaceListing.objects.select_related("goat", "seller__seller_profile")
    transactions = Reservation.objects.filter(reserved_at__gte=start).select_related(
        "listing__goat", "buyer", "completed_by"
    )
    if status != "all":
        transactions = transactions.filter(status=status)
    if search:
        transactions = transactions.filter(
            Q(listing__goat__goat_id__icontains=search)
            | Q(listing__goat__tag_number__icontains=search)
            | Q(listing__goat__name__icontains=search)
            | Q(buyer__username__icontains=search)
            | Q(buyer__first_name__icontains=search)
            | Q(buyer__last_name__icontains=search)
        )

    inquiries = Conversation.objects.filter(created_at__gte=start)
    completed = transactions.filter(status=Reservation.COMPLETED)
    revenue = completed.aggregate(total=Sum("agreed_price"))["total"] or 0
    active_reservations = MarketplaceListing.objects.filter(
        status=MarketplaceListing.RESERVED
    ).count()
    seller_profiles = SellerProfile.objects.all()
    approved_sellers = seller_profiles.filter(status=SellerProfile.APPROVED).count()
    pending_sellers = seller_profiles.filter(status=SellerProfile.PENDING).count()
    registered_buyers = User.objects.filter(
        groups__name=BUYER_GROUP_NAME,
        is_active=True,
    ).distinct().count()
    pending_reports = MarketplaceReport.objects.filter(
        status__in=[MarketplaceReport.PENDING, MarketplaceReport.REVIEWING]
    ).count()
    average_price = listings.filter(
        status__in=[MarketplaceListing.AVAILABLE, MarketplaceListing.RESERVED]
    ).aggregate(value=Avg("price"))["value"] or 0

    data["summary"] = [
        _card(
            "Available Listings",
            listings.filter(status=MarketplaceListing.AVAILABLE).count(),
            "bi-tags",
            "green",
        ),
        _card("Buyer Inquiries", inquiries.count(), "bi-chat-dots", "blue"),
        _card("Reservations in Period", transactions.count(), "bi-bookmark-check", "purple"),
        _card("Currently Reserved", active_reservations, "bi-hourglass-split", "yellow"),
        _card("Completed Sales", completed.count(), "bi-bag-check", "green"),
        _card("Sales Revenue", f"PHP {revenue:,.2f}", "bi-cash-stack", "green"),
        _card("Registered Buyers", registered_buyers, "bi-people", "blue"),
        _card("Approved Sellers", approved_sellers, "bi-patch-check", "green"),
        _card("Pending Sellers", pending_sellers, "bi-person-exclamation", "yellow"),
        _card("Average Active Price", f"PHP {average_price:,.2f}", "bi-tag", "purple"),
        _card("Open Reports", pending_reports, "bi-flag", "yellow"),
    ]

    listing_status_names = _display_map(MarketplaceListing.STATUS_CHOICES)
    listing_status_rows = listings.values("status").annotate(c=Count("id")).order_by("status")
    data["charts"].append(_chart(
        "listing_status",
        "doughnut",
        "Current Listing Status",
        [listing_status_names.get(row["status"], row["status"]) for row in listing_status_rows],
        [{"label": "Listings", "data": [row["c"] for row in listing_status_rows]}],
    ))

    seller_status_names = _display_map(SellerProfile.STATUS_CHOICES)
    seller_status_rows = seller_profiles.values("status").annotate(c=Count("id")).order_by("status")
    data["charts"].append(_chart(
        "seller_status",
        "doughnut",
        "Seller Approval Status",
        [seller_status_names.get(row["status"], row["status"]) for row in seller_status_rows],
        [{"label": "Sellers", "data": [row["c"] for row in seller_status_rows]}],
    ))

    breed_rows = (
        listings.filter(status__in=[MarketplaceListing.AVAILABLE, MarketplaceListing.RESERVED])
        .values("goat__breed")
        .annotate(c=Count("id"))
        .order_by("-c", "goat__breed")[:10]
    )
    breed_names = _display_map(Goat.BREED_CHOICES)
    data["charts"].append(_chart(
        "listed_breeds",
        "bar",
        "Most Listed Breeds",
        [breed_names.get(row["goat__breed"], row["goat__breed"] or "Unspecified") for row in breed_rows],
        [{"label": "Active listings", "data": [row["c"] for row in breed_rows]}],
    ))

    location_rows = (
        listings.filter(status__in=[MarketplaceListing.AVAILABLE, MarketplaceListing.RESERVED])
        .exclude(seller__seller_profile__province="")
        .values("seller__seller_profile__province")
        .annotate(c=Count("id"))
        .order_by("-c", "seller__seller_profile__province")[:10]
    )
    data["charts"].append(_chart(
        "listing_locations",
        "bar",
        "Active Listings by Province",
        [row["seller__seller_profile__province"] for row in location_rows],
        [{"label": "Listings", "data": [row["c"] for row in location_rows]}],
    ))

    period_transactions = Reservation.objects.filter(reserved_at__gte=start)
    transaction_status_rows = (
        period_transactions.values("status").annotate(c=Count("id")).order_by("status")
    )
    data["charts"].append(_chart(
        "transaction_status",
        "bar",
        "Reservation Outcomes in Period",
        [status_names.get(row["status"], row["status"]) for row in transaction_status_rows],
        [{"label": "Transactions", "data": [row["c"] for row in transaction_status_rows]}],
    ))

    daily_sales = (
        Reservation.objects.filter(status=Reservation.COMPLETED, completed_at__gte=start)
        .annotate(d=TruncDate("completed_at"))
        .values("d")
        .annotate(sales=Count("id"), revenue=Sum("agreed_price"))
        .order_by("d")
    )
    data["charts"].append(_chart(
        "sales_trend",
        "line",
        "Completed Sales & Revenue Trend",
        [row["d"].strftime("%b %d") for row in daily_sales if row["d"]],
        [
            {"label": "Sales", "data": [row["sales"] for row in daily_sales if row["d"]]},
            {"label": "Revenue (PHP)", "data": [float(row["revenue"] or 0) for row in daily_sales if row["d"]]},
        ],
    ))

    completed_count = Reservation.objects.filter(
        status=Reservation.COMPLETED, completed_at__gte=start
    ).count()
    data["note"] = (
        f"Marketplace activity covers {_period_label(days).lower()}. Current listing counts are a live snapshot. "
        f"Sales revenue includes only completed transactions; reservations are not treated as sales. "
        f"Inquiry-to-sale conversion for the period is {_pct(completed_count, inquiries.count())}%. "
        f"Seller and buyer totals are current account snapshots; exact private seller addresses are never included."
    )

    pickup_names = _display_map(Reservation.PICKUP_STATUS_CHOICES)
    data["columns"] = [
        "Requested At", "Goat", "Buyer", "Agreed Price", "Status",
        "Pickup Status", "Pickup Schedule", "Completed / Cancelled",
    ]
    data["rows"] = [
        [
            timezone.localtime(item.reserved_at).strftime("%Y-%m-%d %H:%M"),
            item.listing.goat.goat_id,
            item.buyer.get_full_name() or item.buyer.username,
            f"PHP {item.agreed_price:,.2f}",
            status_names.get(item.status, item.status),
            pickup_names.get(item.pickup_status, item.pickup_status),
            timezone.localtime(item.pickup_datetime).strftime("%Y-%m-%d %H:%M")
            if item.pickup_datetime else "—",
            timezone.localtime(
                item.completed_at or item.cancelled_at or item.rejected_at
            ).strftime("%Y-%m-%d %H:%M")
            if (item.completed_at or item.cancelled_at or item.rejected_at) else "—",
        ]
        for item in transactions.order_by("-reserved_at")[:500]
    ]
    return data


# ---------------------------------------------------------------------------
# Report Center summary (landing-page KPI cards — existing data only)
# ---------------------------------------------------------------------------
def build_center_summary(days=7):
    """KPI cards for the Report Center landing page.

    Every value comes from real records; nothing is fabricated. Automation
    counts cover the trailing ``days`` window, herd counts are current.
    """
    start, _ = _date_range(days)
    herd = Goat.objects.all()
    living = herd.exclude(status__in=["sold", "dead"])

    feeding_events = FeedLog.objects.filter(timestamp__gte=start).count()
    door_ops = ActuationLog.objects.filter(
        timestamp__gte=start, action__in=["open", "close"]).count()
    light_ops = ActuationLog.objects.filter(
        timestamp__gte=start, action__in=["turn_on", "turn_off"]).count()
    marketplace_sales = Reservation.objects.filter(
        status=Reservation.COMPLETED, completed_at__gte=start
    ).count()

    return [
        _card("Total Goats", herd.count(), "bi-collection", "blue"),
        _card("Healthy", living.filter(health_status="healthy").count(), "bi-heart", "green"),
        _card("Vaccinated", living.filter(vaccination_status="fully_vaccinated").count(),
              "bi-shield-check", "green"),
        _card("Sick", living.filter(health_status="sick").count(), "bi-thermometer-high", "red"),
        _card("Sold", herd.filter(status="sold").count(), "bi-tag", "purple"),
        _card("Dead", herd.filter(status="dead").count(), "bi-x-octagon", "red"),
        _card("Feeding Events", feeding_events, "bi-basket", "yellow"),
        _card("Door Operations", door_ops, "bi-door-open", "purple"),
        _card("Lighting Operations", light_ops, "bi-lightbulb", "yellow"),
        _card("Marketplace Sales", marketplace_sales, "bi-bag-check", "green"),
    ]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
def _int_days(get, default=7):
    try:
        return int(get.get("days", default))
    except (TypeError, ValueError):
        return default


def build_report(report_type, get):
    """Build a report from a request.GET QueryDict of filters."""
    if report_type == "inventory":
        return build_inventory(
            status=get.get("status", "all"),
            breed=get.get("breed", "all"),
            gender=get.get("gender", "all"),
            health=get.get("health", "all"),
            vaccination=get.get("vaccination", "all"),
            search=get.get("search", "").strip(),
        )
    if report_type == "vaccination":
        return build_vaccination(vaccination=get.get("vaccination", "all"))
    if report_type == "health":
        return build_health(health=get.get("health", "all"))
    if report_type == "feeder":
        return build_feeder(days=_int_days(get))
    if report_type == "door":
        return build_door(days=_int_days(get))
    if report_type == "lighting":
        return build_lighting(days=_int_days(get))
    if report_type == "environmental":
        return build_environmental(days=_int_days(get))
    if report_type == "detection":
        return build_detection(days=_int_days(get))
    if report_type == "marketplace":
        return build_marketplace(
            days=_int_days(get, default=30),
            status=get.get("status", "all"),
            search=get.get("search", "").strip(),
        )
    raise ValueError(f"Unknown report type: {report_type}")
