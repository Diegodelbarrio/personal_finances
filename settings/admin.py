from django.contrib import admin
from .models import UserSettings

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    # Columnas que se verán en el listado principal
    list_display = ('user', 'annual_savings_target', 'net_worth_target', 'target_date', 'main_currency', 'updated_at')
    
    # Filtros laterales
    list_filter = ('main_currency', 'updated_at')
    
    # Buscador por nombre de usuario
    search_fields = ('user__username', 'user__email')
    
    # Organización del formulario de edición
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Financial Objectives', {
            'fields': ('annual_savings_target', 'net_worth_target', 'target_date'),
            'description': "Define the user's long-term goals."
        }),
        ('System Preferences', {
            'fields': ('main_currency', 'emergency_fund_months'),
            'classes': ('collapse',), 
        }),
    )

    # Evita que se pueda cambiar el usuario una vez creado para mantener la integridad
    def get_readonly_fields(self, request, obj=None):
        if obj: # Si el objeto ya existe
            return ('user',)
        return ()