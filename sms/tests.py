from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from marketplace.auth import FARM_OWNER_GROUP_NAME
from marketplace.forms import MarketplaceSignupForm

from .forms import SmsRegistrationForm
from .models import SmsRegistration


class SmsRegistrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('owner', password='test-password')
        owner_group, _ = Group.objects.get_or_create(name=FARM_OWNER_GROUP_NAME)
        self.owner.groups.add(owner_group)
        self.client_user = User.objects.create_user(
            'buyer', email='buyer@example.com', password='test-password'
        )

    def test_login_is_required(self):
        response = self.client.get(reverse('sms:registration'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_owner_can_register_and_normalize_number(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('sms:registration'),
            {'phone_number': '+63 917-123-4567', 'is_active': 'on'},
        )

        self.assertRedirects(response, reverse('sms:registration'))
        registration = SmsRegistration.objects.get(user=self.owner)
        self.assertEqual(registration.phone_number, '09171234567')
        self.assertTrue(registration.is_active)

    def test_marketplace_client_can_open_and_pause_registration(self):
        registration = SmsRegistration.objects.create(
            user=self.client_user,
            phone_number='09171234567',
            is_active=True,
        )
        self.client.force_login(self.client_user)

        self.assertEqual(self.client.get(reverse('sms:registration')).status_code, 200)
        response = self.client.post(
            reverse('sms:registration'),
            {'phone_number': '09171234567'},
        )

        self.assertRedirects(response, reverse('sms:registration'))
        registration.refresh_from_db()
        self.assertFalse(registration.is_active)

    def test_client_slashless_registration_url_redirects_normally(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('sms:registration').rstrip('/'))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse('sms:registration'))

    def test_invalid_mobile_number_is_rejected(self):
        form = SmsRegistrationForm(
            data={'phone_number': '12345', 'is_active': True}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_marketplace_signup_can_create_sms_registration(self):
        User = get_user_model()
        user = User.objects.create_user('new-buyer', email='new@example.com')
        form = MarketplaceSignupForm(
            data={
                'first_name': 'New',
                'last_name': 'Buyer',
                'sms_phone_number': '917 555 1234',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

        form.signup(None, user)

        registration = SmsRegistration.objects.get(user=user)
        self.assertEqual(registration.phone_number, '09175551234')
        self.assertTrue(registration.is_active)
