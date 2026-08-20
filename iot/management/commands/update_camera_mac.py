"""
Management command to update camera MAC address
Usage: python manage.py update_camera_mac <camera_id> <mac_address>
"""
from django.core.management.base import BaseCommand
from iot.goat_models import IPCamera


class Command(BaseCommand):
    help = 'Update camera MAC address by Camera ID or Name'

    def add_arguments(self, parser):
        parser.add_argument('camera_identifier', type=str, help='Camera ID or Name')
        parser.add_argument('mac_address', type=str, help='MAC address (e.g., AA:BB:CC:DD:EE:FF)')
        parser.add_argument('--resolve-ip', action='store_true', help='Try to resolve IP from MAC immediately')

    def handle(self, *args, **options):
        camera_identifier = options['camera_identifier']
        mac_address = options['mac_address'].upper().replace('-', ':')
        resolve_ip = options.get('resolve_ip', False)
        
        # Try to find camera by ID first, then by name
        try:
            camera = IPCamera.objects.get(camera_id=camera_identifier)
        except IPCamera.DoesNotExist:
            try:
                camera = IPCamera.objects.get(name__icontains=camera_identifier)
            except IPCamera.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Camera not found: {camera_identifier}'))
                self.stdout.write('\nAvailable cameras:')
                for cam in IPCamera.objects.all():
                    self.stdout.write(f'  - ID: {cam.camera_id}, Name: {cam.name}')
                return
        
        # Update MAC address
        old_mac = camera.mac_address
        camera.mac_address = mac_address
        
        try:
            camera.save()
            self.stdout.write(self.style.SUCCESS(f'\n✓ Updated {camera.name}'))
            self.stdout.write(f'  Old MAC: {old_mac}')
            self.stdout.write(f'  New MAC: {mac_address}')
            
            # Try to resolve IP if requested
            if resolve_ip:
                self.stdout.write('\n🔍 Scanning network for IP address...')
                if camera.update_ip_from_mac():
                    self.stdout.write(self.style.SUCCESS(f'  ✓ IP resolved: {camera.ip_address}'))
                else:
                    self.stdout.write(self.style.WARNING('  ⚠ Could not resolve IP from MAC'))
                    self.stdout.write('    Make sure camera is powered on and connected to network')
            else:
                self.stdout.write(f'  Current IP: {camera.ip_address or "Not set"}')
                self.stdout.write('\n💡 Tip: Use --resolve-ip flag to auto-discover IP from MAC')
            
            self.stdout.write(self.style.SUCCESS('\n✓ Camera updated successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error updating camera: {e}'))
