from django.db.models import Sum
from django.db.models.functions import TruncMonth
from .models import AccountBalanceSnapshot
from investments.models import AssetHistory 
from collections import defaultdict

def get_net_worth_evolution(user):
    """
    Calcula la evolución del patrimonio neto filtrando 
    estrictamente por el usuario proporcionado.
    """
    # 1. Cash por mes (Filtramos por account__user ya que Snapshot no tiene user directo)
    cash_by_month = AccountBalanceSnapshot.objects.filter(
        account__user=user
    ).annotate(
        month_trunc=TruncMonth('date')
    ).values('month_trunc').annotate(
        total_cash=Sum('balance')
    ).order_by('month_trunc')

    # 2. Inversiones por mes (Filtramos por asset__user)
    inv_by_month = AssetHistory.objects.filter(
        asset__user=user
    ).annotate(
        month_trunc=TruncMonth('date')
    ).values('month_trunc').annotate(
        total_inv=Sum('total_value')
    ).order_by('month_trunc')

    # 3. Consolidación
    consolidated = defaultdict(lambda: {'cash': 0.0, 'inv': 0.0})

    for entry in cash_by_month:
        m = entry['month_trunc']
        if m:
            consolidated[m]['cash'] = float(entry['total_cash'] or 0)

    for entry in inv_by_month:
        m = entry['month_trunc']
        if m:
            consolidated[m]['inv'] = float(entry['total_inv'] or 0)

    # 4. Generar lista final ordenada
    history = []
    sorted_months = sorted(consolidated.keys())
    
    for m in sorted_months:
        cash = consolidated[m]['cash']
        inv = consolidated[m]['inv']
        net_worth = cash + inv
        
        history.append({
            'label': m.strftime('%b %y'), 
            'value': net_worth
        })

    return history