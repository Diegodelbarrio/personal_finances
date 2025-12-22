from django.contrib import admin
from .models import Asset, Transaction, AssetHistory

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'platform', 'isin')
    list_filter = ('category', 'platform')
    search_fields = ('name', 'isin')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'asset', 'action', 'shares', 'amount', 'price_per_share')
    list_filter = ('action', 'asset', 'date')
    search_fields = ('asset__name', 'notes')
    date_hierarchy = 'date' # Quick navigation by year/month

    # This helps auto-calculate the total if you enter quantity and price (optional, visual)
    # but Django Admin is basic. Ideally, you should enter all 3 data points from Excel.

@admin.register(AssetHistory)
class AssetHistoryAdmin(admin.ModelAdmin):
    list_display = ('date', 'asset', 'total_value')
    list_filter = ('asset',)
    date_hierarchy = 'date'