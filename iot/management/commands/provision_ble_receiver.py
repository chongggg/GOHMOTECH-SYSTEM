"""Provision or rotate an independent BLE scanner credential."""

import secrets
import socket

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.models import BLEReceiver, Device


class Command(BaseCommand):
    help = (
        'Create a BLE receiver and print its API key once. '
        'Use --rotate-key to replace an existing credential.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--receiver-id', required=True)
        parser.add_argument('--name')
        parser.add_argument('--device-name')
        parser.add_argument('--location')
        parser.add_argument(
            '--platform',
            choices=[choice[0] for choice in BLEReceiver.PLATFORM_CHOICES],
            default='windows',
        )
        parser.add_argument('--rotate-key', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        receiver_id = options['receiver_id'].strip()
        if not receiver_id:
            raise CommandError('--receiver-id cannot be empty.')

        device, device_created = Device.objects.get_or_create(
            device_id=receiver_id,
            defaults={
                'name': options['name'] or receiver_id,
                'device_type': 'ble_receiver',
                'location': options['location'] or '',
                'is_active': True,
            },
        )
        if not device_created and device.device_type != 'ble_receiver':
            raise CommandError(
                f'Device {receiver_id} exists but is not a BLE receiver.'
            )

        device_fields = []
        if options['name']:
            device.name = options['name']
            device_fields.append('name')
        if options['location'] is not None:
            device.location = options['location']
            device_fields.append('location')
        if not device.is_active:
            device.is_active = True
            device_fields.append('is_active')
        if device_fields:
            device_fields.append('updated_at')
            device.save(update_fields=device_fields)

        receiver, receiver_created = BLEReceiver.objects.get_or_create(
            device=device,
            defaults={
                'platform': options['platform'],
                'device_name': options['device_name'] or socket.gethostname(),
            },
        )
        if receiver.api_key_hash and not options['rotate_key']:
            raise CommandError(
                'This receiver already has a credential. '
                'Use --rotate-key to invalidate it and generate a new one.'
            )

        receiver.platform = options['platform']
        if options['device_name']:
            receiver.device_name = options['device_name']
        elif receiver_created:
            receiver.device_name = socket.gethostname()

        raw_api_key = secrets.token_urlsafe(32)
        receiver.set_api_key(raw_api_key)
        receiver.save()

        self.stdout.write(self.style.SUCCESS('BLE receiver provisioned.'))
        self.stdout.write(f'Receiver ID: {receiver_id}')
        self.stdout.write(f'Receiver key: {raw_api_key}')
        self.stdout.write(
            self.style.WARNING(
                'Store this key securely. Only its one-way hash is saved and '
                'the plaintext key cannot be displayed again.'
            )
        )
