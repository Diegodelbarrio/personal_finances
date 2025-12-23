from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from .models import BankAccount, AccountBalanceSnapshot

# 1. CLASE BASE PARA HOLDINGS
class HoldingsUserOwnedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def get_changeform_initial_data(self, request):
        return {'user': request.user.id}

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ('user',)
        return ()

    def save_model(self, request, obj, form, change):
        if not change and not request.user.is_superuser:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            if db_field.name == "user":
                kwargs["queryset"] = db_field.related_model.objects.filter(id=request.user.id)
            
            # FILTRADO CLAVE: Al registrar un saldo, solo ver SUS cuentas bancarias
            if db_field.name == "account":
                kwargs["queryset"] = BankAccount.objects.filter(user=request.user)
                
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# 2. FILTRO PARA LA BARRA LATERAL
class BankAccountUserFilter(SimpleListFilter):
    title = 'Cuenta'
    parameter_name = 'account'

    def lookups(self, request, model_admin):
        qs = BankAccount.objects.all()
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return [(a.id, a.name) for a in qs]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(account_id=self.value())
        return queryset

# 3. REGISTRO DE ADMINS
@admin.register(BankAccount)
class BankAccountAdmin(HoldingsUserOwnedAdmin):
    list_display = ('name', 'institution', 'account_type', 'currency', 'is_active', 'user')
    list_filter = ('account_type', 'institution', 'is_active', 'currency')
    search_fields = ('name', 'institution')
    list_editable = ('is_active',) # Nota: Solo funcionará para el superuser si no filtramos los permisos de edición

@admin.register(AccountBalanceSnapshot)
class AccountBalanceSnapshotAdmin(HoldingsUserOwnedAdmin):
    list_display = ('account', 'date', 'balance_display', 'user')
    # Usamos el filtro dinámico para que Natalia no vea tus bancos
    list_filter = (BankAccountUserFilter, 'date')
    date_hierarchy = 'date'
    
    def balance_display(self, obj):
        return f"{obj.balance} {obj.account.currency}"
    balance_display.short_description = "Balance"