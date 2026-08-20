from django import forms
from .goat_models import BLEBeacon, Goat


class GoatForm(forms.ModelForm):
    """Form for adding/editing goats with custom styling"""

    # Hidden field for webcam-captured photo (base64)
    captured_photo = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Goat
        fields = [
            'goat_id', 'name', 'tag_number', 'breed', 'gender',
            'date_of_birth', 'weight_kg', 'color_markings',
            'health_status', 'health_notes',
            'vaccination_status', 'vaccine_name', 'vaccination_date', 'next_due_date',
            'notes'
        ]
        widgets = {
            'goat_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., G001, RFID',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional name for the goat'
            }),
            'tag_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Physical tag/ear tag number'
            }),
            'breed': forms.Select(attrs={
                'class': 'form-select'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'weight_kg': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Weight in kilograms',
                'step': '0.1',
                'min': '0'
            }),
            'color_markings': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Brown with white patches, black legs'
            }),
            'health_status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'health_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any health observations or medical notes'
            }),
            'vaccination_status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'vaccine_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., CDT, Rabies'
            }),
            'vaccination_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'next_due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'General notes about this goat'
            }),
        }
        labels = {
            'goat_id': 'Goat ID',
            'name': 'Name',
            'tag_number': 'Tag Number',
            'breed': 'Breed',
            'gender': 'Sex',
            'date_of_birth': 'Date of Birth',
            'weight_kg': 'Weight (kg)',
            'color_markings': 'Color / Markings',
            'health_status': 'Health Status',
            'health_notes': 'Health Notes',
            'vaccination_status': 'Vaccination Status',
            'vaccine_name': 'Vaccine Name',
            'vaccination_date': 'Vaccination Date',
            'next_due_date': 'Next Due Date',
            'notes': 'Notes',
        }


class BLEBeaconForm(forms.ModelForm):
    """Optional BLE tracker assignment used by Add and Manage Goat pages."""

    class Meta:
        model = BLEBeacon
        fields = [
            'enabled', 'device_name', 'mac_address', 'uuid', 'major', 'minor',
            'calibrated_rssi', 'advertising_interval_ms', 'tx_power_dbm',
            'battery_level',
        ]
        widgets = {
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'device_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., CP101-3E95',
            }),
            'mac_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '48:87:2D:9E:3E:95',
            }),
            'uuid': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E2C56DB5-DFFB-48D2-B060-D0F5A71096E0',
            }),
            'major': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 65535,
            }),
            'minor': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 65535,
            }),
            'calibrated_rssi': forms.NumberInput(attrs={
                'class': 'form-control', 'min': -127, 'max': 20,
            }),
            'advertising_interval_ms': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 20, 'max': 10240,
            }),
            'tx_power_dbm': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01',
            }),
            'battery_level': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100,
            }),
        }
        labels = {
            'enabled': 'Tracking Enabled',
            'device_name': 'Beacon Device Name',
            'mac_address': 'Beacon MAC Address',
            'uuid': 'iBeacon UUID',
            'major': 'Major (Farm/Herd ID)',
            'minor': 'Minor (Individual Goat ID)',
            'calibrated_rssi': 'RSSI @ 1 Meter (dBm)',
            'advertising_interval_ms': 'Advertising Interval (ms)',
            'tx_power_dbm': 'TX Power (dBm)',
            'battery_level': 'Battery Level (%)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.Meta.fields:
            self.fields[field_name].required = False
        if not self.is_bound and not self.instance.pk:
            self.initial['enabled'] = False

    def clean(self):
        cleaned_data = super().clean()
        identity_fields = ('uuid', 'major', 'minor')
        meaningful_fields = (
            'device_name', 'mac_address', 'uuid', 'major', 'minor',
            'advertising_interval_ms', 'tx_power_dbm', 'battery_level',
        )
        has_values = any(
            cleaned_data.get(field_name) not in (None, '')
            for field_name in meaningful_fields
        )
        self._should_save_beacon = bool(
            self.instance.pk or cleaned_data.get('enabled') or has_values
        )

        if self._should_save_beacon:
            for field_name in identity_fields:
                if cleaned_data.get(field_name) in (None, ''):
                    self.add_error(
                        field_name,
                        'This field is required when a BLE tracker is configured.'
                    )

        return cleaned_data

    def should_save_beacon(self):
        return getattr(self, '_should_save_beacon', False)

    def save_for_goat(self, goat):
        """Save the configured tracker for ``goat`` or do nothing if omitted."""
        if not self.should_save_beacon():
            return None

        beacon = self.save(commit=False)
        beacon.goat = goat
        beacon.save()
        return beacon
