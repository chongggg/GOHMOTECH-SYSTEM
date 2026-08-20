from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.utils import timezone

from iot.models import Goat

from .models import MarketplaceListing, Message, Reservation
from .auth import BUYER_GROUP_NAME


class BuyerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            buyer_group, _ = Group.objects.get_or_create(name=BUYER_GROUP_NAME)
            user.groups.add(buyer_group)
        return user


class ListingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceListing
        fields = ("goat", "price", "sales_description")
        widgets = {
            "price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "sales_description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        eligible = Goat.objects.filter(status="active", is_active=True)
        if self.instance.pk:
            eligible = eligible.filter(
                Q(marketplace_listing__isnull=True) | Q(pk=self.instance.goat_id)
            )
        else:
            eligible = eligible.filter(marketplace_listing__isnull=True)
        self.fields["goat"].queryset = eligible.order_by("goat_id")
        for name, field in self.fields.items():
            field.widget.attrs.setdefault(
                "class", "form-select" if name == "goat" else "form-control"
            )


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message...", "class": "form-control"})}


class PickupRequestForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ("pickup_datetime", "pickup_notes")
        widgets = {
            "pickup_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "pickup_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pickup_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["pickup_datetime"].required = True
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_pickup_datetime(self):
        pickup_datetime = self.cleaned_data["pickup_datetime"]
        if pickup_datetime <= timezone.now():
            raise forms.ValidationError("Pickup must be scheduled for a future date and time.")
        return pickup_datetime
