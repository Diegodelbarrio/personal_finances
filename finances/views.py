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

    # 2. Años disponibles para el selector
    years = base_qs.annotate(y=ExtractYear('date')).values_list('y', flat=True).distinct().order_by('-y')
    
    # 3. Selección de año
    sel_year = request.GET.get('year')
    if sel_year:
        sel_year = int(sel_year)
    else:
        sel_year = now.year

    # 4. Meses disponibles para el año seleccionado
    months_qs = base_qs.filter(date__year=sel_year).annotate(m=ExtractMonth('date')).values_list('m', flat=True).distinct().order_by('m')
    months = [(m, month_name[m]) for m in months_qs]
    
    # 5. Selección de mes
    sel_month = request.GET.get('month')
    if sel_month:
        sel_month = int(sel_month)
    else:
        sel_month = now.month

    # 6. Queryset filtrado por el periodo seleccionado
    qs = base_qs.filter(date__year=sel_year, date__month=sel_month)

    # 7. Agregación de métricas
    metrics = qs.aggregate(
        income=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='INCOME')),
        expenses=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE')),
        fixed=Sum('amount', filter=Q(subcategory__parent_category__expense_type='FIXED')),
        variable=Sum('amount', filter=Q(subcategory__parent_category__expense_type='VARIABLE')),
        no_housing=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE') & ~Q(subcategory__parent_category__name='Housing'))
    )

    def clean(val): 
        return abs(val or 0)
    
    inc = clean(metrics['income'])
    exp = clean(metrics['expenses'])

    # 8. Cálculo del ingreso del mes anterior
    if sel_month == 1:
        prev_month = 12
        prev_year = sel_year - 1
    else:
        prev_month = sel_month - 1
        prev_year = sel_year

    prev_metrics = base_qs.filter(
        date__year=prev_year,
        date__month=prev_month,
        subcategory__parent_category__transaction_type='INCOME'
    ).aggregate(total=Sum('amount'))

    prev_income = clean(prev_metrics['total'])

    # 9. Contexto para el template
    context = {
        'transactions': qs.order_by('-date'),
        'years': years,
        'months': months,
        'sel_year': sel_year,
        'sel_month': sel_month,
        'prev_income': prev_income,  # <- pasado al template
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
