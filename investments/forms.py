from django import forms
from django.utils import timezone

from .models import Asset, AssetHistory, Transaction


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["name", "isin", "category", "platform"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Asset name",
                    "maxlength": "100",
                }
            ),
            "isin": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional ISIN",
                    "maxlength": "20",
                }
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "platform": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Entity / Platform",
                    "maxlength": "50",
                }
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["name"].label = "Asset"
        self.fields["isin"].label = "ISIN"
        self.fields["category"].label = "Category"
        self.fields["platform"].label = "Platform"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicated_name = Asset.objects.filter(
            user=self.user,
            name__iexact=name,
        ).exclude(pk=self.instance.pk)
        if duplicated_name.exists():
            raise forms.ValidationError("You already have an asset with this name.")
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class InvestmentTransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["asset", "date", "action", "shares", "price_per_share", "amount", "notes"]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "action": forms.Select(attrs={"class": "form-select"}),
            "shares": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional shares",
                    "step": "0.00000001",
                    "min": "0.00000001",
                }
            ),
            "price_per_share": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional price per share",
                    "step": "0.000001",
                    "min": "0.000001",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0.01",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Optional comments...",
                }
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["asset"].label = "Asset"
        self.fields["date"].label = "Date"
        self.fields["action"].label = "Action"
        self.fields["shares"].label = "Shares"
        self.fields["price_per_share"].label = "Price per Share"
        self.fields["amount"].label = "Total (€) Invested"
        self.fields["notes"].label = "Comments"
        self.fields["asset"].queryset = Asset.objects.filter(user=user).order_by("name")
        self.fields["asset"].label_from_instance = lambda obj: obj.name
        if not self.instance.pk:
            self.initial.setdefault("date", timezone.localdate())

    def clean_asset(self):
        asset = self.cleaned_data["asset"]
        if asset.user_id != self.user.id:
            raise forms.ValidationError("Invalid asset.")
        return asset

    def clean_shares(self):
        shares = self.cleaned_data.get("shares")
        if shares is not None and shares <= 0:
            raise forms.ValidationError("Shares must be greater than zero.")
        return shares

    def clean_price_per_share(self):
        price = self.cleaned_data.get("price_per_share")
        if price is not None and price <= 0:
            raise forms.ValidationError("Price per share must be greater than zero.")
        return price

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        instance.amount = (
            -abs(instance.amount) if instance.action == "SELL" else abs(instance.amount)
        )
        if commit:
            instance.save()
        return instance


class AssetHistoryForm(forms.ModelForm):
    class Meta:
        model = AssetHistory
        fields = ["asset", "date", "total_value"]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "total_value": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0.00",
                }
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["asset"].label = "Asset"
        self.fields["date"].label = "Date of Record"
        self.fields["total_value"].label = "Total Market Value (€)"
        self.fields["asset"].queryset = Asset.objects.filter(user=user).order_by("name")
        self.fields["asset"].label_from_instance = lambda obj: obj.name
        self.initial.setdefault("date", timezone.localdate())

    def clean_asset(self):
        asset = self.cleaned_data["asset"]
        if asset.user_id != self.user.id:
            raise forms.ValidationError("Invalid asset.")
        return asset

    def clean_total_value(self):
        total_value = self.cleaned_data["total_value"]
        if total_value is None or total_value < 0:
            raise forms.ValidationError("Total market value must be zero or greater.")
        return total_value

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance
