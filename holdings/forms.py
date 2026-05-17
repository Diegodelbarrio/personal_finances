from django import forms
from django.conf import settings

from holdings.models import BankConnection


class BankConnectionStartForm(forms.Form):
    provider = forms.ChoiceField(
        choices=BankConnection.PROVIDER_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    country_code = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ES"}),
    )
    institution_id = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "modelo-sandbox"}
        ),
    )
    institution_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Sandbox Finance"}),
    )

    def __init__(self, *args, **kwargs):
        institution_choices = kwargs.pop("institution_choices", None)
        super().__init__(*args, **kwargs)
        configured_provider = (
            self.initial.get("provider")
            or getattr(settings, "BANK_SYNC_PROVIDER", "mock")
        ).upper()
        if configured_provider in dict(BankConnection.PROVIDER_CHOICES):
            self.fields["provider"].initial = configured_provider
        self.fields["country_code"].initial = self.initial.get(
            "country_code",
            getattr(settings, "BANK_SYNC_COUNTRY_CODE", "ES"),
        )
        if institution_choices:
            self.fields["institution_id"] = forms.ChoiceField(
                choices=[("", "Select an institution")] + institution_choices,
                required=False,
                widget=forms.Select(attrs={"class": "form-select"}),
            )

    def clean_provider(self):
        return self.cleaned_data["provider"].upper()

    def clean_country_code(self):
        country_code = self.cleaned_data.get("country_code", "").strip().upper()
        return country_code or getattr(settings, "BANK_SYNC_COUNTRY_CODE", "ES")

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get("provider")
        institution_id = cleaned_data.get("institution_id", "").strip()
        if provider == BankConnection.PROVIDER_GOCARDLESS and not institution_id:
            self.add_error("institution_id", "Institution ID is required for GoCardless.")
        cleaned_data["institution_id"] = institution_id
        cleaned_data["institution_name"] = cleaned_data.get("institution_name", "").strip()
        return cleaned_data
