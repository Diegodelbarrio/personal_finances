from django.db import models
from django.conf import settings  # Importa settings en lugar de User
from django.utils.translation import gettext_lazy as _


class UserSettings(models.Model):
    LANGUAGE_CHOICES = [
        ("en-us", "English"),
        ("es", "Spanish"),
    ]
    FINANCIAL_PROFILE_CHOICES = [
        ("BALANCED", "Balanced"),
        ("SECURITY", "Security First"),
        ("GROWTH", "Growth Focus"),
    ]

    user = models.OneToOneField(
            settings.AUTH_USER_MODEL, 
            on_delete=models.CASCADE, 
            related_name='settings'
        )    
    # Objetivos Financieros
    annual_savings_target = models.DecimalField(_("Annual Savings Target"), max_digits=12, decimal_places=2, default=0.00)
    monthly_budget = models.DecimalField(_("Monthly Budget"), max_digits=10, decimal_places=2, default=0.00)
    net_worth_target = models.DecimalField(_("Net Worth Target"), max_digits=15, decimal_places=2, default=0.00)
    savings_rate_target = models.DecimalField(_("Savings Rate Target (%)"), max_digits=5, decimal_places=2, default=20.00)
    target_date = models.DateField(_("Target date"), null=True, blank=True)
    retirement_age = models.PositiveIntegerField(_("Retirement Age"), default=65)
    
    # Preferencias
    main_currency = models.CharField(max_length=3, default='EUR', choices=[('EUR', 'EUR'), ('USD', 'USD')])
    financial_profile = models.CharField(
        _("Financial Profile"),
        max_length=12,
        choices=FINANCIAL_PROFILE_CHOICES,
        default="BALANCED",
    )
    emergency_fund_months = models.IntegerField(_("Emergency Fund Months"), default=6)
    language_code = models.CharField(
        _("Language"),
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="en-us",
    )
    timezone = models.CharField(
        _("Time Zone"),
        max_length=64,
        default="Europe/Madrid",
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings of: {self.user.username}"


class SavingsPotentialModel(models.Model):
    user_settings = models.OneToOneField(
        UserSettings,
        on_delete=models.CASCADE,
        related_name="savings_potential_model",
    )
    conservative_factor = models.DecimalField(
        _("Conservative Factor"),
        max_digits=4,
        decimal_places=2,
        default=0.80,
    )
    baseline_factor = models.DecimalField(
        _("Baseline Factor"),
        max_digits=4,
        decimal_places=2,
        default=1.00,
    )
    optimistic_factor = models.DecimalField(
        _("Optimistic Factor"),
        max_digits=4,
        decimal_places=2,
        default=1.20,
    )
    volatility_impact = models.DecimalField(
        _("Volatility Impact"),
        max_digits=4,
        decimal_places=2,
        default=0.35,
    )
    emergency_buffer_impact = models.DecimalField(
        _("Emergency Buffer Impact"),
        max_digits=4,
        decimal_places=2,
        default=0.30,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Savings Potential Model")
        verbose_name_plural = _("Savings Potential Models")

    def __str__(self):
        return f"Savings potential model for {self.user_settings.user.username}"
