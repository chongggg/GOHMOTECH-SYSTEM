"""Admin registration for the security app."""

from django.contrib import admin

from .models import Notification, PersonDetection


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'severity', 'notification_type', 'source',
        'is_read', 'is_resolved', 'created_at',
    )
    list_filter = ('severity', 'notification_type', 'is_read', 'is_resolved', 'created_at')
    search_fields = ('title', 'description', 'source')
    date_hierarchy = 'created_at'
    readonly_fields = (
        'source_content_type', 'source_object_id', 'created_at', 'updated_at',
        'read_at', 'resolved_at',
    )
    ordering = ('-created_at',)

    # Security events must not be casually removed; keep delete for staff only
    # (Django already gates this behind the delete permission, but we make the
    # intent explicit).
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PersonDetection)
class PersonDetectionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'detection_type', 'source_display', 'confidence',
        'status', 'review_state', 'detected_at',
    )
    list_filter = ('detection_type', 'status', 'review_state', 'detected_at')
    search_fields = ('source_label', 'review_notes')
    date_hierarchy = 'detected_at'
    readonly_fields = ('created_at', 'notification')
    ordering = ('-detected_at',)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
