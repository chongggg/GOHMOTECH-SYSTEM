"""
Management command to populate the database with sample IoT devices and sensor data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from iot.models import Device, SensorData, Alert


class Command(BaseCommand):
    help = 'Populate database with sample IoT devices and sensor data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating sample IoT devices...')
        
        # Create sample devices
        devices_data = [
            {
                'device_id': 'TEMP_SENSOR_01',
                'name': 'Temperature Sensor - Room A',
                'device_type': 'temperature',
                'location': 'Room A - Office',
            },
            {
                'device_id': 'HUMIDITY_SENSOR_01',
                'name': 'Humidity Sensor - Room A',
                'device_type': 'humidity',
                'location': 'Room A - Office',
            },
            {
                'device_id': 'TEMP_SENSOR_02',
                'name': 'Temperature Sensor - Warehouse',
                'device_type': 'temperature',
                'location': 'Warehouse Section B',
            },
            {
                'device_id': 'PRESSURE_SENSOR_01',
                'name': 'Pressure Sensor - Production Line',
                'device_type': 'pressure',
                'location': 'Production Line 1',
            },
            {
                'device_id': 'MOTION_SENSOR_01',
                'name': 'Motion Sensor - Entrance',
                'device_type': 'motion',
                'location': 'Main Entrance',
            },
        ]
        
        devices = []
        for device_data in devices_data:
            device, created = Device.objects.get_or_create(
                device_id=device_data['device_id'],
                defaults=device_data
            )
            devices.append(device)
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Created device: {device.name}'))
            else:
                self.stdout.write(f'  Device already exists: {device.name}')
        
        # Generate sensor data for the last 7 days
        self.stdout.write('\nGenerating sensor data for the last 7 days...')
        
        now = timezone.now()
        sensor_count = 0
        
        for device in devices:
            # Generate data points every hour for the last 7 days
            for hours_ago in range(0, 7 * 24, 1):  # 168 hours (7 days)
                timestamp = now - timedelta(hours=hours_ago)
                
                if device.device_type == 'temperature':
                    value = round(random.uniform(18.0, 28.0), 2)
                    unit = 'celsius'
                    # Add some anomalies
                    if random.random() < 0.02:  # 2% chance of anomaly
                        value = round(random.uniform(35.0, 45.0), 2)
                        
                elif device.device_type == 'humidity':
                    value = round(random.uniform(40.0, 70.0), 2)
                    unit = 'percentage'
                    
                elif device.device_type == 'pressure':
                    value = round(random.uniform(1000.0, 1020.0), 2)
                    unit = 'hPa'
                    # Add some anomalies
                    if random.random() < 0.03:  # 3% chance of anomaly
                        value = round(random.uniform(980.0, 990.0), 2)
                        
                elif device.device_type == 'motion':
                    value = random.choice([0, 1])  # 0 = no motion, 1 = motion detected
                    unit = 'binary'
                else:
                    value = round(random.uniform(0, 100), 2)
                    unit = 'unknown'
                
                SensorData.objects.create(
                    device=device,
                    timestamp=timestamp,
                    sensor_type=device.device_type,
                    value=value,
                    unit=unit,
                    metadata={
                        'battery_level': random.randint(60, 100),
                        'signal_strength': random.randint(-80, -40)
                    }
                )
                sensor_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {sensor_count} sensor data points'))
        
        # Create sample alerts for anomalies
        self.stdout.write('\nCreating sample alerts...')
        
        # Find temperature anomalies
        temp_device = devices[0]  # First temperature sensor
        high_temp_readings = SensorData.objects.filter(
            device=temp_device,
            value__gte=35.0
        )[:3]  # Get first 3 anomalies
        
        alert_count = 0
        for reading in high_temp_readings:
            Alert.objects.create(
                device=reading.device,
                sensor_data=reading,
                severity='high',
                message=f'High temperature detected: {reading.value}°C (Normal range: 18-28°C)',
                is_resolved=random.choice([True, False])
            )
            alert_count += 1
        
        # Find pressure anomalies
        pressure_device = Device.objects.filter(device_type='pressure').first()
        if pressure_device:
            low_pressure_readings = SensorData.objects.filter(
                device=pressure_device,
                value__lt=995.0
            )[:2]
            
            for reading in low_pressure_readings:
                Alert.objects.create(
                    device=reading.device,
                    sensor_data=reading,
                    severity='medium',
                    message=f'Low pressure detected: {reading.value} hPa',
                    is_resolved=True,
                    resolved_at=timezone.now() - timedelta(hours=random.randint(1, 24))
                )
                alert_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {alert_count} alerts'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'Devices: {len(devices)}')
        self.stdout.write(f'Sensor Data Points: {sensor_count}')
        self.stdout.write(f'Alerts: {alert_count}')
        self.stdout.write('\nYou can now access:')
        self.stdout.write('- Devices: http://127.0.0.1:8000/api/iot/devices/')
        self.stdout.write('- Sensor Data: http://127.0.0.1:8000/api/iot/sensor-data/')
        self.stdout.write('- Alerts: http://127.0.0.1:8000/api/iot/alerts/')
        self.stdout.write('- Admin Panel: http://127.0.0.1:8000/admin/')
