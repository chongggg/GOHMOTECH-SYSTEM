"""Standards-focused parser for iBeacon manufacturer advertisements."""

from dataclasses import dataclass
import uuid as uuid_lib


IBEACON_TYPE = b'\x02\x15'
IBEACON_PAYLOAD_LENGTH = 23


@dataclass(frozen=True)
class IBeaconAdvertisement:
    company_id: int
    uuid: str
    major: int
    minor: int
    measured_power: int

    @property
    def identity(self):
        return self.uuid, self.major, self.minor


def parse_ibeacon_manufacturer_data(manufacturer_data):
    """Parse the first valid iBeacon payload from Bleak manufacturer data."""
    for company_id, payload in (manufacturer_data or {}).items():
        raw = bytes(payload)
        if len(raw) < IBEACON_PAYLOAD_LENGTH or raw[:2] != IBEACON_TYPE:
            continue

        beacon_uuid = str(uuid_lib.UUID(bytes=raw[2:18])).upper()
        major = int.from_bytes(raw[18:20], byteorder='big', signed=False)
        minor = int.from_bytes(raw[20:22], byteorder='big', signed=False)
        measured_power = int.from_bytes(raw[22:23], byteorder='big', signed=True)
        return IBeaconAdvertisement(
            company_id=int(company_id),
            uuid=beacon_uuid,
            major=major,
            minor=minor,
            measured_power=measured_power,
        )
    return None


def manufacturer_data_hex(manufacturer_data):
    """Return stable diagnostic text without depending on platform internals."""
    return ', '.join(
        f'0x{int(company_id):04X}:{bytes(payload).hex().upper()}'
        for company_id, payload in sorted((manufacturer_data or {}).items())
    ) or 'none'


def service_data_hex(service_data):
    """Return service-data bytes in a readable, cross-platform form."""
    return ', '.join(
        f'{service_uuid}:{bytes(payload).hex().upper()}'
        for service_uuid, payload in sorted((service_data or {}).items())
    ) or 'none'


def identify_advertisement_protocol(ibeacon, service_data):
    """Label known advertisement framing without inventing missing identities."""
    if ibeacon is not None:
        return 'ibeacon'

    for service_uuid, payload in (service_data or {}).items():
        if str(service_uuid).lower() != '0000feaa-0000-1000-8000-00805f9b34fb':
            continue
        raw = bytes(payload)
        if not raw:
            return 'eddystone'
        return {
            0x00: 'eddystone_uid',
            0x10: 'eddystone_url',
            0x20: 'eddystone_tlm',
            0x30: 'eddystone_eid',
        }.get(raw[0], 'eddystone')
    return 'ble'
