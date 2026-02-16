from django import forms
from .models import UserSettings

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
            'emergency_fund_months'
        ]
        
        # Aquí defines los mensajes exactos para cada campo y tipo de error
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
        
        # Widgets para estilizar con Bootstrap 5
        widgets = {
            'annual_savings_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00',
                'step': '100'
            }),
            'monthly_budget': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00',
                'step': '50'
            }),
            'net_worth_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00',
                'step': '1000'
            }),
            'savings_rate_target': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '20',
                'min': '0',
                'max': '100'
            }),
            'target_date': forms.DateInput(attrs={
                'type': 'date',  
                'class': 'form-control'
            }),
            'main_currency': forms.Select(attrs={
                'class': 'form-select' 
            }),
            'financial_profile': forms.Select(attrs={
                'class': 'form-select'
            }),
            'emergency_fund_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '24'
            }),
            'retirement_age': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '18',
                'max': '100'
            }),
        }
        
        # Etiquetas personalizadas (opcional, si no usas verbose_name en models)
        labels = {
            'annual_savings_target': 'Annual Savings Target',
            'monthly_budget': 'Monthly Budget Limit',
            'net_worth_target': 'Net Worth Target',
            'savings_rate_target': 'Target Savings Rate (%)',
            'emergency_fund_months': 'Emergency Fund Months',
            'financial_profile': 'Financial Profile',
        }
