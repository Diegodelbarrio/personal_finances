from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import SavingsPotentialModel, UserSettings


User = get_user_model()

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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = User.objects.filter(pk=request.user.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(SavingsPotentialModel)
class SavingsPotentialModelAdmin(admin.ModelAdmin):
    list_display = (
        "user_settings",
        "conservative_factor",
        "baseline_factor",
        "optimistic_factor",
        "updated_at",
    )
    search_fields = ("user_settings__user__username", "user_settings__user__email")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user_settings__user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user_settings" and not request.user.is_superuser:
            kwargs["queryset"] = UserSettings.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
