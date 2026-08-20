from django.core.management.base import BaseCommand
from iot.models import Device
from feeding.models import FeedLevel


class Command(BaseCommand):
    help = 'Create default feeder device and feed level'

    def handle(self, *args, **options):
        # Create or get default feeder
        feeder, created = Device.objects.get_or_create(
            device_id='FEEDER001',
            defaults={
                'name': 'Main Feeder',
                'device_type': 'feeder',
                'is_active': True,
                'location': 'Main Pasture'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created feeder: {feeder.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Feeder already exists: {feeder.name}'))
        
        # Create feed level for the feeder
        feed_level, created = FeedLevel.objects.get_or_create(
            feeder=feeder,
            defaults={
                'current_level_grams': 5000,
                'capacity_grams': 10000,
                'low_level_threshold': 1000
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created feed level for {feeder.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Feed level already exists for {feeder.name}'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Setup complete!'))
        self.stdout.write(f'Feeder ID: {feeder.id}')
        self.stdout.write(f'Feed Level: {feed_level.current_level_grams}g / {feed_level.capacity_grams}g')
