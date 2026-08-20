"""
Security module models.

This app introduces a single, unified, user-facing notification inbox plus a
dedicated person/intrusion detection record. It deliberately does NOT replace
the existing event models (iot.Alert, iot.MissingGoatAlert) — those remain the
authoritative records for their domains. Instead, a Notification *points at*
whichever event it represents, so the inbox is uniform and new event types can
plug in later without a schema change.
"""

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Notification(models.Model):
    """
    Unified, user-facing notification / alert inbox row.

    Why a generic relation (source_content_type + source_object_id)?
    ---------------------------------------------------------------
    Alert *events* already live in several tables — iot.Alert (device/sensor
    anomalies), iot.MissingGoatAlert (missing-goat events) and, new here,
    security.PersonDetection (intrusion events). Rather than copy those records
    or bolt read/unread state onto each one, a Notification is one inbox row
    that references the underlying event through Django's ContentType framework.
    This keeps the inbox consistent and lets future event types raise
    notifications WITHOUT altering this table.

    Trade-off vs. nullable per-source FKs: querying "the notification for this
    event" needs a ContentType lookup instead of a direct column, a tiny bit
    more indirection. At farm scale that cost is negligible and it is covered by
    an index on (source_content_type, source_object_id). The upside — no
    migration needed to support a new event type — is worth it for a system
    that is expected to grow (person, face, and other detectors were all called
    out as future work).

    Duplicate prevention
    --------------------
    One event must never create two inbox rows. Two safeguards enforce this:
      1. A DB unique constraint on (source_content_type, source_object_id).
         On MySQL, NULLs are treated as distinct, so purely informational
         notifications (no backing event) are still allowed to coexist, while
         any real event can back at most one notification.
      2. All creation funnels through security.services.create_or_update_notification,
         which uses get_or_create keyed on the source and updates in place.
    """

    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('info', 'Informational'),
    ]

    # Higher weight = more severe. Used for sorting/threshold filtering.
    SEVERITY_WEIGHT = {
        'critical': 5,
        'high': 4,
        'medium': 3,
        'low': 2,
        'info': 1,
    }

    TYPE_CHOICES = [
        ('missing_goat', 'Missing Goat'),
        ('person_detection', 'Person / Intrusion Detection'),
        ('device_anomaly', 'Device / Sensor Anomaly'),
        ('system', 'System'),
        ('other', 'Other'),
    ]

    # --- Core content ---
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default='medium', db_index=True
    )
    notification_type = models.CharField(
        max_length=30, choices=TYPE_CHOICES, default='other', db_index=True
    )
    source = models.CharField(
        max_length=120, blank=True,
        help_text="Human-readable origin, e.g. camera name or device name"
    )

    # --- Link to the underlying event (generic relation) ---
    # Nullable so a standalone informational notification can exist with no
    # backing event.
    source_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
        related_name='security_notifications'
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('source_content_type', 'source_object_id')

    # --- Read / unread state ---
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # --- Resolved / unresolved state ---
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_notifications'
    )
    resolution_notes = models.TextField(blank=True)

    # --- Metadata / timestamps ---
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['is_resolved', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['source_content_type', 'source_object_id']),
        ]
        constraints = [
            # Plain (non-conditional) unique constraint: MySQL treats NULLs as
            # distinct, so this enforces one-notification-per-event for real
            # events while still allowing many event-less info notifications.
            # (A conditional/partial constraint is intentionally avoided because
            # MySQL does not support partial indexes.)
            models.UniqueConstraint(
                fields=['source_content_type', 'source_object_id'],
                name='uniq_notification_per_source',
            )
        ]

    def __str__(self):
        state = 'read' if self.is_read else 'unread'
        return f"[{self.severity}] {self.title} ({state})"

    @property
    def severity_rank(self):
        return self.SEVERITY_WEIGHT.get(self.severity, 0)

    @property
    def resolution_time(self):
        """timedelta between creation and resolution, or None if unresolved."""
        if self.is_resolved and self.resolved_at:
            return self.resolved_at - self.created_at
        return None

    def mark_read(self, save=True):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def mark_unread(self, save=True):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            if save:
                self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def resolve(self, user=None, notes='', save=True):
        """Mark resolved. Resolving also marks the notification as read."""
        if not self.is_resolved:
            self.is_resolved = True
            self.resolved_at = timezone.now()
            self.resolved_by = user if (user and getattr(user, 'is_authenticated', False)) else None
            if notes:
                self.resolution_notes = notes
            if not self.is_read:
                self.is_read = True
                self.read_at = timezone.now()
            if save:
                self.save()

    def reopen(self, save=True):
        if self.is_resolved:
            self.is_resolved = False
            self.resolved_at = None
            self.resolved_by = None
            if save:
                self.save(update_fields=[
                    'is_resolved', 'resolved_at', 'resolved_by', 'updated_at'
                ])


class PersonDetection(models.Model):
    """
    Record of a person / intrusion detection event.

    SCOPE (per project requirements): this records only THAT a person or face
    was detected. It performs NO face recognition or identity matching — the
    project has no such capability and adding it here is explicitly out of
    scope. `detection_type` captures the coarse kind of detection; there is no
    person identity stored.

    Relationship to alerts: each detection is wired to at most ONE Notification
    (via `notification`), created through security.services. This keeps the
    detection -> event -> alert -> notification -> review -> resolve chain free
    of duplicate alerts.
    """

    DETECTION_TYPE_CHOICES = [
        ('person', 'Person Detected'),
        ('unknown_person', 'Unknown Person'),
        ('face', 'Face Detected'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewing', 'Under Review'),
        ('confirmed', 'Confirmed Threat'),
        ('dismissed', 'Dismissed / False Alarm'),
    ]

    REVIEW_STATE_CHOICES = [
        ('unreviewed', 'Unreviewed'),
        ('reviewed', 'Reviewed'),
    ]

    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    snapshot = models.ImageField(
        upload_to='person_detections/%Y/%m/%d/', null=True, blank=True,
        help_text="Snapshot image captured at detection time"
    )

    # Source camera. FK to the existing iot.IPCamera model. Nullable + SET_NULL
    # so removing a camera never destroys security history.
    camera = models.ForeignKey(
        'iot.IPCamera', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='person_detections'
    )
    source_label = models.CharField(
        max_length=200, blank=True,
        help_text="Free-text source when no camera FK applies (e.g. uploaded frame)"
    )

    detection_type = models.CharField(
        max_length=20, choices=DETECTION_TYPE_CHOICES, default='person'
    )
    confidence = models.FloatField(default=0.0, help_text="Detection confidence (0-1)")
    bounding_boxes = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='new', db_index=True
    )
    review_state = models.CharField(
        max_length=20, choices=REVIEW_STATE_CHOICES, default='unreviewed', db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_person_detections'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Direct pointer to the one notification raised for this detection.
    notification = models.OneToOneField(
        Notification, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='person_detection'
    )

    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']
        verbose_name = 'Person Detection'
        verbose_name_plural = 'Person Detections'
        indexes = [
            models.Index(fields=['-detected_at']),
            models.Index(fields=['detection_type', '-detected_at']),
            models.Index(fields=['status', '-detected_at']),
            models.Index(fields=['review_state', '-detected_at']),
        ]

    def __str__(self):
        return (
            f"{self.get_detection_type_display()} @ "
            f"{self.detected_at:%Y-%m-%d %H:%M} ({self.confidence:.2f})"
        )

    @property
    def source_display(self):
        if self.camera:
            return self.camera.name
        return self.source_label or 'Unknown source'

    def mark_reviewed(self, user=None, notes='', status=None, save=True):
        self.review_state = 'reviewed'
        self.reviewed_at = timezone.now()
        self.reviewed_by = user if (user and getattr(user, 'is_authenticated', False)) else None
        if notes:
            self.review_notes = notes
        if status:
            self.status = status
        if save:
            self.save()
