from django.contrib import admin
from .models import FeedSchedule, FeedLevel, FeedLog, AutomatedFeedingConfig


@admin.register(AutomatedFeedingConfig)
class AutomatedFeedingConfigAdmin(admin.ModelAdmin):
    list_display = ['is_enabled', 'updated_at', 'updated_by']
    readonly_fields = ['updated_at']
    
    def has_add_permission(self, request):
        # Only allow one config instance
        return not AutomatedFeedingConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deleting the config
        return False


@admin.register(FeedSchedule)
class FeedScheduleAdmin(admin.ModelAdmin):
    list_display = ['feeder', 'schedule_time', 'amount_grams', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['feeder__name']


@admin.register(FeedLevel)
class FeedLevelAdmin(admin.ModelAdmin):
    list_display = ['feeder', 'current_level_grams', 'capacity_grams', 'percentage_full', 'is_low', 'updated_at']
    search_fields = ['feeder__name']
    readonly_fields = ['percentage_full', 'is_low']


@admin.register(FeedLog)
class FeedLogAdmin(admin.ModelAdmin):
    list_display = [
        'feeder', 'feeding_mode', 'trigger_reason', 'amount_dispensed', 
        'temperature_celsius', 'grass_health_index', 'status', 'timestamp'
    ]
    list_filter = ['feeding_mode', 'trigger_reason', 'status', 'timestamp']
    search_fields = ['feeder__name', 'trigger_reason']
    # date_hierarchy = 'timestamp'  # Commented out - requires MySQL timezone tables on Windows
    
    fieldsets = (
        ('Feeding Information', {
            'fields': ('feeder', 'amount_dispensed', 'feeding_mode', 'trigger_reason', 'status', 'error_message')
        }),
        ('Environmental Snapshot', {
            'fields': ('temperature_celsius', 'humidity_percent', 'soil_moisture_percent', 'grass_health_index'),
            'classes': ('collapse',)
        }),
        ('ML Analysis Snapshot', {
            'fields': ('goat_activity_score', 'grazing_behavior_score'),
            'classes': ('collapse',)
        }),
        ('Legacy Fields', {
            'fields': ('scheduled', 'schedule'),
            'classes': ('collapse',)
        }),
    )
