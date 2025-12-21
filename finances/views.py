from django.shortcuts import render
from django.db.models import Sum, Q
from django.db.models.functions import ExtractYear, ExtractMonth
from django.utils import timezone
from calendar import month_name
from .models import Transaction

def summary(request):
    # 1. Referencia de tiempo actual
    now = timezone.now()
    base_qs = Transaction.objects.select_related('subcategory__parent_category')

    # 2. Años disponibles para el selector (se mantiene dinámico según tus datos)
    years = base_qs.annotate(y=ExtractYear('date')).values_list('y', flat=True).distinct().order_by('-y')
    
    # LÓGICA DE CARGA POR DEFECTO:
    # Prioridad: 1. Parámetro URL -> 2. Año actual del sistema
    sel_year = request.GET.get('year')
    if sel_year:
        sel_year = int(sel_year)
    else:
        sel_year = now.year

    # 3. Meses disponibles para el año seleccionado
    months_qs = base_qs.filter(date__year=sel_year).annotate(m=ExtractMonth('date')).values_list('m', flat=True).distinct().order_by('m')
    months = [(m, month_name[m]) for m in months_qs]
    
    # LÓGICA DE CARGA POR DEFECTO:
    # Prioridad: 1. Parámetro URL -> 2. Mes actual del sistema
    sel_month = request.GET.get('month')
    if sel_month:
        sel_month = int(sel_month)
    else:
        sel_month = now.month

    # 4. Queryset filtrado por el periodo seleccionado
    qs = base_qs.filter(date__year=sel_year, date__month=sel_month)

    # 5. Agregación de métricas (se mantiene igual, es muy eficiente)
    metrics = qs.aggregate(
        income=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='INCOME')),
        expenses=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE')),
        fixed=Sum('amount', filter=Q(subcategory__parent_category__expense_type='FIXED')),
        variable=Sum('amount', filter=Q(subcategory__parent_category__expense_type='VARIABLE')),
        no_housing=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE') & ~Q(subcategory__parent_category__name='Housing'))
    )

    def clean(val): return abs(val or 0)
    
    inc = clean(metrics['income'])
    exp = clean(metrics['expenses'])

    context = {
        'transactions': qs.order_by('-date'),
        'years': years,
        'months': months,
        'sel_year': sel_year,
        'sel_month': sel_month,
        'kpis': [
            {'label': 'Net Savings', 'value': inc - exp, 'class': 'soft-primary'},
            {'label': 'Total Income', 'value': inc, 'class': 'soft-success'},
            {'label': 'Total Expenses', 'value': exp, 'class': 'soft-danger'},
            {'label': 'Fixed Expenses', 'value': clean(metrics['fixed']), 'class': 'soft-secondary'},
            {'label': 'Variable Expenses', 'value': clean(metrics['variable']), 'class': 'soft-warning'},
            {'label': 'No Housing', 'value': clean(metrics['no_housing']), 'class': 'soft-info'},
        ]
    }
    return render(request, 'finances/summary.html', context)