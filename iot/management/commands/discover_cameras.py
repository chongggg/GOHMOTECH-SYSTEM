"""
Management command to discover cameras on the network and display their MAC addresses
Usage: python manage.py discover_cameras
"""
from django.core.management.base import BaseCommand
import subprocess
import re
import platform


class Command(BaseCommand):
    help = 'Discover network devices and display their IP and MAC addresses (helps find camera MAC)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Network Device Discovery - Find Your Camera MAC Address'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        devices = self.scan_network()
        
        if devices:
            self.stdout.write(self.style.SUCCESS(f'\nFound {len(devices)} device(s) on network:\n'))
            self.stdout.write(f"{'IP Address':<18} {'MAC Address':<20} {'Status'}")
            self.stdout.write('-' * 70)
            
            for device in devices:
                ip = device.get('ip', 'N/A')
                mac = device.get('mac', 'N/A')
                status = device.get('status', 'Unknown')
                
                # Highlight likely camera IPs
                if any(cam_ip in ip for cam_ip in ['192.168.1.', '192.168.0.', '10.0.0.']):
                    self.stdout.write(
                        self.style.SUCCESS(f"{ip:<18} {mac:<20} {status}")
                    )
                else:
                    self.stdout.write(f"{ip:<18} {mac:<20} {status}")
            
            self.stdout.write('\n')
            self.stdout.write(self.style.WARNING('📷 Tips for identifying your camera:'))
            self.stdout.write('   1. Check your router\'s admin page for connected devices')
            self.stdout.write('   2. Look for manufacturer names like "Hikvision", "Dahua", "TP-Link"')
            self.stdout.write('   3. Your camera\'s MAC address is usually printed on a label')
            self.stdout.write('   4. Try accessing http://[IP_ADDRESS] in your browser')
            self.stdout.write('\n')
            self.stdout.write(self.style.SUCCESS('✓ Once you find your camera\'s MAC, add it in:'))
            self.stdout.write('   Django Admin → IoT → IP Cameras → Add Camera')
            self.stdout.write('   Enter the MAC address (e.g., AA:BB:CC:DD:EE:FF)')
            self.stdout.write('   The system will auto-discover the IP when needed!')
            
        else:
            self.stdout.write(self.style.WARNING('No devices found. Make sure:'))
            self.stdout.write('   - You are connected to the same network as your camera')
            self.stdout.write('   - The camera is powered on')
            self.stdout.write('   - Your firewall allows ARP requests')
        
        self.stdout.write('')

    def scan_network(self):
        """Scan network using ARP table"""
        devices = []
        
        try:
            system = platform.system()
            
            if system == 'Windows':
                # Windows: use 'arp -a'
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
                output = result.stdout
                
                # Parse Windows ARP format
                # Example: 192.168.1.100    aa-bb-cc-dd-ee-ff     dynamic
                for line in output.split('\n'):
                    # Match IP and MAC pattern
                    match = re.search(
                        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2})\s+(\w+)',
                        line
                    )
                    if match:
                        ip = match.group(1)
                        mac = match.group(2).upper().replace('-', ':')
                        status = match.group(3)
                        
                        # Filter out multicast and broadcast
                        if not ip.startswith('224.') and not ip.endswith('.255'):
                            devices.append({
                                'ip': ip,
                                'mac': mac,
                                'status': status
                            })
            
            else:
                # Linux/Unix: try 'ip neigh' first
                try:
                    result = subprocess.run(['ip', 'neigh'], capture_output=True, text=True, timeout=10)
                    output = result.stdout
                    
                    for line in output.split('\n'):
                        # Example: 192.168.1.100 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
                        match = re.search(
                            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})\s+(\w+)',
                            line
                        )
                        if match:
                            devices.append({
                                'ip': match.group(1),
                                'mac': match.group(2).upper(),
                                'status': match.group(3)
                            })
                except:
                    pass
                
                # Fallback to 'arp -n'
                if not devices:
                    result = subprocess.run(['arp', '-n'], capture_output=True, text=True, timeout=10)
                    output = result.stdout
                    
                    for line in output.split('\n'):
                        parts = line.split()
                        if len(parts) >= 3:
                            # Try to extract IP and MAC
                            ip_match = re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', parts[0])
                            mac_match = re.match(r'[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}', parts[2] if len(parts) > 2 else '')
                            
                            if ip_match and mac_match:
                                devices.append({
                                    'ip': parts[0],
                                    'mac': parts[2].upper(),
                                    'status': 'active'
                                })
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error scanning network: {e}'))
        
        return devices
