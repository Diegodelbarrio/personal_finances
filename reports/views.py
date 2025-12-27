from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .services import services

@login_required
def financial_report(request):
    """
    Vista para el reporte de flujo de caja (Ingresos vs Gastos)
    """
    # 1. Determinar el año (por defecto el actual)
    now = timezone.now()
    try:
        current_year = int(request.GET.get('year', now.year))
    except ValueError:
        current_year = now.year

    # 2. Obtener lista de años para el selector
    available_years = services.get_available_years(request.user)
    
    # 3. Llamar al servicio orquestador
    report_data = services.get_financial_annual_report(request.user, current_year)

    context = {
        'active_tab': 'finance', 
        'selected_year': current_year,
        'years': available_years,
        'report': report_data,
        'page_title': f'Financial Report {current_year}'
    }
    return render(request, 'reports/financial_report.html', context)

@login_required
def investment_report(request):
    """
    Vista para el reporte de evolución de inversiones (Invested vs Market Value)
    """
    now = timezone.now()
    try:
        current_year = int(request.GET.get('year', now.year))
    except ValueError:
        current_year = now.year

    available_years = services.get_available_years(request.user)
    
    # Llamada al servicio de inversiones
    report_data = services.get_investment_annual_report(request.user, current_year)

    context = {
        'active_tab': 'investments',
        'selected_year': current_year,
        'years': available_years,
        'report': report_data,
        'page_title': f'Investment Report {current_year}'
    }
    return render(request, 'reports/investment_report.html', context)

@login_required
def holdings_report(request):
    now = timezone.now()
    current_year = int(request.GET.get('year', now.year))
    available_years = services.get_available_years(request.user)
    
    report_data = services.get_holdings_annual_report(request.user, current_year)

    context = {
        'active_tab': 'holdings',
        'selected_year': current_year,
        'years': available_years,
        'report': report_data,
        'page_title': f'Cash Holdings {current_year}'
    }
    # CORRECCIÓN: Apuntar al template de holdings
    return render(request, 'reports/holdings_report.html', context)