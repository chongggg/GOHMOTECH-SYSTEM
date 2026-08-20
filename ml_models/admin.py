from django.contrib import admin
from .models import MLModel


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'model_type', 'version', 'is_active', 'accuracy', 'created_at']
    list_filter = ['is_active', 'model_type', 'created_at']
    search_fields = ['name', 'description', 'model_type']
