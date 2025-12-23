from django.shortcuts import render
from django.db.models import Sum, Max
import datetime
from .models import Asset
from django.contrib.auth.decorators import login_required

@login_required
def investments_dashboard(request):
    # 1. FILTRO DE SEGURIDAD: Solo activos del usuario actual
    assets = Asset.objects.filter(user=request.user)
    
    portfolio_data = []
    global_invested = 0
    global_current_value = 0
    last_market_dates = []

    temp_list = []

    for asset in assets:
        # Al venir de 'assets' ya filtrados, su history y transactions son privados
        last_market_record = asset.history.order_by('-date').first()
        last_market_date = last_market_record.date if last_market_record else None

        if last_market_date:
            last_market_dates.append(last_market_date)

        tx_qs = asset.transactions.all()
        if last_market_date:
            tx_qs = tx_qs.filter(date__lte=last_market_date)

        invested = tx_qs.aggregate(total=Sum('amount'))['total'] or 0
        current_value = last_market_record.total_value if last_market_record else invested
        profit_loss = current_value - invested
        roi = (profit_loss / invested * 100) if invested != 0 else 0

        temp_list.append({
            'obj': asset,
            'invested': invested,
            'current_value': current_value,
            'profit_loss': profit_loss,
            'roi': roi,
        })

        global_invested += invested
        global_current_value += current_value

    # Asignar porcentajes de allocation (basado solo en el portfolio del usuario)
    for item in temp_list:
        allocation_raw = (item['current_value'] / global_current_value * 100) if global_current_value > 0 else 0
        item['allocation_display'] = round(allocation_raw, 1)
        item['allocation_css'] = f"{round(allocation_raw, 0)}%"
        portfolio_data.append(item)

    last_market_date_global = max(last_market_dates) if last_market_dates else None

    context = {
        'portfolio': portfolio_data,
        'global_invested': global_invested,
        'global_current_value': global_current_value,
        'global_profit_loss': global_current_value - global_invested,
        'global_roi': ((global_current_value - global_invested) / global_invested * 100) if global_invested != 0 else 0,
        'last_market_date': last_market_date_global, 
    }

    return render(request, 'investments/investment_dashboard.html', context)