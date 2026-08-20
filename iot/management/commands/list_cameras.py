"""
Management command to list all cameras
Usage: python manage.py list_cameras
"""
from django.core.management.base import BaseCommand
from iot.goat_models import IPCamera


class Command(BaseCommand):
    help = 'List all configured cameras'

    def handle(self, *args, **options):
        cameras = IPCamera.objects.all()
        
        if not cameras.exists():
            self.stdout.write(self.style.WARNING('No cameras configured.'))
            self.stdout.write('\n💡 Add a camera:')
            self.stdout.write('   1. Go to http://localhost:8000/admin/iot/ipcamera/')
            self.stdout.write('   2. Or use: python manage.py shell')
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n📷 Found {cameras.count()} camera(s):\n'))
        self.stdout.write('=' * 100)
        
        for i, camera in enumerate(cameras, 1):
            status_symbol = '✓' if camera.status == 'active' else '✗' if camera.status == 'error' else '◯'
            active_symbol = '✓' if camera.is_active else '✗'
            
            self.stdout.write(f'\n{i}. {camera.name}')
            self.stdout.write(f'   Camera ID:    {camera.camera_id}')
            self.stdout.write(f'   Type:         {camera.get_camera_type_display()}')
            self.stdout.write(f'   MAC Address:  {camera.mac_address}')
            self.stdout.write(f'   IP Address:   {camera.ip_address or "Not set"}')
            self.stdout.write(f'   Location:     {camera.location}')
            self.stdout.write(f'   Status:       {status_symbol} {camera.get_status_display()}')
            self.stdout.write(f'   Active:       {active_symbol} {camera.is_active}')
            
            if camera.rtsp_url:
                self.stdout.write(f'   RTSP URL:     {camera.rtsp_url}')
            if camera.http_url:
                self.stdout.write(f'   HTTP URL:     {camera.http_url}')
            
            if camera.last_connected:
                self.stdout.write(f'   Last Online:  {camera.last_connected}')
            
            if camera.last_error:
                self.stdout.write(self.style.WARNING(f'   Last Error:   {camera.last_error[:80]}'))
            
            self.stdout.write('-' * 100)
        
        self.stdout.write('\n💡 Quick actions:')
        self.stdout.write('   Update MAC:   python manage.py update_camera_mac <camera_id> <mac_address>')
        self.stdout.write('   Find MACs:    python manage.py discover_cameras')
        self.stdout.write('   View in web:  http://localhost:8000/iot/cameras/')
        self.stdout.write('   Admin panel:  http://localhost:8000/admin/iot/ipcamera/')
        self.stdout.write('')
