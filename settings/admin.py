from django.contrib import admin
from .models import UserSettings

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    # Columns to be displayed in the main list
    list_display = ('user', 'annual_savings_target', 'net_worth_target', 'target_date', 'main_currency', 'updated_at')
    
    # Sidebar filters
    list_filter = ('main_currency', 'updated_at')
    
    # Search by username
    search_fields = ('user__username', 'user__email')
    
    # Edit form organization
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Financial Objectives', {
            'fields': ('net_worth_target', 'target_date', 'annual_savings_target', 'monthly_budget', 'savings_rate_target', 'retirement_age'),
            'description': "Define the user's long-term goals."
        }),
        ('System Preferences', {
            'fields': ('main_currency', 'emergency_fund_months'),
            'classes': ('collapse',), 
        }),
    )

    # Prevents changing the user once created to maintain integrity
    def get_readonly_fields(self, request, obj=None):
        if obj: # If the object already exists
            return ('user',)
        return ()