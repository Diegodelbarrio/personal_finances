from django import forms

from .models import UserSettings


COMMON_TIMEZONES = [
    ("Europe/Brussels", "Europe/Brussels"),
    ("Europe/Madrid", "Europe/Madrid"),
    ("Europe/London", "Europe/London"),
    ("Europe/Paris", "Europe/Paris"),
    ("UTC", "UTC"),
    ("America/New_York", "America/New_York"),
    ("America/Chicago", "America/Chicago"),
    ("America/Los_Angeles", "America/Los_Angeles"),
]


class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            'annual_savings_target', 
            'monthly_budget',
            'net_worth_target', 
            'savings_rate_target',
            'target_date', 
            'retirement_age',
            'main_currency', 
            'financial_profile',
            'emergency_fund_months',
            'language_code',
            'timezone',
        ]

        error_messages = {
            'emergency_fund_months': {
                'required': "Please specify the number of months for your emergency fund.",
                'invalid': "Enter a valid number of months.",
            },
            'net_worth_target': {
                'required': "You must set a net worth objective.",
            },
            'target_date': {
                'required': "A deadline date is required to track your progress.",
            }
        }

        widgets = {
            'annual_savings_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00',
                'step': '100',
                'min': '0',
                'inputmode': 'decimal',
            }),
            'monthly_budget': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00',
                'step': '50',
                'min': '0',
                'inputmode': 'decimal',
            }),
            'net_worth_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00',
                'step': '1000',
                'min': '0',
                'inputmode': 'decimal',
            }),
            'savings_rate_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '20',
                'min': '0',
                'max': '100',
                'step': '0.1',
                'inputmode': 'decimal',
            }),
            'target_date': forms.DateInput(attrs={
                'type': 'date',  
                'class': 'form-control'
            }),
            'main_currency': forms.Select(attrs={
                'class': 'form-select' 
            }),
            'financial_profile': forms.RadioSelect(attrs={
                'class': 'settings-profile-input'
            }),
            'emergency_fund_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '24',
                'step': '1',
                'inputmode': 'numeric',
            }),
            'retirement_age': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '18',
                'max': '100',
                'step': '1',
                'inputmode': 'numeric',
            }),
            'language_code': forms.Select(attrs={
                'class': 'form-select',
            }),
            'timezone': forms.Select(attrs={
                'class': 'form-select',
            }),
        }

        labels = {
            'annual_savings_target': 'Annual Savings Target',
            'monthly_budget': 'Monthly Budget Limit',
            'net_worth_target': 'Net Worth Target',
            'savings_rate_target': 'Target Savings Rate (%)',
            'emergency_fund_months': 'Emergency Fund Months',
            'financial_profile': 'Financial Profile',
            'language_code': 'Language',
            'timezone': 'Time Zone',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_timezone = self.initial.get("timezone") or getattr(self.instance, "timezone", "")
        choices = list(COMMON_TIMEZONES)
        if current_timezone and current_timezone not in dict(choices):
            choices.insert(0, (current_timezone, current_timezone))
        self.fields["timezone"].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        decimal_fields = (
            "annual_savings_target",
            "monthly_budget",
            "net_worth_target",
            "savings_rate_target",
        )

        for field_name in decimal_fields:
            value = cleaned_data.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, "Enter a positive value.")

        savings_rate = cleaned_data.get("savings_rate_target")
        if savings_rate is not None and savings_rate > 100:
            self.add_error("savings_rate_target", "Savings rate cannot exceed 100%.")

        emergency_months = cleaned_data.get("emergency_fund_months")
        if emergency_months is not None and not 1 <= emergency_months <= 24:
            self.add_error("emergency_fund_months", "Choose between 1 and 24 months.")

        retirement_age = cleaned_data.get("retirement_age")
        if retirement_age is not None and not 18 <= retirement_age <= 100:
            self.add_error("retirement_age", "Choose an age between 18 and 100.")

        return cleaned_data
