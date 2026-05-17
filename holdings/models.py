import uuid

from django.conf import settings  # Importante para referenciar al usuario
from django.db import models


class BankConnection(models.Model):
    PROVIDER_MOCK = "MOCK"
    PROVIDER_GOCARDLESS = "GOCARDLESS"
    PROVIDER_YAPILY = "YAPILY"

    PROVIDER_CHOICES = [
        (PROVIDER_MOCK, "Mock bank data"),
        (PROVIDER_GOCARDLESS, "GoCardless Bank Account Data"),
        (PROVIDER_YAPILY, "Yapily"),
    ]

    STATUS_CREATED = "CREATED"
    STATUS_LINKED = "LINKED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_ERROR = "ERROR"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_LINKED, "Linked"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_ERROR, "Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bank_connections",
    )
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES)
    institution_id = models.CharField(max_length=128, blank=True)
    institution_name = models.CharField(max_length=255, blank=True)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    external_id = models.CharField(max_length=128, blank=True, db_index=True)
    agreement_id = models.CharField(max_length=128, blank=True)
    consent_token = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_CREATED,
        db_index=True,
    )
    redirect_url = models.URLField(blank=True, max_length=2048)
    consent_url = models.URLField(blank=True, max_length=4096)
    accounts = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    consent_expires_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bank connection"
        verbose_name_plural = "Bank connections"

    def __str__(self):
        institution = self.institution_name or self.institution_id or self.provider
        return f"{institution} - {self.user.username}"

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
    sync_connection = models.ForeignKey(
        BankConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_accounts",
    )
    sync_provider = models.CharField(max_length=30, blank=True, db_index=True)
    external_account_id = models.CharField(max_length=128, blank=True, db_index=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

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
