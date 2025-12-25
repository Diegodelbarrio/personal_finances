from django.db.models import Sum
from django.db.models.functions import TruncMonth
from .models import AccountBalanceSnapshot
from investments.models import AssetHistory 
from collections import defaultdict

def get_net_worth_evolution(user):
    """
    Calcula la evolución del patrimonio neto desglosado por cash e inversiones.
    """
    # 1. Cash por mes
    cash_by_month = AccountBalanceSnapshot.objects.filter(
        account__user=user
    ).annotate(
        month_trunc=TruncMonth('date')
    ).values('month_trunc').annotate(
        total_cash=Sum('balance')
    ).order_by('month_trunc')

    # 2. Inversiones por mes
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

    # 4. Generar lista final ordenada con DESGLOSE
    history = []
    sorted_months = sorted(consolidated.keys())
    
    for m in sorted_months:
        cash = consolidated[m]['cash']
        inv = consolidated[m]['inv']
        
        history.append({
            'date': m,               
            'label': m.strftime('%b %y'), 
            'savings': cash,         # <--- CLAVE NUEVA
            'investments': inv,      # <--- CLAVE NUEVA
            'value': cash + inv      # Mantenemos 'value' para el total
        })

    return history