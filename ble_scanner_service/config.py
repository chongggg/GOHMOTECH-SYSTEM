"""Configuration primitives shared by Windows and future Linux scanners."""

from dataclasses import dataclass
import re
import uuid as uuid_lib


GOHMOTECH_IBEACON_UUID = 'E2C56DB5-DFFB-48D2-B060-D0F5A71096E0'


def normalize_uuid(value):
    return str(uuid_lib.UUID(str(value))).upper()


def normalize_mac(value):
    if not value:
        return None
    compact = re.sub(r'[^0-9A-Fa-f]', '', str(value))
    if len(compact) != 12:
        raise ValueError('BLE MAC address must contain exactly 12 hexadecimal digits.')
    return ':'.join(compact[index:index + 2] for index in range(0, 12, 2)).upper()


@dataclass(frozen=True)
class ScannerConfig:
    """Runtime scanner settings with no Django dependency."""

    target_uuid: str = GOHMOTECH_IBEACON_UUID
    target_mac: str | None = None
    target_name: str | None = None
    # Bleak's passive watcher mode is currently a BlueZ/Linux-only option.
    # Active discovery is still connectionless and never pairs with a beacon.
    scan_mode: str = 'active'
    smoothing_method: str = 'median'
    smoothing_window: int = 5
    report_interval_seconds: float = 1.0
    restart_interval_seconds: float = 300.0
    duration_seconds: float | None = None
    raw_output: bool = False
    show_all_devices: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'target_uuid', normalize_uuid(self.target_uuid))
        object.__setattr__(self, 'target_mac', normalize_mac(self.target_mac))
        if self.scan_mode not in {'passive', 'active'}:
            raise ValueError('scan_mode must be passive or active.')
        if self.smoothing_method not in {'median', 'moving_average'}:
            raise ValueError('smoothing_method must be median or moving_average.')
        if not 3 <= self.smoothing_window <= 50:
            raise ValueError('smoothing_window must be between 3 and 50.')
        if self.report_interval_seconds <= 0:
            raise ValueError('report_interval_seconds must be greater than zero.')
        if self.restart_interval_seconds <= 0:
            raise ValueError('restart_interval_seconds must be greater than zero.')
        if self.duration_seconds is not None and self.duration_seconds <= 0:
            raise ValueError('duration_seconds must be greater than zero when provided.')
