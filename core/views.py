from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.utils import timezone
from datetime import timedelta
from holdings.views import get_net_worth_evolution
from holdings.models import AccountBalanceSnapshot, BankAccount
from investments.models import Asset, AssetHistory

@login_required
def home(request):
    # Mantenemos la evolución para la gráfica
    net_worth_history = get_net_worth_evolution(request.user)
    
    # --- CÁLCULO DEL PATRIMONIO ACTUAL REAL ---
    current_net_worth = 0
    snapshot_dates = []

    # A. Cuentas de Efectivo (Cash)
    accounts = BankAccount.objects.filter(user=request.user)
    for acc in accounts:
        # Obtenemos el último balance registrado de ESTA cuenta
        last_balance = AccountBalanceSnapshot.objects.filter(account=acc).order_by('-date').first()
        if last_balance:
            current_net_worth += float(last_balance.balance)
            snapshot_dates.append(last_balance.date)

    # B. Inversiones (Investments)
    assets = Asset.objects.filter(user=request.user)
    for asset in assets:
        # Obtenemos el último valor de mercado de ESTE activo
        last_val = AssetHistory.objects.filter(asset=asset).order_by('-date').first()
        if last_val:
            current_net_worth += float(last_val.total_value)
            snapshot_dates.append(last_val.date)

    # --- DETERMINAR LA FECHA DE REFERENCIA (La más antigua de las últimas) ---
    # Si tengo datos de Noviembre y Diciembre, la fecha que manda es la de Noviembre
    last_market_date = min(snapshot_dates) if snapshot_dates else None

    # Indicador de desactualización (30 días)
    is_stale = False
    if last_market_date:
        # Si la fecha más antigua de nuestro set es de hace más de 30 días respecto a hoy
        if last_market_date < (timezone.now().date() - timedelta(days=30)):
            is_stale = True

    context = {
        'net_worth_history': net_worth_history,
        'current_net_worth': current_net_worth,
        'last_market_date': last_market_date,
        'is_stale': is_stale,
        'user_name': request.user.username,
    }
    return render(request, 'core/index.html', context)