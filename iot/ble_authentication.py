"""Authentication dedicated to independent BLE receiver processes."""

from dataclasses import dataclass

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import BLEReceiver


@dataclass(frozen=True)
class BLEReceiverPrincipal:
    """Small authenticated principal exposed as request.user."""

    receiver: BLEReceiver

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.receiver.device.is_active

    @property
    def username(self):
        return self.receiver.device.device_id


class BLEReceiverAuthentication(BaseAuthentication):
    """Authenticate one pre-provisioned scanner using a bearer credential."""

    keyword = b'bearer'

    def authenticate(self, request):
        receiver_id = request.headers.get('X-Receiver-ID', '').strip()
        authorization = get_authorization_header(request).split()

        if not receiver_id or not authorization:
            raise AuthenticationFailed('Receiver credentials are required.')
        if len(authorization) != 2 or authorization[0].lower() != self.keyword:
            raise AuthenticationFailed('Use Authorization: Bearer <receiver-key>.')

        try:
            raw_api_key = authorization[1].decode('utf-8')
        except UnicodeError as exc:
            raise AuthenticationFailed('Invalid receiver credentials.') from exc

        try:
            receiver = BLEReceiver.objects.select_related('device').get(
                device__device_id=receiver_id
            )
        except BLEReceiver.DoesNotExist as exc:
            raise AuthenticationFailed('Invalid receiver credentials.') from exc

        if not receiver.device.is_active or not receiver.check_api_key(raw_api_key):
            raise AuthenticationFailed('Invalid receiver credentials.')

        return BLEReceiverPrincipal(receiver), raw_api_key

    def authenticate_header(self, request):
        return 'Bearer realm="ble-receiver"'
