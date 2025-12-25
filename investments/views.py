from django.shortcuts import render
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.contrib.auth.decorators import login_required
from .models import Asset, Transaction, AssetHistory

@login_required
def investments_dashboard(request):
    # Definimos el nombre del asset a excluir para usarlo en varios sitios
    EXCLUDE_ASSET_NAME = 'Family Investments'
    
    assets = Asset.objects.filter(user=request.user)
    
    portfolio_data = []
    global_invested = 0
    global_current_value = 0
    last_market_dates = []
    temp_list = []

    # 1. Procesamiento de activos individuales
    for asset in assets:
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
            'invested': float(invested),
            'current_value': float(current_value),
            'profit_loss': float(profit_loss),
            'roi': float(roi),
        })
        global_invested += float(invested)
        global_current_value += float(current_value)

    # 2. Porcentajes de alocación
    for item in temp_list:
        allocation_raw = (item['current_value'] / global_current_value * 100) if global_current_value > 0 else 0
        item['allocation_display'] = round(allocation_raw, 1)
        item['allocation_css'] = f"{round(allocation_raw, 0)}%"
        portfolio_data.append(item)

    # 3. Historia de rendimiento EXCLUYENDO Family Investment
    # Filtramos las transacciones para que no sumen las de 'Family Investment'
    contributions = Transaction.objects.filter(
        asset__user=request.user
    ).exclude(
        asset__name=EXCLUDE_ASSET_NAME
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(total=Sum('amount')).order_by('month')

    # Filtramos el historial de precios para que no sume el de 'Family Investment'
    market_history = AssetHistory.objects.filter(
        asset__user=request.user
    ).exclude(
        asset__name=EXCLUDE_ASSET_NAME
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(total=Sum('total_value')).order_by('month')

    all_months = sorted(list(set(
        [c['month'] for c in contributions if c['month']] + 
        [m['month'] for m in market_history if m['month']]
    )))

    performance_history = []
    running_invested = 0
    last_market_value = 0

    for m in all_months:
        current_month_contrib = next((c['total'] for c in contributions if c['month'] == m), 0)
        running_invested += float(current_month_contrib or 0)
        current_month_market = next((mh['total'] for mh in market_history if mh['month'] == m), None)
        
        if current_month_market is not None:
            last_market_value = float(current_month_market)
        else:
            # Si un mes no tiene foto de mercado, el valor es al menos el invertido acumulado
            last_market_value = max(last_market_value, running_invested)

        performance_history.append({
            'label': m.strftime('%b %y'),
            'invested': running_invested,
            'market': last_market_value
        })

    # 4. Cálculos finales (Totales y Desglose Ex-Family)
    global_profit_loss = global_current_value - global_invested
    global_roi = (global_profit_loss / global_invested * 100) if global_invested != 0 else 0
    
    portfolio_no_family = [item for item in temp_list if item['obj'].name != EXCLUDE_ASSET_NAME]
    no_family_invested = sum(item['invested'] for item in portfolio_no_family)
    no_family_value = sum(item['current_value'] for item in portfolio_no_family)
    no_family_profit_loss = no_family_value - no_family_invested
    no_family_roi = (no_family_profit_loss / no_family_invested * 100) if no_family_invested != 0 else 0

    # 5. Datos para el gráfico Donut (Asset Allocation)
    # Filtramos el portfolio para el gráfico
    chart_assets = [item for item in temp_list if item['obj'].name != EXCLUDE_ASSET_NAME]
    
    # Ordenamos por valor actual para que el gráfico sea legible (de mayor a menor)
    chart_assets.sort(key=lambda x: x['current_value'], reverse=True)

    allocation_labels = [item['obj'].name for item in chart_assets]
    allocation_data = [item['current_value'] for item in chart_assets]

# --- 6. Datos para Gráfico de Barras Apiladas (Aportaciones Mensuales) ---
    contributions_by_asset = Transaction.objects.filter(
        asset__user=request.user
    ).exclude(
        asset__name=EXCLUDE_ASSET_NAME
    ).annotate(
        month=TruncMonth('date')
    ).values('month', 'asset__name').annotate(
        total=Sum('amount')
    ).order_by('month') # Orden base desde DB

    # Extraemos objetos datetime únicos y los ordenamos cronológicamente
    unique_months = sorted(list(set(c['month'] for c in contributions_by_asset if c['month'])))
    
    # Formateamos las etiquetas para el gráfico
    monthly_labels = [m.strftime('%b %y') for m in unique_months]
    
    asset_names = sorted(list(set(c['asset__name'] for c in contributions_by_asset)))
    bar_chart_datasets = []
    
    for asset_name in asset_names:
        data_points = []
        for m_obj in unique_months:
            # Buscamos el valor comparando el objeto mes completo, no el string
            val = next((c['total'] for c in contributions_by_asset 
                       if c['month'] == m_obj and c['asset__name'] == asset_name), 0)
            data_points.append(float(val))
        
        bar_chart_datasets.append({
            'label': asset_name,
            'data': data_points
        })

    context = {
        'portfolio': portfolio_data,
        'global_invested': global_invested,
        'global_current_value': global_current_value,
        'global_profit_loss': global_profit_loss,
        'global_roi': global_roi,
        'no_family_invested': no_family_invested,
        'no_family_value': no_family_value,
        'no_family_profit_loss': no_family_profit_loss,
        'no_family_roi': no_family_roi,
        'last_market_date': max(last_market_dates) if last_market_dates else None,
        'performance_history': performance_history,
        'allocation_labels': allocation_labels,
        'allocation_data': allocation_data,
        'bar_labels': monthly_labels,
        'bar_datasets': bar_chart_datasets,
    }

    return render(request, 'investments/investment_dashboard.html', context)