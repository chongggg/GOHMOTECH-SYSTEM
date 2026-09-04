"""Forms for user-managed SMS registration."""

from django import forms

from .models import SmsRegistration
from .providers import normalize_ph_number


class SmsRegistrationForm(forms.ModelForm):
    class Meta:
        model = SmsRegistration
        fields = ('phone_number', 'is_active')
        labels = {
            'phone_number': 'Mobile number',
            'is_active': 'Enable this SMS registration',
        }
        help_texts = {
            'phone_number': (
                'Use a Philippine mobile number such as 09171234567. '
                'Spaces, hyphens, and +63 format are accepted.'
            ),
            'is_active': (
                'Turn this off to pause account-related SMS without deleting '
                'your registered number.'
            ),
        }
        widgets = {
            'phone_number': forms.TextInput(
                attrs={
                    'autocomplete': 'tel',
                    'inputmode': 'tel',
                    'placeholder': '0917 123 4567',
                }
            ),
        }

    def clean_phone_number(self):
        number = self.cleaned_data['phone_number']
        try:
            return normalize_ph_number(number)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
