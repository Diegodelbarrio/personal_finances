from django.db import models
from django.conf import settings  # Importa settings en lugar de User
from django.utils.translation import gettext_lazy as _

class UserSettings(models.Model):
    user = models.OneToOneField(
            settings.AUTH_USER_MODEL, 
            on_delete=models.CASCADE, 
            related_name='settings'
        )    
    # Objetivos Financieros
    annual_savings_target = models.DecimalField(_("Annual Savings Target"), max_digits=12, decimal_places=2, default=0.00)
    net_worth_target = models.DecimalField(_("Net Worth Target"), max_digits=15, decimal_places=2, default=0.00)
    target_date = models.DateField(_("Target date"), null=True, blank=True)
    
    # Preferencias
    main_currency = models.CharField(max_length=3, default='EUR', choices=[('EUR', 'EUR'), ('USD', 'USD')])
    emergency_fund_months = models.IntegerField(_("Emergency Fund Months"), default=6)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings of: {self.user.username}"