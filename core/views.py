from datetime import date
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Servicios de las diferentes Apps
from core.services.net_worth import calculate_net_worth
from holdings.services.history import get_net_worth_evolution
from settings.services.api import SettingsService
from finances.services.api import get_annual_cashflow_summary

@login_required
def home(request):
    """
    Dashboard principal que unifica datos de inversiones, 
    finanzas mensuales y objetivos personales.
    """
    # 1. Datos de Patrimonio (Net Worth) e Historial
    # net_worth_data suele traer: current_net_worth, last_market_date, is_stale, etc.
    net_worth_history = get_net_worth_evolution(request.user)
    net_worth_data = calculate_net_worth(request.user)
    
    # Obtenemos el valor actual del patrimonio para la API de Settings
    current_nw = net_worth_data.get('current_net_worth', 0)

    # 2. Calcular Ahorro Anual Real (App Finances)
    current_date = date.today()
    annual_data = get_annual_cashflow_summary(request.user, current_date.year)
    
    # Calculamos el ahorro neto sumando (Ingresos - Gastos) de cada mes
    # Filtramos para sumar solo hasta el mes actual
    total_income = sum(m['income'] for m in annual_data if m['month'] <= current_date.month)
    total_expenses = sum(m['expenses'] for m in annual_data if m['month'] <= current_date.month)
    
    # Ahorro neto real acumulado en el año
    total_annual_savings = total_income - total_expenses

    # 3. Calcular Progreso de Objetivos (App Settings)
    # Inyectamos los valores reales calculados arriba
    stats = SettingsService.calculate_goals_progress(
        request.user, 
        current_net_worth=current_nw, 
        current_annual_savings=total_annual_savings
    )

    # 4. Contexto Final para el template
    context = {
        "net_worth_history": net_worth_history,
        "stats": stats,
        "user_name": request.user.username,
        "total_annual_savings": total_annual_savings,
        "total_income": total_income,
        "total_expenses": total_expenses,
        **net_worth_data, #
    }

    return render(request, "core/index.html", context)