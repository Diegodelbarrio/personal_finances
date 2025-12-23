from django.db import models
from django.utils import timezone
from django.conf import settings  # Importante para referenciar al modelo de usuario

class Asset(models.Model):
    # CUALQUIER activo debe pertenecer a alguien
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='assets'
    )
    
    CATEGORY_CHOICES = [
        ('CRYPTO', 'Cryptocurrencies'),
        ('INDEX_FUND', 'Index Funds'),
        ('COMMODITY', 'Commodities'),
        ('STOCK', 'Individual Stocks'),
    ]

    name = models.CharField(max_length=100, verbose_name="Name of Asset")
    isin = models.CharField(max_length=20, blank=True, null=True, verbose_name="ISIN")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="Category")
    platform = models.CharField(max_length=50, verbose_name="Entity/Platform")

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    class Meta:
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        # CLAVE: Evita que el MISMO usuario duplique el activo, 
        # pero permite que otros usuarios tengan uno igual.
        unique_together = ('user', 'name')


class Transaction(models.Model):
    # Cada transacción de compra/venta pertenece a un usuario
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='investment_transactions'
    )
    # Si borras el activo, se borran sus transacciones (CASCADE)
    asset = models.ForeignKey(
        Asset, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    
    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    date = models.DateField(default=timezone.now, verbose_name="Date")
    action = models.CharField(max_length=4, choices=ACTION_CHOICES, default='BUY')
    shares = models.DecimalField(max_digits=20, decimal_places=8, verbose_name="Shares")
    price_per_share = models.DecimalField(max_digits=20, decimal_places=6, verbose_name="Price per Share")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Total (€) Invested")
    notes = models.TextField(blank=True, null=True, verbose_name="Comments")

    def __str__(self):
        return f"{self.user.username} | {self.get_action_display()} {self.asset.name} ({self.date})"

    class Meta:
        ordering = ['-date']
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"


class AssetHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='asset_histories',
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='history')
    date = models.DateField(verbose_name="Date of Record")
    total_value = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Total Market Value (€)")

    def __str__(self):
        return f"{self.asset.name} - {self.date} - {self.total_value}€"

    class Meta:
        ordering = ['-date']
        verbose_name = "Asset History"
        verbose_name_plural = "Asset Histories"