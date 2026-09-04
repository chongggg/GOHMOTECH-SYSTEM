"""Generate a paper-ready logical database schema as SVG and 300-DPI PNG."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


OUTPUT_DIR = Path(__file__).resolve().parent

COLORS = {
    "ink": "#172033",
    "muted": "#536174",
    "line": "#6B7788",
    "paper": "#FFFFFF",
    "goat": "#EAF5EE",
    "goat_head": "#2E6B4E",
    "iot": "#EAF2FA",
    "iot_head": "#2B5F8A",
    "vision": "#F3EDFA",
    "vision_head": "#69508F",
    "market": "#FFF3E5",
    "market_head": "#9A5B24",
}


def panel(ax, x, y, w, h, title, fill, number):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            linewidth=1.1, edgecolor="#C7CDD6", facecolor=fill, zorder=0,
        )
    )
    ax.text(x + 0.18, y + h - 0.22, f"{number}  {title}", fontsize=12,
            fontweight="bold", color=COLORS["ink"], va="top")


def entity(ax, x, y, w, title, fields, head_color, h=0.92):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.015,rounding_size=0.04",
            linewidth=0.9, edgecolor=head_color, facecolor=COLORS["paper"], zorder=3,
        )
    )
    ax.add_patch(Rectangle((x, y + h - 0.27), w, 0.27, linewidth=0,
                           facecolor=head_color, zorder=4))
    ax.text(x + 0.09, y + h - 0.135, title, fontsize=8.5, fontweight="bold",
            color="white", va="center", zorder=5)
    field_text = "\n".join(fields)
    ax.text(x + 0.09, y + h - 0.36, field_text, fontsize=6.6,
            color=COLORS["ink"], va="top", linespacing=1.18, zorder=5)
    return {"left": (x, y + h / 2), "right": (x + w, y + h / 2),
            "top": (x + w / 2, y + h), "bottom": (x + w / 2, y)}


def relation(ax, start, end, label="", rad=0.0, dashed=False):
    arrow = FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=7,
        connectionstyle=f"arc3,rad={rad}", linewidth=0.75,
        linestyle="--" if dashed else "-", color=COLORS["line"], zorder=2,
        shrinkA=3, shrinkB=3,
    )
    ax.add_patch(arrow)
    if label:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2 + (0.10 if rad >= 0 else -0.10)
        ax.text(mx, my, label, fontsize=6.1, color=COLORS["muted"],
                ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor="none", pad=0.7, alpha=0.92), zorder=6)


fig, ax = plt.subplots(figsize=(16.54, 11.69))  # A3 landscape
fig.patch.set_facecolor(COLORS["paper"])
ax.set_xlim(0, 16.54)
ax.set_ylim(0, 11.69)
ax.axis("off")

ax.text(0.42, 11.37, "Logical Database Schema — Smart Goat Farm Management System",
        fontsize=17, fontweight="bold", color=COLORS["ink"], va="top")
ax.text(0.42, 11.03,
        "Paper-ready overview of the principal entities and relationships; framework and audit-support tables are summarized.",
        fontsize=8.5, color=COLORS["muted"], va="top")

# Four self-contained panels keep the figure legible when placed on a landscape page.
panel(ax, 0.35, 5.78, 7.72, 4.92, "GOAT RECORDS AND MONITORING", COLORS["goat"], "A")
panel(ax, 8.47, 5.78, 7.72, 4.92, "IOT, FEEDING, AND BLE TRACKING", COLORS["iot"], "B")
panel(ax, 0.35, 0.64, 7.72, 4.82, "MARKETPLACE AND SUPPORT", COLORS["market"], "C")
panel(ax, 8.47, 0.64, 7.72, 4.82, "SECURITY, MACHINE LEARNING, AND REPORTS", COLORS["vision"], "D")

# Panel A
a_user = entity(ax, 0.65, 8.93, 1.80, "AUTH_USER", ["PK id", "username, email"], COLORS["goat_head"])
a_goat = entity(ax, 3.03, 8.93, 2.08, "GOAT", ["PK id  •  UK goat_id", "FK owner_id", "identity, health, status"], COLORS["goat_head"])
a_weight = entity(ax, 0.65, 7.45, 1.92, "GOAT_WEIGHT", ["PK id", "FK goat_id", "weight_kg, measured_at"], COLORS["goat_head"])
a_image = entity(ax, 2.85, 7.45, 1.92, "GOAT_IMAGE", ["PK id", "FK goat_id", "image, image_type"], COLORS["goat_head"])
a_behavior = entity(ax, 5.06, 7.45, 2.03, "BEHAVIOR_LOG", ["PK id", "FK goat_id (optional)", "type, confidence, time"], COLORS["goat_head"])
a_camera = entity(ax, 0.65, 6.05, 1.92, "IP_CAMERA", ["PK id  •  UK camera_id", "location, status"], COLORS["goat_head"])
a_detect = entity(ax, 2.85, 6.05, 2.05, "GOAT_DETECTION", ["PK id", "FK goat_id, camera_id", "confidence, timestamp"], COLORS["goat_head"])
a_missing = entity(ax, 5.20, 6.05, 2.05, "MISSING_ALERT", ["PK id", "FK camera_id", "counts, severity, resolved"], COLORS["goat_head"])

relation(ax, a_user["right"], a_goat["left"], "1 owner → 0..* goats")
relation(ax, a_goat["left"], a_weight["right"], "1 → 0..*", rad=-0.15)
relation(ax, a_goat["bottom"], a_image["top"], "1 → 0..*")
relation(ax, a_goat["right"], a_behavior["top"], "0..1 → 0..*", rad=0.15)
relation(ax, a_camera["right"], a_detect["left"], "1 → 0..*")
relation(ax, a_goat["bottom"], a_detect["top"], "0..1 → 0..*", rad=-0.08)
relation(ax, a_camera["right"], a_missing["left"], "0..1 → 0..*", rad=-0.16)
relation(ax, a_missing["top"], a_goat["right"], "M:N missing goats", rad=-0.20, dashed=True)

# Panel B
b_device = entity(ax, 8.78, 8.93, 1.82, "DEVICE", ["PK id  •  UK device_id", "type, location, active"], COLORS["iot_head"])
b_sensor = entity(ax, 10.93, 8.93, 1.91, "SENSOR_READING", ["PK id", "FK device_id", "environment values, time"], COLORS["iot_head"])
b_rule = entity(ax, 13.14, 8.93, 1.82, "AUTOMATION_RULE", ["PK id", "FK actuator_id", "criteria, action, priority"], COLORS["iot_head"])
b_act = entity(ax, 8.78, 7.45, 1.82, "ACTUATION_LOG", ["PK id", "FK device_id, rule_id", "action, result, time"], COLORS["iot_head"])
b_schedule = entity(ax, 10.93, 7.45, 1.91, "FEED_SCHEDULE", ["PK id", "FK feeder_id", "time, grams, weekdays"], COLORS["iot_head"])
b_level = entity(ax, 13.14, 7.45, 1.82, "FEED_LEVEL", ["PK id", "FK/UK feeder_id", "level, capacity, percent"], COLORS["iot_head"])
b_feedlog = entity(ax, 8.78, 6.05, 1.82, "FEED_LOG", ["PK id", "FK feeder_id, schedule_id", "amount, mode, status"], COLORS["iot_head"])
b_receiver = entity(ax, 10.93, 6.05, 1.91, "BLE_RECEIVER", ["PK id", "FK/UK device_id", "platform, status, online"], COLORS["iot_head"])
b_beacon = entity(ax, 13.14, 6.05, 1.82, "BLE_BEACON", ["PK id", "FK/UK goat_id", "mac, battery, enabled"], COLORS["iot_head"])
b_observe = entity(ax, 15.10, 7.14, 0.80, "BLE OBS.", ["PK id", "FK beacon", "FK receiver", "RSSI, time"], COLORS["iot_head"], h=1.22)

relation(ax, b_device["right"], b_sensor["left"], "1 → 0..*")
relation(ax, b_device["right"], b_rule["left"], "1 → 0..*", rad=0.16)
relation(ax, b_device["bottom"], b_act["top"], "1 → 0..*")
relation(ax, b_rule["bottom"], b_act["right"], "0..1 → 0..*", rad=-0.20)
relation(ax, b_device["right"], b_schedule["left"], "feeder 1 → 0..*", rad=-0.10)
relation(ax, b_device["right"], b_level["left"], "feeder 1 → 0..1", rad=0.25)
relation(ax, b_schedule["left"], b_feedlog["right"], "0..1 → 0..*", rad=-0.12)
relation(ax, b_device["bottom"], b_receiver["top"], "1 → 0..1", rad=0.18)
relation(ax, b_receiver["right"], b_observe["left"], "1 → 0..*", rad=-0.12)
relation(ax, b_beacon["right"], b_observe["left"], "1 → 0..*", rad=0.12)

# Panel C
c_user = entity(ax, 0.65, 3.74, 1.68, "AUTH_USER", ["PK id", "buyer / seller / admin"], COLORS["market_head"])
c_profile = entity(ax, 2.62, 3.74, 1.78, "SELLER_PROFILE", ["PK id", "FK/UK user_id", "farm, address, status"], COLORS["market_head"])
c_goat = entity(ax, 4.70, 3.74, 1.34, "GOAT", ["PK id", "FK owner_id"], COLORS["market_head"])
c_listing = entity(ax, 6.32, 3.74, 1.43, "LISTING", ["PK id", "FK/UK goat_id", "FK seller_id", "price, status"], COLORS["market_head"], h=1.12)
c_convo = entity(ax, 0.65, 2.23, 1.68, "CONVERSATION", ["PK id", "FK listing_id, buyer_id", "status"], COLORS["market_head"])
c_message = entity(ax, 2.62, 2.23, 1.78, "MESSAGE", ["PK id", "FK conversation_id", "FK sender_id, body"], COLORS["market_head"])
c_reserve = entity(ax, 4.70, 2.23, 1.82, "RESERVATION", ["PK id", "FK listing, buyer, convo", "price, status, pickup"], COLORS["market_head"])
c_favorite = entity(ax, 6.82, 2.23, 0.92, "FAVORITE", ["PK id", "FK user", "FK listing"], COLORS["market_head"])
c_ticket = entity(ax, 0.65, 0.88, 1.68, "SUPPORT_TICKET", ["PK id  •  UK ticket_no", "FK user_id", "category, priority, status"], COLORS["market_head"])
c_support = entity(ax, 2.62, 0.88, 1.78, "SUPPORT_MESSAGE", ["PK id", "FK ticket_id, sender_id", "body, created_at"], COLORS["market_head"])
c_notice = entity(ax, 4.70, 0.88, 1.82, "MARKET_NOTICE", ["PK id", "FK recipient_id", "optional related records"], COLORS["market_head"])
c_audit = entity(ax, 6.82, 0.88, 0.92, "AUDIT", ["activity", "reports", "account", "state"], COLORS["market_head"])

relation(ax, c_user["right"], c_profile["left"], "1 → 0..1")
relation(ax, c_user["right"], c_goat["left"], "1 → 0..*", rad=0.16)
relation(ax, c_goat["right"], c_listing["left"], "1 → 0..1")
relation(ax, c_listing["left"], c_convo["right"], "1 → 0..*", rad=-0.12)
relation(ax, c_convo["right"], c_message["left"], "1 → 0..*")
relation(ax, c_listing["bottom"], c_reserve["top"], "1 → 0..*")
relation(ax, c_listing["bottom"], c_favorite["top"], "1 → 0..*")
relation(ax, c_user["bottom"], c_ticket["top"], "1 → 0..*", rad=0.08)
relation(ax, c_ticket["right"], c_support["left"], "1 → 0..*")
relation(ax, c_user["bottom"], c_notice["top"], "recipient 1 → 0..*", rad=-0.14)

# Panel D
d_camera = entity(ax, 8.78, 3.74, 1.75, "IP_CAMERA", ["PK id", "camera_id, location"], COLORS["vision_head"])
d_person = entity(ax, 10.83, 3.74, 1.93, "PERSON_DETECTION", ["PK id", "FK camera_id", "confidence, review state"], COLORS["vision_head"])
d_notify = entity(ax, 13.06, 3.74, 1.76, "NOTIFICATION", ["PK id", "type, severity", "read / resolved state"], COLORS["vision_head"])
d_sms = entity(ax, 15.10, 3.74, 0.80, "SMS LOG", ["PK id", "FK notice", "status"], COLORS["vision_head"], h=0.92)
d_model = entity(ax, 8.78, 2.23, 1.75, "ML_MODEL", ["PK id", "name, type, version", "status, accuracy"], COLORS["vision_head"])
d_detect = entity(ax, 10.83, 2.23, 1.93, "ML_DETECTION", ["PK id", "FK model_id, device_id", "count, confidence, boxes"], COLORS["vision_head"])
d_user = entity(ax, 13.06, 2.23, 1.76, "AUTH_USER", ["PK id", "uploader / reviewer"], COLORS["vision_head"])
d_report = entity(ax, 15.10, 2.23, 0.80, "REPORT", ["PK id", "FK user", "period"], COLORS["vision_head"], h=0.92)
d_settings = entity(ax, 8.78, 0.88, 1.75, "SMS_SETTINGS", ["PK id", "recipient, alert rules"], COLORS["vision_head"])
d_reminder = entity(ax, 10.83, 0.88, 1.93, "SMS_REMINDER", ["PK id", "message, time, weekdays"], COLORS["vision_head"])
d_summary = entity(ax, 13.06, 0.88, 2.84, "SUPPORTING RECORDS", ["Security source reference • model metadata", "SMS provider response • report file path"], COLORS["vision_head"])

relation(ax, d_camera["right"], d_person["left"], "0..1 → 0..*")
relation(ax, d_person["right"], d_notify["left"], "0..1 ↔ 0..1")
relation(ax, d_notify["right"], d_sms["left"], "0..1 → 0..*")
relation(ax, d_model["right"], d_detect["left"], "0..1 → 0..*")
relation(ax, d_user["left"], d_model["right"], "uploads", rad=0.14)
relation(ax, d_user["right"], d_report["left"], "generates")
relation(ax, d_reminder["right"], d_sms["left"], "0..1 → 0..*", rad=-0.20)

# Figure legend and cross-module references.
ax.text(0.42, 0.25,
        "Notation: PK = primary key   FK = foreign key   UK = unique key   1 → 0..* = one-to-many   1 → 0..1 = one-to-zero-or-one   dashed = many-to-many",
        fontsize=7.2, color=COLORS["muted"], va="bottom")
ax.text(16.10, 0.25, "Source: application model definitions", fontsize=7.2,
        color=COLORS["muted"], va="bottom", ha="right")

plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
svg_path = OUTPUT_DIR / "database_schema_visual.svg"
png_path = OUTPUT_DIR / "database_schema_visual_300dpi.png"
fig.savefig(svg_path, format="svg", bbox_inches=None, facecolor=COLORS["paper"])
fig.savefig(png_path, format="png", dpi=300, bbox_inches=None, facecolor=COLORS["paper"])
plt.close(fig)

print(svg_path)
print(png_path)
