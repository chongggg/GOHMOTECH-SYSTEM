"""Render conventional, paper-ready ERD figures with columns, types, PKs and FKs."""

from pathlib import Path
from math import hypot

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


OUT = Path(__file__).resolve().parent / "database_schema_figures"
OUT.mkdir(exist_ok=True)

INK = "#172033"
MUTED = "#596579"
LINE = "#65748A"
HEADER = "#244A68"
HEADER_2 = "#365E7D"
PK_FILL = "#FFF4CC"
FK_FILL = "#EAF3FA"
WHITE = "#FFFFFF"
GRID = "#AEB8C5"


def table_height(fields):
    return 0.43 + 0.245 * len(fields)


def draw_table(ax, name, x, top, width, fields):
    """Draw a conventional database-table box and return its geometry."""
    row_h = 0.245
    head_h = 0.43
    height = head_h + row_h * len(fields)
    bottom = top - height

    ax.add_patch(Rectangle((x, bottom), width, height, facecolor=WHITE,
                           edgecolor=HEADER, linewidth=1.0, zorder=3))
    ax.add_patch(Rectangle((x, top - head_h), width, head_h, facecolor=HEADER,
                           edgecolor=HEADER, linewidth=0, zorder=4))
    ax.text(x + 0.10, top - head_h / 2, name, fontsize=8.4, fontweight="bold",
            color=WHITE, va="center", ha="left", zorder=5)

    key_w = 0.40
    type_w = 0.83
    field_w = width - key_w - type_w
    for i, (key, field, dtype) in enumerate(fields):
        y_top = top - head_h - i * row_h
        y_bottom = y_top - row_h
        fill = PK_FILL if "PK" in key else FK_FILL if "FK" in key else WHITE
        ax.add_patch(Rectangle((x, y_bottom), width, row_h, facecolor=fill,
                               edgecolor="none", linewidth=0, zorder=3))
        ax.plot([x, x + width], [y_bottom, y_bottom], color=GRID, lw=0.35, zorder=4)
        ax.plot([x + key_w, x + key_w], [y_bottom, y_top], color=GRID, lw=0.35, zorder=4)
        ax.plot([x + key_w + field_w, x + key_w + field_w], [y_bottom, y_top],
                color=GRID, lw=0.35, zorder=4)
        ax.text(x + key_w / 2, (y_top + y_bottom) / 2, key, fontsize=6.3,
                fontweight="bold" if key else "normal", color=INK,
                va="center", ha="center", zorder=5)
        ax.text(x + key_w + 0.06, (y_top + y_bottom) / 2, field, fontsize=6.6,
                color=INK, va="center", ha="left", zorder=5)
        ax.text(x + width - 0.06, (y_top + y_bottom) / 2, dtype, fontsize=6.1,
                color=MUTED, va="center", ha="right", zorder=5)

    return {
        "x": x, "top": top, "bottom": bottom, "w": width, "h": height,
        "left": (x, bottom + height / 2),
        "right": (x + width, bottom + height / 2),
        "center": (x + width / 2, bottom + height / 2),
    }


def nearest_sides(a, b):
    candidates = [
        (a["right"], b["left"]), (a["left"], b["right"]),
        ((a["x"] + a["w"] / 2, a["top"]), (b["x"] + b["w"] / 2, b["bottom"])),
        ((a["x"] + a["w"] / 2, a["bottom"]), (b["x"] + b["w"] / 2, b["top"])),
    ]
    return min(candidates, key=lambda p: hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]))


def relation(ax, a, b, a_card="1", b_card="0..N", label="", bend=0.0):
    start, end = nearest_sides(a, b)
    mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(hypot(dx, dy), 0.01)
    nx, ny = -dy / length * bend, dx / length * bend
    mid = (mx + nx, my + ny)
    ax.plot([start[0], mid[0], end[0]], [start[1], mid[1], end[1]],
            color=LINE, lw=0.8, zorder=1)

    def near(p, q, fraction):
        return (p[0] + (q[0] - p[0]) * fraction, p[1] + (q[1] - p[1]) * fraction)

    pa = near(start, mid, 0.16)
    pb = near(end, mid, 0.16)
    bbox = dict(facecolor=WHITE, edgecolor="none", pad=0.4, alpha=0.96)
    ax.text(pa[0], pa[1], a_card, fontsize=6.3, fontweight="bold", color=INK,
            ha="center", va="center", bbox=bbox, zorder=6)
    ax.text(pb[0], pb[1], b_card, fontsize=6.3, fontweight="bold", color=INK,
            ha="center", va="center", bbox=bbox, zorder=6)
    if label:
        ax.text(mid[0], mid[1], label, fontsize=5.9, color=MUTED,
                ha="center", va="center", bbox=bbox, zorder=6)


def render(filename, title, subtitle, tables, relations):
    fig, ax = plt.subplots(figsize=(11.69, 8.27))  # A4 landscape
    fig.patch.set_facecolor(WHITE)
    ax.set_xlim(0, 11.69)
    ax.set_ylim(0, 8.27)
    ax.axis("off")
    ax.text(0.35, 8.02, title, fontsize=14.5, fontweight="bold", color=INK, va="top")
    ax.text(0.35, 7.73, subtitle, fontsize=7.5, color=MUTED, va="top")

    boxes = {}
    for name, spec in tables.items():
        boxes[name] = draw_table(ax, name, spec[0], spec[1], spec[2], spec[3])
    for left, right, lc, rc, label, bend in relations:
        relation(ax, boxes[left], boxes[right], lc, rc, label, bend)

    ax.text(0.35, 0.20,
            "Legend: PK = primary key   FK = foreign key   UK = unique key   1 = exactly one   0..1 = optional one   0..N = zero or many",
            fontsize=6.8, color=MUTED, va="bottom")
    ax.text(11.34, 0.20, "Logical relational schema • MySQL / Django ORM",
            fontsize=6.8, color=MUTED, va="bottom", ha="right")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / f"{filename}.svg", format="svg", facecolor=WHITE)
    fig.savefig(OUT / f"{filename}_300dpi.png", format="png", dpi=300, facecolor=WHITE)
    plt.close(fig)


AUTH_USER = [
    ("PK", "id", "BIGINT"), ("UK", "username", "VARCHAR"),
    ("UK", "email", "VARCHAR"), ("", "is_active", "BOOLEAN"),
]


render(
    "erd_01_goat_monitoring",
    "Database Schema 1 — Goat Records and Camera Monitoring",
    "Conventional ERD showing table columns, SQL data types, keys, and relationship cardinalities.",
    {
        "auth_user": (0.35, 7.25, 2.35, AUTH_USER),
        "goat": (3.10, 7.25, 2.55, [
            ("PK", "id", "BIGINT"), ("UK", "goat_id", "VARCHAR"),
            ("FK", "owner_id", "BIGINT"), ("UK", "tag_number", "VARCHAR"),
            ("", "name", "VARCHAR"), ("", "breed", "VARCHAR"),
            ("", "gender", "VARCHAR"), ("", "date_of_birth", "DATE"),
            ("", "weight_kg", "FLOAT"), ("", "health_status", "VARCHAR"),
            ("", "vaccination_status", "VARCHAR"), ("", "status", "VARCHAR"),
            ("", "last_seen", "DATETIME"),
        ]),
        "goat_weight_measurement": (6.05, 7.25, 2.60, [
            ("PK", "id", "BIGINT"), ("FK", "goat_id", "BIGINT"),
            ("FK", "recorded_by_id", "BIGINT"), ("", "weight_kg", "DECIMAL"),
            ("", "source", "VARCHAR"), ("UK", "request_id", "UUID"),
            ("", "measured_at", "DATETIME"),
        ]),
        "goat_image": (9.00, 7.25, 2.35, [
            ("PK", "id", "BIGINT"), ("FK", "goat_id", "BIGINT"),
            ("", "image", "VARCHAR"), ("", "image_type", "VARCHAR"),
            ("", "is_processed", "BOOLEAN"), ("", "is_training_data", "BOOLEAN"),
            ("", "uploaded_at", "DATETIME"),
        ]),
        "ip_camera": (0.35, 4.20, 2.35, [
            ("PK", "id", "BIGINT"), ("UK", "camera_id", "VARCHAR"),
            ("", "name", "VARCHAR"), ("", "ip_address", "VARCHAR"),
            ("", "location", "VARCHAR"), ("", "status", "VARCHAR"),
            ("", "is_active", "BOOLEAN"),
        ]),
        "goat_detection_history": (3.10, 3.65, 2.55, [
            ("PK", "id", "BIGINT"), ("FK", "goat_id", "BIGINT NULL"),
            ("FK", "camera_id", "BIGINT"), ("", "bounding_box", "JSON"),
            ("", "detection_confidence", "FLOAT"),
            ("", "identification_confidence", "FLOAT"),
            ("", "is_new_goat", "BOOLEAN"), ("", "timestamp", "DATETIME"),
        ]),
        "goat_behavior_log": (6.05, 4.20, 2.60, [
            ("PK", "id", "BIGINT"), ("FK", "goat_id", "BIGINT NULL"),
            ("", "behavior_type", "VARCHAR"), ("", "confidence_score", "FLOAT"),
            ("", "detected_by", "VARCHAR"), ("", "detection_data", "JSON"),
            ("", "timestamp", "DATETIME"),
        ]),
        "missing_goat_alert": (9.00, 4.20, 2.35, [
            ("PK", "id", "BIGINT"), ("FK", "camera_id", "BIGINT NULL"),
            ("", "alert_type", "VARCHAR"), ("", "severity", "VARCHAR"),
            ("", "expected_count", "INTEGER"), ("", "detected_count", "INTEGER"),
            ("", "missing_count", "INTEGER"), ("", "is_resolved", "BOOLEAN"),
            ("", "triggered_at", "DATETIME"),
        ]),
        "missing_alert_goats": (8.75, 1.35, 2.60, [
            ("PK/FK", "missing_alert_id", "BIGINT"),
            ("PK/FK", "goat_id", "BIGINT"),
        ]),
    },
    [
        ("auth_user", "goat", "1", "0..N", "owns", 0.0),
        ("auth_user", "goat_weight_measurement", "1", "0..N", "records", 0.15),
        ("goat", "goat_weight_measurement", "1", "0..N", "has", 0.0),
        ("goat", "goat_image", "1", "0..N", "has", 0.0),
        ("goat", "goat_behavior_log", "0..1", "0..N", "behavior", -0.10),
        ("goat", "goat_detection_history", "0..1", "0..N", "identified", 0.0),
        ("ip_camera", "goat_detection_history", "1", "0..N", "captures", 0.0),
        ("ip_camera", "missing_goat_alert", "0..1", "0..N", "raises", -0.18),
        ("missing_goat_alert", "missing_alert_goats", "1", "0..N", "contains", 0.0),
        ("goat", "missing_alert_goats", "1", "0..N", "referenced by", 0.20),
    ],
)


render(
    "erd_02_iot_feeding_ble",
    "Database Schema 2 — IoT, Automated Feeding, and BLE Tracking",
    "Device readings and commands, feeder operations, and BLE proximity tracking.",
    {
        "device": (0.35, 7.25, 2.35, [
            ("PK", "id", "BIGINT"), ("UK", "device_id", "VARCHAR"),
            ("", "name", "VARCHAR"), ("", "device_type", "VARCHAR"),
            ("", "location", "VARCHAR"), ("", "is_active", "BOOLEAN"),
        ]),
        "sensor_reading": (3.05, 7.25, 2.55, [
            ("PK", "id", "BIGINT"), ("FK", "device_id", "BIGINT"),
            ("", "temperature", "FLOAT"), ("", "humidity", "FLOAT"),
            ("", "soil_moisture", "FLOAT"), ("", "air_quality_ppm", "FLOAT"),
            ("", "rain_detected", "BOOLEAN"), ("", "feeder_level", "FLOAT"),
            ("", "timestamp", "DATETIME"),
        ]),
        "automation_rule": (6.00, 7.25, 2.45, [
            ("PK", "id", "BIGINT"), ("FK", "actuator_id", "BIGINT"),
            ("", "name", "VARCHAR"), ("", "rule_type", "VARCHAR"),
            ("", "action", "VARCHAR"), ("", "criteria", "JSON"),
            ("", "priority", "INTEGER"), ("", "is_active", "BOOLEAN"),
        ]),
        "actuation_log": (8.85, 7.25, 2.50, [
            ("PK", "id", "BIGINT"), ("FK", "device_id", "BIGINT"),
            ("FK", "rule_id", "BIGINT NULL"), ("", "action", "VARCHAR"),
            ("", "source", "VARCHAR"), ("", "result", "VARCHAR"),
            ("", "timestamp", "DATETIME"),
        ]),
        "feed_schedule": (0.35, 4.25, 2.35, [
            ("PK", "id", "BIGINT"), ("FK", "feeder_id", "BIGINT"),
            ("", "schedule_time", "TIME"), ("", "amount_grams", "INTEGER"),
            ("", "days_of_week", "JSON"), ("", "is_active", "BOOLEAN"),
        ]),
        "feed_level": (3.05, 4.25, 2.55, [
            ("PK", "id", "BIGINT"), ("FK/UK", "feeder_id", "BIGINT"),
            ("", "current_level_grams", "INTEGER"), ("", "capacity_grams", "INTEGER"),
            ("", "low_level_threshold", "INTEGER"), ("", "percentage", "INTEGER"),
            ("", "updated_at", "DATETIME"),
        ]),
        "feed_log": (6.00, 4.25, 2.45, [
            ("PK", "id", "BIGINT"), ("FK", "feeder_id", "BIGINT"),
            ("FK", "schedule_id", "BIGINT NULL"), ("", "amount_dispensed", "INTEGER"),
            ("", "feeding_mode", "VARCHAR"), ("", "trigger_reason", "VARCHAR"),
            ("", "status", "VARCHAR"), ("", "timestamp", "DATETIME"),
        ]),
        "goat": (8.85, 4.25, 2.50, [
            ("PK", "id", "BIGINT"), ("UK", "goat_id", "VARCHAR"),
            ("UK", "tag_number", "VARCHAR"), ("", "name", "VARCHAR"),
            ("", "status", "VARCHAR"),
        ]),
        "ble_receiver": (0.35, 1.80, 2.35, [
            ("PK", "id", "BIGINT"), ("FK/UK", "device_id", "BIGINT"),
            ("", "platform", "VARCHAR"), ("", "status", "VARCHAR"),
            ("", "last_online", "DATETIME"),
        ]),
        "ble_beacon": (3.05, 1.80, 2.55, [
            ("PK", "id", "BIGINT"), ("FK/UK", "goat_id", "BIGINT NULL"),
            ("UK", "mac_address", "VARCHAR"), ("", "uuid", "VARCHAR"),
            ("", "battery_level", "INTEGER"), ("", "enabled", "BOOLEAN"),
        ]),
        "ble_tracking_state": (6.00, 1.80, 2.45, [
            ("PK", "id", "BIGINT"), ("FK", "beacon_id", "BIGINT"),
            ("FK", "receiver_id", "BIGINT"), ("", "smoothed_rssi", "FLOAT"),
            ("", "proximity", "VARCHAR"), ("", "status", "VARCHAR"),
            ("", "last_seen", "DATETIME"),
        ]),
        "ble_observation": (8.85, 1.80, 2.50, [
            ("PK", "id", "BIGINT"), ("FK", "beacon_id", "BIGINT"),
            ("FK", "receiver_id", "BIGINT"), ("FK", "goat_id", "BIGINT NULL"),
            ("", "rssi", "INTEGER"), ("", "proximity", "VARCHAR"),
            ("", "detected_at", "DATETIME"),
        ]),
    },
    [
        ("device", "sensor_reading", "1", "0..N", "reports", 0.0),
        ("device", "automation_rule", "1", "0..N", "actuator rules", 0.12),
        ("device", "actuation_log", "1", "0..N", "commands", 0.20),
        ("automation_rule", "actuation_log", "0..1", "0..N", "triggers", 0.0),
        ("device", "feed_schedule", "1", "0..N", "feeder", -0.08),
        ("device", "feed_level", "1", "0..1", "current level", 0.0),
        ("device", "feed_log", "1", "0..N", "feeding events", 0.12),
        ("feed_schedule", "feed_log", "0..1", "0..N", "generates", 0.0),
        ("device", "ble_receiver", "1", "0..1", "scanner host", 0.10),
        ("goat", "ble_beacon", "0..1", "0..1", "assigned", -0.16),
        ("ble_receiver", "ble_tracking_state", "1", "0..N", "maintains", 0.0),
        ("ble_beacon", "ble_tracking_state", "1", "0..N", "tracked", 0.0),
        ("ble_receiver", "ble_observation", "1", "0..N", "detects", 0.12),
        ("ble_beacon", "ble_observation", "1", "0..N", "emits", -0.12),
        ("goat", "ble_observation", "0..1", "0..N", "assignment snapshot", 0.16),
    ],
)


render(
    "erd_03_marketplace",
    "Database Schema 3 — Goat Marketplace and Support",
    "Seller approval, listings, buyer communication, reservations, favorites, reports, and support.",
    {
        "auth_user": (0.35, 7.25, 2.25, AUTH_USER),
        "seller_profile": (2.90, 7.25, 2.40, [
            ("PK", "id", "BIGINT"), ("FK/UK", "user_id", "BIGINT"),
            ("FK", "reviewed_by_id", "BIGINT NULL"), ("", "farm_name", "VARCHAR"),
            ("", "municipality", "VARCHAR"), ("", "province", "VARCHAR"),
            ("", "contact_number", "VARCHAR"), ("", "status", "VARCHAR"),
        ]),
        "goat": (5.60, 7.25, 2.20, [
            ("PK", "id", "BIGINT"), ("FK", "owner_id", "BIGINT NULL"),
            ("UK", "goat_id", "VARCHAR"), ("", "name", "VARCHAR"),
            ("", "breed", "VARCHAR"), ("", "status", "VARCHAR"),
        ]),
        "marketplace_listing": (8.10, 7.25, 2.55, [
            ("PK", "id", "BIGINT"), ("FK/UK", "goat_id", "BIGINT"),
            ("FK", "seller_id", "BIGINT"), ("", "price", "DECIMAL"),
            ("", "sales_description", "TEXT"), ("", "status", "VARCHAR"),
            ("", "published_at", "DATETIME"), ("", "sold_at", "DATETIME"),
        ]),
        "conversation": (0.35, 4.25, 2.25, [
            ("PK", "id", "BIGINT"), ("FK", "listing_id", "BIGINT"),
            ("FK", "buyer_id", "BIGINT"), ("FK", "closed_by_id", "BIGINT NULL"),
            ("", "status", "VARCHAR"), ("", "created_at", "DATETIME"),
        ]),
        "message": (2.90, 4.25, 2.40, [
            ("PK", "id", "BIGINT"), ("FK", "conversation_id", "BIGINT"),
            ("FK", "sender_id", "BIGINT"), ("", "body", "TEXT"),
            ("", "is_read", "BOOLEAN"), ("", "created_at", "DATETIME"),
        ]),
        "reservation": (5.60, 4.25, 2.20, [
            ("PK", "id", "BIGINT"), ("FK", "listing_id", "BIGINT"),
            ("FK", "buyer_id", "BIGINT"), ("FK", "conversation_id", "BIGINT NULL"),
            ("", "agreed_price", "DECIMAL"), ("", "status", "VARCHAR"),
            ("", "expires_at", "DATETIME"), ("", "pickup_datetime", "DATETIME"),
            ("", "pickup_status", "VARCHAR"),
        ]),
        "favorite": (8.10, 4.25, 2.55, [
            ("PK", "id", "BIGINT"), ("FK", "user_id", "BIGINT"),
            ("FK", "listing_id", "BIGINT"), ("", "created_at", "DATETIME"),
            ("UK", "user_id + listing_id", "COMPOSITE"),
        ]),
        "marketplace_report": (0.35, 1.78, 2.25, [
            ("PK", "id", "BIGINT"), ("FK", "reporter_id", "BIGINT"),
            ("FK", "listing_id", "BIGINT"), ("FK", "reviewed_by_id", "BIGINT NULL"),
            ("", "reason", "VARCHAR"), ("", "status", "VARCHAR"),
        ]),
        "support_ticket": (2.90, 1.78, 2.40, [
            ("PK", "id", "BIGINT"), ("UK", "ticket_number", "VARCHAR"),
            ("FK", "user_id", "BIGINT"), ("FK", "assigned_to_id", "BIGINT NULL"),
            ("FK", "related_listing_id", "BIGINT NULL"),
            ("", "category", "VARCHAR"), ("", "status", "VARCHAR"),
        ]),
        "support_message": (5.60, 1.78, 2.20, [
            ("PK", "id", "BIGINT"), ("FK", "ticket_id", "BIGINT"),
            ("FK", "sender_id", "BIGINT"), ("", "body", "TEXT"),
            ("", "created_at", "DATETIME"),
        ]),
        "support_attachment": (8.10, 1.78, 2.55, [
            ("PK", "id", "BIGINT"), ("FK", "message_id", "BIGINT"),
            ("", "file", "VARCHAR"), ("", "original_name", "VARCHAR"),
            ("", "content_type", "VARCHAR"), ("", "size", "INTEGER"),
        ]),
    },
    [
        ("auth_user", "seller_profile", "1", "0..1", "seller account", 0.0),
        ("auth_user", "goat", "1", "0..N", "owns", 0.10),
        ("goat", "marketplace_listing", "1", "0..1", "listed as", 0.0),
        ("auth_user", "marketplace_listing", "1", "0..N", "sells", 0.22),
        ("marketplace_listing", "conversation", "1", "0..N", "discussed in", -0.18),
        ("auth_user", "conversation", "1", "0..N", "buyer", 0.08),
        ("conversation", "message", "1", "0..N", "contains", 0.0),
        ("marketplace_listing", "reservation", "1", "0..N", "reserved", 0.0),
        ("conversation", "reservation", "0..1", "0..N", "supports", 0.12),
        ("marketplace_listing", "favorite", "1", "0..N", "saved", 0.0),
        ("marketplace_listing", "marketplace_report", "1", "0..N", "reported", -0.15),
        ("auth_user", "support_ticket", "1", "0..N", "opens", 0.16),
        ("support_ticket", "support_message", "1", "0..N", "contains", 0.0),
        ("support_message", "support_attachment", "1", "0..N", "has", 0.0),
    ],
)


render(
    "erd_04_security_ml_reports",
    "Database Schema 4 — Security, Machine Learning, SMS, and Reports",
    "Detection review, unified notifications, SMS delivery, ML model versions, and generated reports.",
    {
        "auth_user": (0.35, 7.25, 2.35, AUTH_USER),
        "ip_camera": (3.05, 7.25, 2.35, [
            ("PK", "id", "BIGINT"), ("UK", "camera_id", "VARCHAR"),
            ("", "name", "VARCHAR"), ("", "location", "VARCHAR"),
            ("", "status", "VARCHAR"),
        ]),
        "notification": (5.75, 7.25, 2.50, [
            ("PK", "id", "BIGINT"), ("FK", "resolved_by_id", "BIGINT NULL"),
            ("", "title", "VARCHAR"), ("", "severity", "VARCHAR"),
            ("", "notification_type", "VARCHAR"), ("", "source", "VARCHAR"),
            ("", "is_read", "BOOLEAN"), ("", "is_resolved", "BOOLEAN"),
            ("", "created_at", "DATETIME"),
        ]),
        "person_detection": (8.60, 7.25, 2.70, [
            ("PK", "id", "BIGINT"), ("FK", "camera_id", "BIGINT NULL"),
            ("FK", "reviewed_by_id", "BIGINT NULL"),
            ("FK/UK", "notification_id", "BIGINT NULL"),
            ("", "detection_type", "VARCHAR"), ("", "confidence", "FLOAT"),
            ("", "bounding_boxes", "JSON"), ("", "review_state", "VARCHAR"),
            ("", "detected_at", "DATETIME"),
        ]),
        "sms_reminder": (0.35, 4.25, 2.35, [
            ("PK", "id", "BIGINT"), ("", "title", "VARCHAR"),
            ("", "reminder_type", "VARCHAR"), ("", "message", "TEXT"),
            ("", "schedule_time", "TIME"), ("", "days_of_week", "JSON"),
            ("", "is_active", "BOOLEAN"),
        ]),
        "sms_log": (3.05, 4.25, 2.35, [
            ("PK", "id", "BIGINT"), ("FK", "notification_id", "BIGINT NULL"),
            ("FK", "reminder_id", "BIGINT NULL"), ("", "recipient", "VARCHAR"),
            ("", "message", "TEXT"), ("", "status", "VARCHAR"),
            ("", "provider", "VARCHAR"), ("", "sent_at", "DATETIME"),
        ]),
        "ml_model": (5.75, 4.25, 2.50, [
            ("PK", "id", "BIGINT"), ("FK", "uploaded_by_id", "BIGINT NULL"),
            ("", "name", "VARCHAR"), ("", "category", "VARCHAR"),
            ("", "model_type", "VARCHAR"), ("", "version", "VARCHAR"),
            ("", "status", "VARCHAR"), ("", "accuracy", "FLOAT"),
            ("", "is_active", "BOOLEAN"),
        ]),
        "ml_detection": (8.60, 4.25, 2.70, [
            ("PK", "id", "BIGINT"), ("FK", "model_id", "BIGINT NULL"),
            ("FK", "camera_id", "BIGINT NULL"), ("", "image_url", "VARCHAR"),
            ("", "goat_count", "INTEGER"), ("", "confidence", "FLOAT"),
            ("", "bounding_boxes", "JSON"), ("", "timestamp", "DATETIME"),
        ]),
        "report": (2.10, 1.65, 2.60, [
            ("PK", "id", "BIGINT"), ("FK", "generated_by_id", "BIGINT NULL"),
            ("", "title", "VARCHAR"), ("", "report_type", "VARCHAR"),
            ("", "export_format", "VARCHAR"), ("", "start_date", "DATE"),
            ("", "end_date", "DATE"), ("", "file_path", "VARCHAR"),
        ]),
        "sms_settings": (7.00, 1.65, 2.60, [
            ("PK", "id", "BIGINT"), ("", "enabled", "BOOLEAN"),
            ("", "recipient_number", "VARCHAR"), ("", "alerts_enabled", "BOOLEAN"),
            ("", "alert_min_severity", "VARCHAR"),
            ("", "reminders_enabled", "BOOLEAN"),
        ]),
    },
    [
        ("auth_user", "notification", "0..1", "0..N", "resolves", 0.12),
        ("auth_user", "person_detection", "0..1", "0..N", "reviews", 0.22),
        ("ip_camera", "person_detection", "0..1", "0..N", "captures", 0.0),
        ("notification", "person_detection", "0..1", "0..1", "represents", 0.0),
        ("notification", "sms_log", "0..1", "0..N", "delivered by", -0.10),
        ("sms_reminder", "sms_log", "0..1", "0..N", "generates", 0.0),
        ("auth_user", "ml_model", "0..1", "0..N", "uploads", 0.15),
        ("ml_model", "ml_detection", "0..1", "0..N", "performs", 0.0),
        ("ip_camera", "ml_detection", "0..1", "0..N", "source", 0.16),
        ("auth_user", "report", "0..1", "0..N", "generates", -0.15),
    ],
)

print(OUT)
