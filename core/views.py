from datetime import date
import logging

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse

# Servicios de las diferentes Apps
from core.services.live_market import get_live_market_context
from core.services.portfolio_market import get_portfolio_market_context
from core.services.csv_import import get_csv_template_payload
from core.services.net_worth import calculate_net_worth
from finances.services.api import get_annual_cashflow_summary
from finances.services.selectors import get_emergency_fund_status
from holdings.services.history import get_net_worth_evolution
from settings.services.api import SettingsService


logger = logging.getLogger(__name__)


def health(request):
    """Minimal liveness/readiness response without exposing internal details."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check failed")
        return JsonResponse({"status": "unhealthy"}, status=503)

    return JsonResponse({"status": "ok"})

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

    # 4. Datos del Fondo de Emergencia
    emergency_fund_data = get_emergency_fund_status(request.user)

    # 5. Contexto Final para el template
    context = {
        "net_worth_history": net_worth_history,
        "stats": stats,
        "user_name": request.user.username,
        "total_annual_savings": total_annual_savings,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "emergency_fund": emergency_fund_data,
        **net_worth_data,
    }

    return render(request, "core/index.html", context)

@login_required
def compound_interest_calculator(request):
    presets = [
        {
            "key": "conservative",
            "title": "Conservative",
            "rate": "4",
            "rate_label": "4.0%",
            "inflation": "2",
            "contribution_growth": "1",
            "icon": "bi-shield-check",
            "icon_class": "text-info",
            "active": False,
        },
        {
            "key": "balanced",
            "title": "Balanced",
            "rate": "7",
            "rate_label": "7.0%",
            "inflation": "2",
            "contribution_growth": "0",
            "icon": "bi-graph-up-arrow",
            "icon_class": "text-primary",
            "active": True,
        },
        {
            "key": "growth",
            "title": "Growth",
            "rate": "9.5",
            "rate_label": "9.5%",
            "inflation": "2.5",
            "contribution_growth": "2",
            "icon": "bi-rocket-takeoff",
            "icon_class": "text-success",
            "active": False,
        },
    ]
    currencies = [
        {"code": "EUR", "default": True},
        {"code": "USD", "default": False},
        {"code": "GBP", "default": False},
        {"code": "CHF", "default": False},
    ]

    return render(request, "core/compound_interest.html", {
        "page_title": "Compound Interest Calculator",
        "compound_interest_presets": presets,
        "compound_interest_currencies": currencies,
    })


@login_required
def investment_dashboard(request):
    selected_period = request.GET.get("period", "1y")
    selected_asset_id = request.GET.get("asset_id")
    query = request.GET.get("q", "")

    context = get_portfolio_market_context(
        user=request.user,
        period=selected_period,
        asset_id=selected_asset_id,
        query=query,
    )
    return render(request, "core/market_data.html", context)


@login_required
def live_market_dashboard(request):
    selected_period = request.GET.get("period", "1y")
    selected_asset_id = request.GET.get("asset_id")
    query = request.GET.get("q", "")
    force_refresh = request.GET.get("refresh") == "1"

    context = get_live_market_context(
        user=request.user,
        period=selected_period,
        asset_id=selected_asset_id,
        query=query,
        force_refresh=force_refresh,
    )
    return render(request, "core/live_market_data.html", context)


@login_required
def download_csv_template(request, template_key):
    payload = get_csv_template_payload(template_key)
    if payload is None:
        raise Http404("CSV template not found.")

    response = HttpResponse(payload["content"], content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{payload["filename"]}"'
    return response
