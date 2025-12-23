import calendar
from decimal import Decimal

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from .models import Category, SubCategory, Location, Transaction


# ======================================================
# FILTROS DE FECHA
# ======================================================

class YearFilter(SimpleListFilter):
    title = _('year')
    parameter_name = 'year'

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        years = qs.dates('date', 'year')
        return [(y.year, y.year) for y in years]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(date__year=self.value())
        return queryset


class MonthFilter(SimpleListFilter):
    title = _('month')
    parameter_name = 'month'

    def lookups(self, request, model_admin):
        return [(i, _(calendar.month_name[i])) for i in range(1, 13)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(date__month=self.value())
        return queryset


class TransactionTypeFilter(SimpleListFilter):
    title = _('type')
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('INCOME', _('Income')),
            ('EXPENSE', _('Expense')),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                subcategory__parent_category__transaction_type=self.value()
            )
        return queryset


# ======================================================
# SUBCATEGORY FILTER CON SEARCH (Django < 4.2)
# ======================================================

class SubCategorySearchFilter(SimpleListFilter):
    title = _('Subcategory')
    parameter_name = 'subcategory_search'

    def lookups(self, request, model_admin):
        return ()

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(subcategory__name__icontains=value)
        return queryset

    def choices(self, changelist):
        yield {
            'selected': False,
            'query_string': '',
            'display': '',
        }


# ======================================================
# BASE ADMIN: PRIVACIDAD POR USUARIO
# ======================================================

class UserOwnedAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    # --- ESTA ES LA PARTE QUE DEBES AÑADIR/ASEGURAR ---
    def get_changeform_initial_data(self, request):
        """Define el usuario logueado como valor inicial en el formulario"""
        return {'user': request.user}

    def get_list_filter(self, request):
        filters = list(self.list_filter) if self.list_filter else []
        if request.user.is_superuser and 'user' not in filters:
            filters.append('user')
        return filters

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ('user',)
        return ()

    def save_model(self, request, obj, form, change):
        # Si no es superusuario, forzamos que el dueño sea él
        if not change and not request.user.is_superuser:
            obj.user = request.user
        # Si es superusuario y dejó el campo vacío (o para asegurar)
        elif not change and request.user.is_superuser and not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Para el superusuario, permitimos ver todos los usuarios en el dropdown
        if request.user.is_superuser:
            return super().formfield_for_foreignkey(db_field, request, **kwargs)

        if hasattr(db_field.remote_field, 'model'):
            related_model = db_field.remote_field.model
            if hasattr(related_model, 'user'):
                kwargs['queryset'] = related_model.objects.filter(user=request.user)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ======================================================
# CATEGORY
# ======================================================

@admin.register(Category)
class CategoryAdmin(UserOwnedAdmin):
    list_display = (
        'name',
        'transaction_type',
        'expense_type',
        'is_housing',
        'user',
    )
    list_filter = (
        'transaction_type',
        'expense_type',
        'is_housing',
    )
    search_fields = ('name',)


# ======================================================
# SUBCATEGORY
# ======================================================

@admin.register(SubCategory)
class SubCategoryAdmin(UserOwnedAdmin):
    list_display = (
        'name',
        'parent_category',
        'is_essential',
        'user',
    )
    list_filter = (
        'is_essential',
        'parent_category',
    )
    search_fields = (
        'name',
        'parent_category__name',
    )

    def save_model(self, request, obj, form, change):
        if obj.parent_category and obj.parent_category.user != obj.user:
            obj.user = obj.parent_category.user
        super().save_model(request, obj, form, change)


# ======================================================
# LOCATION
# ======================================================

@admin.register(Location)
class LocationAdmin(UserOwnedAdmin):
    list_display = ('name', 'user')
    search_fields = ('name',)


# ======================================================
# TRANSACTION
# ======================================================

@admin.register(Transaction)
class TransactionAdmin(UserOwnedAdmin):
    list_display = (
        'date',
        'description',
        'amount',          
        # 'transaction_type',
        'category',
        'subcategory',
        # 'location',        
    )

    list_filter = (
        YearFilter,
        MonthFilter,
        TransactionTypeFilter,
        SubCategorySearchFilter,
        'subcategory__parent_category',
        'location',
    )

    search_fields = ('description',)
    autocomplete_fields = ('subcategory', 'location')
    ordering = ('-date',)

    list_select_related = (
        'user',
        'subcategory',
        'subcategory__parent_category',
        'location',
    )

    @admin.display(description=_('Type'))
    def transaction_type(self, obj):
        return obj.subcategory.parent_category.transaction_type

    @admin.display(description=_('Category'))
    def category(self, obj):
        return obj.subcategory.parent_category.name

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            qs = response.context_data['cl'].queryset
            total = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            response.context_data['total_amount'] = total
        except Exception:
            pass
        return response
