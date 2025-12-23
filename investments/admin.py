from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from .models import Asset, Transaction, AssetHistory

# 1. CLASE BASE PARA REUTILIZAR LÓGICA
class InvestmentUserOwnedAdmin(admin.ModelAdmin):
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
            # Filtrar el selector de usuario
            if db_field.name == "user":
                kwargs["queryset"] = db_field.related_model.objects.filter(id=request.user.id)
            
            # Filtrar para que solo vea SUS activos en los desplegables de Transacciones e Historial
            if db_field.name == "asset":
                kwargs["queryset"] = Asset.objects.filter(user=request.user)
                
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# 2. FILTRO PERSONALIZADO PARA QUE EL STAFF SOLO VEA SUS ACTIVOS EN EL LATERAL
class AssetUserFilter(SimpleListFilter):
    title = 'Asset'
    parameter_name = 'asset'

    def lookups(self, request, model_admin):
        qs = Asset.objects.all()
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return [(a.id, a.name) for a in qs]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(asset_id=self.value())
        return queryset

# 3. REGISTRO DE ADMINS
@admin.register(Asset)
class AssetAdmin(InvestmentUserOwnedAdmin):
    list_display = ('name', 'category', 'platform', 'isin', 'user')
    list_filter = ('category', 'platform')
    search_fields = ('name', 'isin')

@admin.register(Transaction)
class TransactionAdmin(InvestmentUserOwnedAdmin):
    list_display = ('date', 'asset', 'action', 'shares', 'amount', 'user')
    # Usamos el filtro personalizado en lugar de 'asset' plano
    list_filter = ('action', AssetUserFilter, 'date')
    search_fields = ('asset__name', 'notes')
    date_hierarchy = 'date'

@admin.register(AssetHistory)
class AssetHistoryAdmin(InvestmentUserOwnedAdmin):
    list_display = ('date', 'asset', 'total_value', 'user')
    list_filter = (AssetUserFilter, 'date')
    date_hierarchy = 'date'