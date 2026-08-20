"""Small bounded RSSI smoothing window for fluctuating BLE signals."""

from collections import deque
from statistics import fmean, median


class RSSISmoother:
    def __init__(self, window_size=5, method='median'):
        if not 3 <= int(window_size) <= 50:
            raise ValueError('window_size must be between 3 and 50.')
        if method not in {'median', 'moving_average'}:
            raise ValueError('method must be median or moving_average.')
        self.method = method
        self.samples = deque(maxlen=int(window_size))

    def add(self, rssi):
        value = int(rssi)
        if not -127 <= value <= 20:
            raise ValueError('RSSI must be between -127 and 20 dBm.')
        self.samples.append(value)
        return self.value

    @property
    def value(self):
        if not self.samples:
            return None
        if self.method == 'moving_average':
            return float(fmean(self.samples))
        return float(median(self.samples))

    @property
    def count(self):
        return len(self.samples)
