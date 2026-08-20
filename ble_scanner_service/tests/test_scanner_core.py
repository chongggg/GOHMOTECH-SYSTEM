import unittest

from ble_scanner_service.config import (
    GOHMOTECH_IBEACON_UUID,
    ScannerConfig,
    normalize_mac,
    normalize_uuid,
)
from ble_scanner_service.ibeacon import (
    identify_advertisement_protocol,
    manufacturer_data_hex,
    parse_ibeacon_manufacturer_data,
    service_data_hex,
)
from ble_scanner_service.smoothing import RSSISmoother


class IBeaconParserTests(unittest.TestCase):
    def test_parses_cp101_test_beacon_payload(self):
        payload = bytes.fromhex(
            '0215'
            'E2C56DB5DFFB48D2B060D0F5A71096E0'
            '0001'
            '0001'
            'C7'
        )

        beacon = parse_ibeacon_manufacturer_data({0x004C: payload})

        self.assertEqual(beacon.company_id, 0x004C)
        self.assertEqual(beacon.uuid, GOHMOTECH_IBEACON_UUID)
        self.assertEqual(beacon.major, 1)
        self.assertEqual(beacon.minor, 1)
        self.assertEqual(beacon.measured_power, -57)
        self.assertEqual(beacon.identity, (GOHMOTECH_IBEACON_UUID, 1, 1))

    def test_ignores_non_ibeacon_manufacturer_payload(self):
        self.assertIsNone(
            parse_ibeacon_manufacturer_data({0xFFFF: bytes.fromhex('01020304')})
        )

    def test_formats_raw_manufacturer_data_for_diagnostics(self):
        self.assertEqual(
            manufacturer_data_hex({76: bytes.fromhex('0215')}),
            '0x004C:0215',
        )

    def test_labels_observed_cp101_eddystone_frames_without_faking_ibeacon(self):
        service_uuid = '0000feaa-0000-1000-8000-00805f9b34fb'
        uid_frame = bytes.fromhex('00E8E5A4A7E5A48F3132333444584C29191A0000')
        url_frame = bytes.fromhex('10E802656E2E737A64782D736D61727400')

        self.assertEqual(
            identify_advertisement_protocol(None, {service_uuid: uid_frame}),
            'eddystone_uid',
        )
        self.assertEqual(
            identify_advertisement_protocol(None, {service_uuid: url_frame}),
            'eddystone_url',
        )
        self.assertIn(uid_frame.hex().upper(), service_data_hex({service_uuid: uid_frame}))


class ScannerConfigurationTests(unittest.TestCase):
    def test_normalizes_test_beacon_identifiers(self):
        self.assertEqual(
            normalize_uuid('E2C56DB5DFFB48D2B060D0F5A71096E0'),
            GOHMOTECH_IBEACON_UUID,
        )
        self.assertEqual(normalize_mac('48-87-2d-9e-3e-95'), '48:87:2D:9E:3E:95')

    def test_windows_compatible_mode_is_default(self):
        self.assertEqual(ScannerConfig().scan_mode, 'active')

    def test_rejects_invalid_window(self):
        with self.assertRaises(ValueError):
            ScannerConfig(smoothing_window=2)


class RSSISmootherTests(unittest.TestCase):
    def test_median_rejects_single_packet_spike(self):
        smoother = RSSISmoother(window_size=5, method='median')
        for value in (-58, -57, -90, -56, -57):
            smoothed = smoother.add(value)

        self.assertEqual(smoothed, -57.0)
        self.assertEqual(smoother.count, 5)

    def test_moving_average_uses_bounded_window(self):
        smoother = RSSISmoother(window_size=3, method='moving_average')
        for value in (-90, -60, -50, -40):
            smoothed = smoother.add(value)

        self.assertAlmostEqual(smoothed, -50.0)
        self.assertEqual(smoother.count, 3)


if __name__ == '__main__':
    unittest.main()
