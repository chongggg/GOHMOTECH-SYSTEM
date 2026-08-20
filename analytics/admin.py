from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'export_format', 'start_date', 'end_date', 'created_at']
    list_filter = ['report_type', 'export_format', 'created_at']
    search_fields = ['title']
    # date_hierarchy = 'created_at'  # Commented out - requires MySQL timezone tables on Windows
