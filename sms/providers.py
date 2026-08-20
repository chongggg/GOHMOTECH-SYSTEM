"""
SMS provider clients.

Two backends, selected by settings.SMS_BACKEND:
  * 'console'   — development/test mode. Logs the message and returns success
                  WITHOUT calling any external API, so the whole Daily / Alert /
                  Reminder workflow can be exercised end-to-end without spending
                  Semaphore credits (mirrors Django's console email backend).
  * 'semaphore' — live sending through the Semaphore HTTP API.

SECURITY: the Semaphore API key and sender name are read from settings (which
read them from environment variables). They are NEVER stored in the database and
NEVER sent to the browser.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SmsResult:
    """Normalized result of a send attempt, uniform across all backends."""

    def __init__(self, ok, provider, message_id='', status='', raw=None, error=''):
        self.ok = ok
        self.provider = provider
        self.message_id = message_id
        self.status = status
        self.raw = raw            # raw provider response (stored on SmsLog)
        self.error = error


def normalize_ph_number(number):
    """
    Normalize a Philippine mobile number to Semaphore's 11-digit ``09XXXXXXXXX``
    form. Accepts ``09XXXXXXXXX``, ``+639XXXXXXXXX``, ``639XXXXXXXXX`` and
    ``9XXXXXXXXX``.

    Returns the normalized string, or raises ValueError if it is not a plausible
    PH mobile number.
    """
    if not number:
        raise ValueError("No recipient number configured")
    digits = ''.join(ch for ch in str(number) if ch.isdigit())
    if digits.startswith('63') and len(digits) == 12:
        digits = '0' + digits[2:]
    elif len(digits) == 10 and digits.startswith('9'):
        digits = '0' + digits
    if not (len(digits) == 11 and digits.startswith('09')):
        raise ValueError(f"Invalid PH mobile number: {number!r}")
    return digits


class ConsoleSmsClient:
    """Dev backend: pretends to send, spends no credits."""

    name = 'console'

    def send(self, number, message):
        logger.info("[console-sms] To %s: %s", number, message)
        return SmsResult(
            ok=True, provider=self.name, message_id='console', status='sent',
            raw={'backend': 'console', 'number': number, 'message': message},
        )

    def get_balance(self):
        return None  # no credits are consumed in console mode


class SemaphoreSmsClient:
    """
    Live backend using the Semaphore API (https://semaphore.co).

    Endpoint + parameter names follow Semaphore's v4 API: POST
    apikey/number/message/sendername to /api/v4/messages, which returns a JSON
    array of queued message objects. Confirm against the live docs before going
    to production.
    """

    name = 'semaphore'

    def __init__(self):
        self.api_key = getattr(settings, 'SEMAPHORE_API_KEY', '')
        self.sender_name = getattr(settings, 'SEMAPHORE_SENDER_NAME', '')
        self.api_url = getattr(
            settings, 'SEMAPHORE_API_URL',
            'https://api.semaphore.co/api/v4/messages')
        self.account_url = getattr(
            settings, 'SEMAPHORE_ACCOUNT_URL',
            'https://api.semaphore.co/api/v4/account')

    def send(self, number, message):
        if not self.api_key:
            return SmsResult(ok=False, provider=self.name,
                             error="SEMAPHORE_API_KEY is not configured")
        payload = {
            'apikey': self.api_key,
            'number': number,
            'message': message,
        }
        if self.sender_name:
            payload['sendername'] = self.sender_name

        try:
            resp = requests.post(self.api_url, data=payload, timeout=15)
        except requests.RequestException as exc:
            logger.error("Semaphore request failed: %s", exc)
            return SmsResult(ok=False, provider=self.name, error=str(exc))

        try:
            data = resp.json()
        except ValueError:
            data = {'raw_text': resp.text}

        # Success: Semaphore returns a JSON array of queued message objects.
        if resp.status_code in (200, 201) and isinstance(data, list) and data:
            first = data[0] or {}
            return SmsResult(
                ok=True, provider=self.name,
                message_id=str(first.get('message_id', '')),
                status=str(first.get('status', 'queued')),
                raw=data,
            )
        # Failure: surface whatever Semaphore returned for the log.
        return SmsResult(
            ok=False, provider=self.name, raw=data,
            error=f"HTTP {resp.status_code}: {data}",
        )

    def get_balance(self):
        """Return the account credit balance, or None on failure."""
        if not self.api_key:
            return None
        try:
            resp = requests.get(self.account_url,
                                params={'apikey': self.api_key}, timeout=15)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("Semaphore balance check failed: %s", exc)
            return None
        if isinstance(data, dict):
            return data.get('credit_balance', data.get('account_balance'))
        return None


def get_client():
    """Return the SMS client selected by settings.SMS_BACKEND."""
    backend = getattr(settings, 'SMS_BACKEND', 'console').lower()
    if backend == 'semaphore':
        return SemaphoreSmsClient()
    return ConsoleSmsClient()
