"""
Management command to manually trigger smart door check

Usage:
    python manage.py test_door_check
    python manage.py test_door_check --camera-id CAM-001
"""

from django.core.management.base import BaseCommand
from iot.ai_tasks import scheduled_door_check


class Command(BaseCommand):
    help = 'Manually trigger AI-powered door check for testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--camera-id',
            type=str,
            help='Camera ID to use (optional, uses first active camera if not specified)',
            default=None
        )
    
    def handle(self, *args, **options):
        camera_id = options['camera_id']
        
        self.stdout.write(self.style.WARNING('🔍 Starting manual door check...'))
        self.stdout.write(f'Camera ID: {camera_id or "Auto-detect"}')
        self.stdout.write('')
        
        # Run the task synchronously
        result = scheduled_door_check(camera_id=camera_id)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Door check complete!'))
        self.stdout.write('')
        self.stdout.write('Results:')
        self.stdout.write(f"  Status: {result.get('status')}")
        self.stdout.write(f"  Action: {result.get('action')}")
        self.stdout.write(f"  Detected: {result.get('detected_count', 0)}")
        self.stdout.write(f"  Expected: {result.get('expected_count', 0)}")
        self.stdout.write(f"  All Present: {result.get('all_present', False)}")
        
        if result.get('missing_count'):
            self.stdout.write(self.style.ERROR(f"\n⚠️  Missing {result['missing_count']} goat(s)"))
            self.stdout.write(f"  Missing IDs: {result.get('missing_goats', [])}")
        
        if result.get('status') == 'error':
            self.stdout.write(self.style.ERROR(f"\n❌ Error: {result.get('message')}"))
