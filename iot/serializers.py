from rest_framework import serializers
from .models import Device, SensorData, Alert, ActuatorState, AutomationRule, ActuationLog, SensorReading


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'


class SensorReadingSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(write_only=True, required=False)
    device_name = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = SensorReading
        fields = ['id', 'device', 'device_id', 'device_name', 'temperature', 'humidity', 
                  'soil_moisture', 'light_intensity', 'light_raw', 'light_level_percentage',
                  'air_quality_raw', 'air_quality_voltage', 'air_quality_ppm',
                  'air_quality_calibrated', 'rain_detected', 'feeder_level', 'timestamp']
        read_only_fields = ['id', 'timestamp']
        extra_kwargs = {
            'device': {'required': False, 'allow_null': True}
        }
    
    def create(self, validated_data):
        # Handle device identification
        device_id = validated_data.pop('device_id', None)
        device_name = validated_data.pop('device_name', None)
        
        # If device is not provided, try to find/create by device_id or device_name
        if 'device' not in validated_data or validated_data.get('device') is None:
            if device_id:
                device, created = Device.objects.get_or_create(
                    device_id=device_id,
                    defaults={
                        'name': device_name or device_id,
                        'device_type': 'environmental_sensor',
                        'is_active': True
                    }
                )
                validated_data['device'] = device
            elif device_name:
                # Try to find device by name
                device = Device.objects.filter(name=device_name).first()
                if not device:
                    # Create new device
                    device = Device.objects.create(
                        device_id=device_name.lower().replace(' ', '_'),
                        name=device_name,
                        device_type='environmental_sensor',
                        is_active=True
                    )
                validated_data['device'] = device
            else:
                raise serializers.ValidationError("Either device, device_id, or device_name must be provided")
        
        return super().create(validated_data)


class SensorDataSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = SensorData
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = Alert
        fields = '__all__'


class ActuatorStateSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    device_location = serializers.CharField(source='device.location', read_only=True)
    actuator_type_display = serializers.CharField(source='get_actuator_type_display', read_only=True)
    current_state_display = serializers.CharField(source='get_current_state_display', read_only=True)
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    
    class Meta:
        model = ActuatorState
        fields = '__all__'


class AutomationRuleSerializer(serializers.ModelSerializer):
    actuator_name = serializers.CharField(source='actuator.name', read_only=True)
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AutomationRule
        fields = '__all__'


class ActuationLogSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    rule_name = serializers.CharField(source='rule.name', read_only=True, allow_null=True)
    
    class Meta:
        model = ActuationLog
        fields = '__all__'
