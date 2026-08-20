from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from iot.models import Device


class AutomatedFeedingConfig(models.Model):
    """Global configuration for automated feeding system"""
    is_enabled = models.BooleanField(
        default=True,
        help_text="Master switch for automated feeding"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = "Automated Feeding Configuration"
        verbose_name_plural = "Automated Feeding Configuration"
    
    def __str__(self):
        status = "ENABLED" if self.is_enabled else "DISABLED"
        return f"Automated Feeding: {status}"
    
    @classmethod
    def get_config(cls):
        """Get or create the configuration"""
        config, created = cls.objects.get_or_create(id=1)
        return config


class FeedSchedule(models.Model):
    """Automated feeding schedule"""
    DAYS_OF_WEEK = [
        (0, 'Sunday'),
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
    ]
    
    feeder = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='feed_schedules',
        limit_choices_to={'device_type': 'feeder'}
    )
    schedule_time = models.TimeField(help_text="Time to dispense feed")
    amount_grams = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Amount of feed in grams"
    )
    is_active = models.BooleanField(default=True)
    days_of_week = models.JSONField(
        default=list,
        help_text="List of day numbers (0=Sunday, 6=Saturday)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['schedule_time']

    def __str__(self):
        return f"{self.feeder.name} - {self.schedule_time} ({self.amount_grams}g)"


class FeedLevel(models.Model):
    """Current feed level in feeder"""
    feeder = models.OneToOneField(
        Device,
        on_delete=models.CASCADE,
        related_name='feed_level',
        limit_choices_to={'device_type': 'feeder'}
    )
    current_level_grams = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0
    )
    capacity_grams = models.IntegerField(
        validators=[MinValueValidator(1)],
        default=10000
    )
    low_level_threshold = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=1000,
        help_text="Alert when feed level drops below this"
    )
    # Ultrasonic sensor data (from ESP32)
    distance_cm = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance measured by ultrasonic sensor (cm)"
    )
    percentage = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Feed level percentage from ultrasonic sensor (0-100%)"
    )
    last_refilled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.feeder.name} - {self.current_level_grams}g / {self.capacity_grams}g"

    @property
    def percentage_full(self):
        """Calculate percentage of feed remaining"""
        if self.capacity_grams == 0:
            return 0
        return (self.current_level_grams / self.capacity_grams) * 100

    @property
    def is_low(self):
        """Check if feed level is below threshold"""
        return self.current_level_grams < self.low_level_threshold


class FeedLog(models.Model):
    """Log of all feeding events"""
    STATUS_CHOICES = [
        ('pending', 'Pending Execution'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ]
    
    FEEDING_MODE_CHOICES = [
        ('automated', 'Automated (Environment + ML)'),
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual'),
    ]
    
    TRIGGER_REASON_CHOICES = [
        # Environmental triggers
        ('drought_detected', 'Drought Detected'),
        ('low_soil_moisture', 'Low Soil Moisture'),
        ('high_temp_low_humidity', 'High Temperature + Low Humidity'),
        ('poor_grass_health', 'Poor Grass Health (Computer Vision)'),
        ('rainfall_detected', 'Rainfall Detected - Feeding Adjusted'),
        
        # ML triggers
        ('reduced_grazing', 'Reduced Grazing Behavior (ML)'),
        ('inactive_goats', 'Inactive Goats During Feeding Hours (ML)'),
        ('abnormal_behavior', 'Abnormal Goat Behavior (ML)'),
        ('ml_feeding_required', 'ML Flagged: Feeding Assistance Required'),
        
        # Manual/Scheduled
        ('time_based', 'Time-Based Schedule'),
        ('manual_override', 'Manual Override by User'),
        ('physical_button', 'Physical Button Press'),
        ('emergency', 'Emergency Feeding'),
        ('testing', 'System Testing'),
    ]
    
    feeder = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='feed_logs'
    )
    amount_dispensed = models.IntegerField(
        validators=[MinValueValidator(0)]
    )
    
    # NEW: Feeding mode classification
    feeding_mode = models.CharField(
        max_length=20,
        choices=FEEDING_MODE_CHOICES,
        default='manual',
        help_text="Primary classification of feeding trigger",
        db_index=True
    )
    
    # NEW: Specific trigger reason
    trigger_reason = models.CharField(
        max_length=50,
        choices=TRIGGER_REASON_CHOICES,
        default='manual_override',
        help_text="Specific reason why feeding was activated"
    )
    
    # NEW: Environmental data snapshot at feeding time
    temperature_celsius = models.FloatField(null=True, blank=True)
    humidity_percent = models.FloatField(null=True, blank=True)
    soil_moisture_percent = models.FloatField(null=True, blank=True)
    grass_health_index = models.FloatField(null=True, blank=True, help_text="0-1 scale, computer vision derived")
    
    # NEW: ML-derived data
    goat_activity_score = models.FloatField(null=True, blank=True, help_text="0-1 scale, ML confidence")
    grazing_behavior_score = models.FloatField(null=True, blank=True, help_text="0-1 scale, ML confidence")
    
    # Existing fields
    scheduled = models.BooleanField(
        default=False,
        help_text="Was this a scheduled feeding or manual?"
    )
    schedule = models.ForeignKey(
        FeedSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='success'
    )
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['feeder', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.feeder.name} - {self.amount_dispensed}g at {self.timestamp}"
