from django.db.models import Sum, Q
from calendar import month_name

def _clean(val):
    return abs(val or 0)

def get_period_metrics(qs):
    metrics = qs.aggregate(
        income=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='INCOME')),
        expenses=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE')),
        fixed=Sum('amount', filter=Q(subcategory__parent_category__expense_type='FIXED')),
        variable=Sum('amount', filter=Q(subcategory__parent_category__expense_type='VARIABLE')),
        no_housing=Sum('amount', filter=Q(subcategory__parent_category__transaction_type='EXPENSE') & 
                                 Q(subcategory__parent_category__is_housing=False))
    )
    
    inc = _clean(metrics['income'])
    exp = _clean(metrics['expenses'])
    
    return {
        "income": inc,
        "expenses": exp,
        "fixed": _clean(metrics['fixed']),
        "variable": _clean(metrics['variable']),
        "no_housing": _clean(metrics['no_housing']),
        "savings": inc - exp,
        "is_incomplete": (inc - exp) < 0 and inc < 2000
    }

def get_previous_month_income(base_qs, year, month):
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    data = base_qs.filter(
        date__year=prev_year,
        date__month=prev_month,
        subcategory__parent_category__transaction_type='INCOME'
    ).aggregate(total=Sum('amount'))
    
    return _clean(data['total'])

def get_expense_distribution_chart(qs):
    expense_stats = qs.filter(
        subcategory__parent_category__transaction_type='EXPENSE'
    ).values(
        'subcategory__parent_category__name'
    ).annotate(total=Sum('amount')).order_by('-total')

    return {
        "labels": [item['subcategory__parent_category__name'] for item in expense_stats],
        "data": [float(_clean(item['total'])) for item in expense_stats]
    }