from django.db.models import Sum
from django.db.models.functions import TruncMonth
from .models import AccountBalanceSnapshot
from investments.models import AssetHistory 
from collections import defaultdict

def get_net_worth_evolution():
    # 1. Agrupamos y sumamos TODO el cash de holdings por mes
    cash_by_month = AccountBalanceSnapshot.objects.annotate(
        month_trunc=TruncMonth('date')
    ).values('month_trunc').annotate(
        total_cash=Sum('balance')
    ).order_by('month_trunc')

    # 2. Agrupamos y sumamos TODOS los activos de AssetsHistory por mes
    # Usamos total_value y date según la estructura de tu modelo
    inv_by_month = AssetHistory.objects.annotate(
        month_trunc=TruncMonth('date')
    ).values('month_trunc').annotate(
        total_inv=Sum('total_value')
    ).order_by('month_trunc')

    # 3. Consolidación en un diccionario usando el mes truncado como clave
    consolidated = defaultdict(lambda: {'cash': 0.0, 'inv': 0.0})

    for entry in cash_by_month:
        m = entry['month_trunc']
        if m: # Evitar nulos
            consolidated[m]['cash'] = float(entry['total_cash'] or 0)

    for entry in inv_by_month:
        m = entry['month_trunc']
        if m:
            consolidated[m]['inv'] = float(entry['total_inv'] or 0)

    # 4. Generar la lista final para el gráfico (ordenada cronológicamente)
    history = []
    sorted_months = sorted(consolidated.keys())
    
    for m in sorted_months:
        cash = consolidated[m]['cash']
        inv = consolidated[m]['inv']
        net_worth = cash + inv
        
        history.append({
            'label': m.strftime('%b %y'), # Formato: Nov 24, Dec 24...
            'value': net_worth
        })

    return history