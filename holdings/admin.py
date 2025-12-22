from django.contrib import admin
from .models import BankAccount, AccountBalanceSnapshot

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution', 'account_type', 'currency', 'is_active')
    list_filter = ('account_type', 'institution', 'is_active', 'currency')
    search_fields = ('name', 'institution')
    list_editable = ('is_active',)

@admin.register(AccountBalanceSnapshot)
class AccountBalanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ('account', 'date', 'balance_display')
    list_filter = ('account__institution', 'date', 'account__account_type')
    date_hierarchy = 'date'
    
    def balance_display(self, obj):
        return f"{obj.balance} {obj.account.currency}"
    balance_display.short_description = "Balance"