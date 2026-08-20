from rest_framework import serializers
from .models import FeedSchedule, FeedLevel, FeedLog, AutomatedFeedingConfig


class AutomatedFeedingConfigSerializer(serializers.ModelSerializer):
    """Serializer for Automated Feeding Configuration"""
    
    class Meta:
        model = AutomatedFeedingConfig
        fields = '__all__'
        read_only_fields = ['updated_at']


class FeedScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Feed Schedule"""
    feeder_name = serializers.CharField(source='feeder.name', read_only=True)
    
    class Meta:
        model = FeedSchedule
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class FeedLevelSerializer(serializers.ModelSerializer):
    """Serializer for Feed Level"""
    feeder_name = serializers.CharField(source='feeder.name', read_only=True)
    percentage_full = serializers.ReadOnlyField()
    is_low = serializers.ReadOnlyField()
    
    class Meta:
        model = FeedLevel
        fields = [
            'id', 'feeder', 'feeder_name', 
            'current_level_grams', 'capacity_grams', 
            'low_level_threshold', 'percentage_full', 'is_low',
            'distance_cm', 'percentage',  # Ultrasonic sensor data
            'last_refilled_at', 'updated_at'
        ]
        read_only_fields = ['updated_at']


class FeedLogSerializer(serializers.ModelSerializer):
    """Serializer for Feed Log"""
    feeder_name = serializers.CharField(source='feeder.name', read_only=True)
    
    class Meta:
        model = FeedLog
        fields = '__all__'
        read_only_fields = ['timestamp']
