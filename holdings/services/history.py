from collections import defaultdict
from django.db.models import Sum
from django.db.models.functions import TruncMonth

from holdings.models import AccountBalanceSnapshot
from investments.models import AssetHistory


def get_net_worth_evolution(user):
    """
    Calcula la evolución del patrimonio neto desglosado por cash e inversiones.
    Devuelve una lista ordenada por mes.
    """

    # 1. Cash por mes
    cash_by_month = (
        AccountBalanceSnapshot.objects
        .filter(account__user=user)
        .annotate(month_trunc=TruncMonth('date'))
        .values('month_trunc')
        .annotate(total_cash=Sum('balance'))
        .order_by('month_trunc')
    )

    # 2. Inversiones por mes
    inv_by_month = (
        AssetHistory.objects
        .filter(asset__user=user)
        .annotate(month_trunc=TruncMonth('date'))
        .values('month_trunc')
        .annotate(total_inv=Sum('total_value'))
        .order_by('month_trunc')
    )

    # 3. Consolidación
    consolidated = defaultdict(lambda: {'cash': 0.0, 'inv': 0.0})

    for entry in cash_by_month:
        month = entry['month_trunc']
        if month:
            consolidated[month]['cash'] = float(entry['total_cash'] or 0)

    for entry in inv_by_month:
        month = entry['month_trunc']
        if month:
            consolidated[month]['inv'] = float(entry['total_inv'] or 0)

    # 4. Lista final ordenada
    history = []
    for month in sorted(consolidated.keys()):
        cash = consolidated[month]['cash']
        inv = consolidated[month]['inv']

        history.append({
            'date': month,
            'label': month.strftime('%b %y'),
            'savings': cash,
            'investments': inv,
            'value': cash + inv,
        })

    return history
