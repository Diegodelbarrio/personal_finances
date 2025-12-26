# import calendar
# from decimal import Decimal
# from django.shortcuts import render
# from django.db.models import Sum, Q
# from django.db.models.functions import ExtractYear, ExtractMonth
# from django.utils import timezone
# from calendar import month_name
# from .models import Transaction
# from django.contrib.auth.decorators import login_required

# @login_required
# def summary(request):
#     # 1. Filtro base de seguridad por usuario
#     base_qs = Transaction.objects.filter(user=request.user).select_related('subcategory__parent_category')

#     now = timezone.now()

#     # 2. Años disponibles para el usuario
#     years = base_qs.annotate(y=ExtractYear('date')).values_list('y', flat=True).distinct().order_by('-y')
    
#     # 3. Selección de año
#     sel_year = request.GET.get('year')
#     sel_year = int(sel_year) if sel_year else now.year

#     # 4. Meses disponibles para este usuario en este año
#     months_qs = base_qs.filter(date__year=sel_year).annotate(m=ExtractMonth('date')).values_list('m', flat=True).distinct().order_by('m')
#     months = [(m, month_name[m]) for m in months_qs]
    
#     # 5. Selección de mes
#     sel_month = request.GET.get('month')
#     sel_month = int(sel_month) if sel_month else now.month

#     # 6. Datos del periodo seleccionado
#     qs = base_qs.filter(date__year=sel_year, date__month=sel_month)

#     # 7. Agregación de métricas para KPIs
#     metrics = qs.aggregate(
#         income=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='INCOME')),
#         expenses=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE')),
#         fixed=Sum('amount', filter=Q(subcategory__parent_category__expense_type='FIXED')),
#         variable=Sum('amount', filter=Q(subcategory__parent_category__expense_type='VARIABLE')),
#         no_housing=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE') & 
#                                  Q(subcategory__parent_category__is_housing=False))
#     )

#     def clean(val): 
#         return abs(val or 0)
    
#     inc = clean(metrics['income'])
#     exp = clean(metrics['expenses'])

#     # Lógica de aviso: ahorros negativos e ingresos bajos (posibles datos faltantes)
#     savings = inc - exp
#     is_incomplete = False
#     if savings < 0 and inc < 2000:
#         is_incomplete = True

#     # 8. Cálculo de ingresos del mes anterior (para comparativas)
#     if sel_month == 1:
#         prev_month = 12
#         prev_year = sel_year - 1
#     else:
#         prev_month = sel_month - 1
#         prev_year = sel_year

#     prev_income_data = base_qs.filter(
#         date__year=prev_year,
#         date__month=prev_month,
#         subcategory__parent_category__transaction_type='INCOME'
#     ).aggregate(total=Sum('amount'))
#     prev_income = clean(prev_income_data['total'])

#     # 9. Lógica para el gráfico de distribución de gastos
#     expense_stats = qs.filter(
#         subcategory__parent_category__transaction_type='EXPENSE'
#     ).values(
#         'subcategory__parent_category__name'
#     ).annotate(
#         total=Sum('amount')
#     ).order_by('-total')

#     chart_labels = [item['subcategory__parent_category__name'] for item in expense_stats]
#     chart_data = [float(abs(item['total'] or 0)) for item in expense_stats]

#     # 10. Datos para la gráfica de Regla de Ahorro (Savings Rule)
#     # Calculamos los 3 pilares
#     fixed_val = clean(metrics['fixed'])
#     variable_val = clean(metrics['variable'])
#     savings_val = max(0, float(inc - exp)) # Solo si hay capacidad de ahorro

#     savings_rule_labels = ['Savings', 'Fixed Expenses', 'Variable Expenses']
#     savings_rule_data = [savings_val, float(fixed_val), float(variable_val)]

#     context = {
#         'transactions': qs.order_by('-date'),
#         'years': years,
#         'months': months,
#         'sel_year': sel_year,
#         'sel_month': sel_month,
#         'prev_income': prev_income,
#         'chart_labels': chart_labels,
#         'chart_data': chart_data,
#         'savings_rule_labels': savings_rule_labels,
#         'savings_rule_data': savings_rule_data,
#         'is_incomplete': is_incomplete,
#         'savings_val': savings, # Lo pasamos para usarlo en el mensaje
#         'kpis': [
#             {'label': 'Net Savings', 'value': inc - exp, 'class': 'soft-primary'},
#             {'label': 'Total Income', 'value': inc, 'class': 'soft-success'},
#             {'label': 'Total Expenses', 'value': exp, 'class': 'soft-danger'},
#             {'label': 'Fixed Expenses', 'value': clean(metrics['fixed']), 'class': 'soft-secondary'},
#             {'label': 'Variable Expenses', 'value': clean(metrics['variable']), 'class': 'soft-warning'},
#             {'label': 'No Housing', 'value': clean(metrics['no_housing']), 'class': 'soft-info'},
#         ]
#     }
#     return render(request, 'finances/summary.html', context)

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .services.selectors import get_summary_page_data

@login_required
def summary(request):
    # 1. Entrada de datos (Input)
    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    
    # 2. Lógica de negocio/selección (Process)
    context = get_summary_page_data(request.user, year, month)
    
    # 3. Respuesta (Output)
    return render(request, 'finances/summary.html', context)