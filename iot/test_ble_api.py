from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    BLEBeacon,
    BLEObservation,
    BLEReceiver,
    BLETrackingSettings,
    BLETrackingState,
    Device,
    Goat,
)


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
)
class BLEReceiverApiTests(TestCase):
    UUID = 'E2C56DB5-DFFB-48D2-B060-D0F5A71096E0'
    API_KEY = 'phase-1-test-receiver-key'

    def setUp(self):
        self.goat = Goat.objects.create(
            goat_id='298439',
            name='jericson',
            gender='male',
        )
        self.beacon = BLEBeacon.objects.create(
            goat=self.goat,
            device_name='CP101-3E95',
            mac_address='48:87:2D:9E:3E:95',
            uuid=self.UUID,
            major=1,
            minor=1,
            calibrated_rssi=-57,
        )
        device = Device.objects.create(
            device_id='phase-1-laptop',
            name='My Laptop',
            device_type='ble_receiver',
            location='Development Laptop',
        )
        self.receiver = BLEReceiver.objects.create(
            device=device,
            platform='windows',
            device_name='TEST-LAPTOP',
        )
        self.receiver.set_api_key(self.API_KEY)
        self.receiver.save(update_fields=['api_key_hash', 'updated_at'])
        self.client = APIClient()
        self.credentials = {
            'HTTP_X_RECEIVER_ID': device.device_id,
            'HTTP_AUTHORIZATION': f'Bearer {self.API_KEY}',
        }

    def post(self, url_name, payload, **credentials):
        headers = credentials or self.credentials
        return self.client.post(
            reverse(f'iot:{url_name}'),
            payload,
            format='json',
            **headers,
        )

    def test_receiver_credentials_are_required_and_invalid_keys_are_rejected(self):
        missing = self.post('ble_receiver_heartbeat', {}, invalid='ignored')
        invalid = self.client.post(
            reverse('iot:ble_receiver_heartbeat'),
            {},
            format='json',
            HTTP_X_RECEIVER_ID='phase-1-laptop',
            HTTP_AUTHORIZATION='Bearer wrong-key',
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)

    def test_heartbeat_marks_receiver_online_and_returns_config_and_assignments(self):
        response = self.post(
            'ble_receiver_heartbeat',
            {
                'scanner_version': '0.1.0',
                'device_name': 'PHASE1-WINDOWS',
                'platform': 'windows',
                'metadata': {'python': '3.14.2'},
            },
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.receiver.refresh_from_db()
        self.assertEqual(self.receiver.status, 'online')
        self.assertEqual(self.receiver.scanner_version, '0.1.0')
        self.assertIsNotNone(self.receiver.last_online)
        self.assertEqual(response.data['beacons'][0]['goat']['goat_id'], '298439')
        self.assertEqual(
            response.data['tracking_config']['out_of_range_timeout_seconds'],
            20,
        )

    def test_complete_ibeacon_identity_updates_current_state(self):
        response = self.post(
            'ble_observation_ingest',
            {
                'protocol': 'ibeacon',
                'address': '48-87-2d-9e-3e-95',
                'uuid': self.UUID.replace('-', ''),
                'major': 1,
                'minor': 1,
                'rssi': -52,
                'smoothed_rssi': -49.5,
                'sample_count': 5,
            },
        )

        self.assertEqual(response.status_code, 200, response.data)
        state = BLETrackingState.objects.get(
            beacon=self.beacon,
            receiver=self.receiver,
        )
        self.assertEqual(state.current_rssi, -52)
        self.assertEqual(state.proximity, 'very_near')
        self.assertEqual(state.status, 'detected')
        self.assertEqual(state.sample_count, 1)
        self.assertEqual(BLEObservation.objects.count(), 1)
        self.assertTrue(response.data['history_saved'])

    def test_mac_only_eddystone_frame_is_accepted_without_fabricated_identity(self):
        response = self.post(
            'ble_observation_ingest',
            {
                'protocol': 'eddystone_uid',
                'address': '48:87:2D:9E:3E:95',
                'uuid': None,
                'major': None,
                'minor': None,
                'rssi': -61,
                'smoothed_rssi': -58,
                'service_data': {
                    '0000feaa-0000-1000-8000-00805f9b34fb': '00E8'
                },
            },
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['goat']['goat_id'], '298439')
        self.assertEqual(response.data['state']['proximity'], 'near')

    def test_partial_ibeacon_identity_is_rejected(self):
        response = self.post(
            'ble_observation_ingest',
            {'uuid': self.UUID, 'major': 1, 'rssi': -55},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(BLETrackingState.objects.count(), 0)

    def test_conflicting_mac_and_ibeacon_identity_are_rejected(self):
        other_goat = Goat.objects.create(
            goat_id='G002',
            name='Other Goat',
            gender='female',
        )
        BLEBeacon.objects.create(
            goat=other_goat,
            device_name='OTHER',
            mac_address='AA:BB:CC:DD:EE:FF',
            uuid='11111111-1111-1111-1111-111111111111',
            major=2,
            minor=2,
        )

        response = self.post(
            'ble_observation_ingest',
            {
                'address': 'AA:BB:CC:DD:EE:FF',
                'uuid': self.UUID,
                'major': 1,
                'minor': 1,
                'rssi': -50,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'beacon_identity_conflict')
        self.assertEqual(BLETrackingState.objects.count(), 0)

    def test_unknown_or_disabled_beacon_is_not_accepted(self):
        self.beacon.enabled = False
        self.beacon.save(update_fields=['enabled', 'updated_at'])

        response = self.post(
            'ble_observation_ingest',
            {'address': '48:87:2D:9E:3E:95', 'rssi': -60},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['code'], 'unknown_beacon')

    def test_history_is_throttled_but_proximity_changes_are_saved(self):
        payload = {
            'address': '48:87:2D:9E:3E:95',
            'rssi': -58,
            'smoothed_rssi': -58,
        }
        first = self.post('ble_observation_ingest', payload)
        second = self.post('ble_observation_ingest', payload)
        payload.update({'rssi': -74, 'smoothed_rssi': -74})
        changed = self.post('ble_observation_ingest', payload)

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data['history_saved'])
        self.assertFalse(second.data['history_saved'])
        self.assertTrue(changed.data['history_saved'])
        self.assertEqual(BLEObservation.objects.count(), 2)
        state = BLETrackingState.objects.get()
        self.assertEqual(state.proximity, 'far')
        self.assertEqual(state.sample_count, 3)

    def test_snapshot_interval_allows_later_history(self):
        self.post(
            'ble_observation_ingest',
            {
                'address': '48:87:2D:9E:3E:95',
                'rssi': -58,
                'smoothed_rssi': -58,
            },
        )
        config = BLETrackingSettings.get_config()
        BLEObservation.objects.update(
            detected_at=timezone.now() - timedelta(
                seconds=config.history_snapshot_interval_seconds + 1
            )
        )

        response = self.post(
            'ble_observation_ingest',
            {
                'address': '48:87:2D:9E:3E:95',
                'rssi': -57,
                'smoothed_rssi': -58,
            },
        )

        self.assertTrue(response.data['history_saved'])
        self.assertEqual(BLEObservation.objects.count(), 2)


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
)
class BLEReceiverProvisioningCommandTests(TestCase):
    @mock.patch(
        'iot.management.commands.provision_ble_receiver.secrets.token_urlsafe',
        return_value='generated-receiver-secret',
    )
    def test_command_provisions_one_way_hashed_credential(self, _mock_token):
        output = StringIO()

        call_command(
            'provision_ble_receiver',
            receiver_id='phase-1-laptop',
            name='My Laptop',
            location='Development Laptop',
            platform='windows',
            stdout=output,
        )

        receiver = BLEReceiver.objects.get(device__device_id='phase-1-laptop')
        self.assertNotEqual(receiver.api_key_hash, 'generated-receiver-secret')
        self.assertTrue(receiver.check_api_key('generated-receiver-secret'))
        self.assertIn('Receiver key: generated-receiver-secret', output.getvalue())

        with self.assertRaises(CommandError):
            call_command(
                'provision_ble_receiver',
                receiver_id='phase-1-laptop',
                stdout=StringIO(),
            )
