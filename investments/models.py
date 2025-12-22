from django.db import models
from django.utils import timezone

class Asset(models.Model):
    CATEGORY_CHOICES = [
        ('CRYPTO', 'Cryptocurrencies'),
        ('INDEX_FUND', 'Index Funds'),
        ('COMMODITY', 'Commodities'),
        ('STOCK', 'Individual Stocks'),
    ]

    name = models.CharField(max_length=100, verbose_name="Name of Asset") # Ej: MSCI World
    isin = models.CharField(max_length=20, blank=True, null=True, verbose_name="ISIN")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="Category")
    platform = models.CharField(max_length=50, verbose_name="Entity/Platform") # Ej: MyInvestor, Binance

    # Optional: Color for charts
    # color = models.CharField(max_length=7, default="#3366cc", help_text="Hex Code for charts (e.g., #FF5733)")

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Asset"
        verbose_name_plural = "Assets"


class Transaction(models.Model):
    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField(default=timezone.now, verbose_name="Date")
    action = models.CharField(max_length=4, choices=ACTION_CHOICES, default='BUY')

    shares = models.DecimalField(max_digits=20, decimal_places=8, verbose_name="Shares")
    price_per_share = models.DecimalField(max_digits=20, decimal_places=6, verbose_name="Price per Share")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Total (€) Invested")

    notes = models.TextField(blank=True, null=True, verbose_name="Comments")

    def __str__(self):
        return f"{self.get_action_display()} {self.asset.name} ({self.date})"

    class Meta:
        ordering = ['-date'] # Latest first
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"


class AssetHistory(models.Model):
    """
    Manual register of the total asset value at the end of the month.
    Ex: On January 31st, my Bitcoin is worth €2,500 (even though I only put in €1,000).
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='history')
    date = models.DateField(verbose_name="Date of Record")
    total_value = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Total Market Value (€)")

    def __str__(self):
        return f"{self.asset.name} - {self.date} - {self.total_value}€"

    class Meta:
        ordering = ['-date']
        verbose_name = "Asset History"
        verbose_name_plural = "Asset Histories"