from django.db import models
from django.contrib.auth.models import User


class Report(models.Model):
    """Generated reports for analytics"""
    REPORT_TYPES = [
        ('daily', 'Daily Summary'),
        ('weekly', 'Weekly Summary'),
        ('monthly', 'Monthly Summary'),
        ('custom', 'Custom Report'),
    ]
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
    ]
    
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMATS, default='pdf')
    start_date = models.DateField()
    end_date = models.DateField()
    file_path = models.CharField(max_length=500, blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.report_type})"
