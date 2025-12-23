from django.db import models
from django.conf import settings # Importante para referenciar al usuario

class BankAccount(models.Model):
    # Relación con el usuario: Cada cuenta tiene un dueño
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='accounts',
    )

    ACCOUNT_TYPES = [
        ('CHECKING', 'Checking Account'),
        ('SAVINGS', 'Savings / Emergency Fund'), 
        ('CASH', 'Cash (Wallet)'),
        ('DEBT', 'Debt / Loan (Liability)'),
    ]

    name = models.CharField(max_length=100, verbose_name="Account Name")
    institution = models.CharField(max_length=100, help_text="e.g., ING, Revolut, Binance...")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    currency = models.CharField(max_length=3, default='EUR', help_text="ISO Code (EUR, USD, etc.)")
    
    iban = models.CharField(max_length=34, blank=True, null=True, verbose_name="IBAN / Account Number")
    notes = models.TextField(blank=True, null=True, verbose_name="Additional Notes")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        # Añadimos el dueño al string para identificarlo en el Admin
        return f"{self.name} ({self.institution}) - {self.user.username}"

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        # Un usuario no puede repetir el nombre de cuenta en la misma institución
        unique_together = ('user', 'name', 'institution')

class AccountBalanceSnapshot(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='account_snapshots',
    )
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='balances')
    date = models.DateField(verbose_name="Snapshot Date")
    balance = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Balance")
    interest_earned = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Interest Earned (Month)"
    )

    class Meta:
        unique_together = ('account', 'date')
        ordering = ['-date']
        verbose_name = "Balance Snapshot"
        verbose_name_plural = "Balance Snapshots"

    def __str__(self):
        return f"{self.account.name} - {self.date} - {self.balance} {self.account.currency}"