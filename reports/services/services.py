# reports/services.py

from finances.services.api import get_annual_cashflow_summary, get_available_transaction_years
from investments.services.api import get_annual_portfolio_evolution
from holdings.services.api import get_annual_balance_evolution

def get_available_years(user):
    return get_available_transaction_years(user)

# 1. REPORTE FINANCIERO (Flujo de caja)
def get_financial_annual_report(user, year):
    monthly_data = get_annual_cashflow_summary(user, year)
    
    annual_stats = {
        "income": sum(m["income"] for m in monthly_data),
        "expenses": sum(m["expenses"] for m in monthly_data),
        "fixed_total": sum(m["fixed"] for m in monthly_data),
        "variable_total": sum(m["variable"] for m in monthly_data),
        "savings": sum(m["savings"] for m in monthly_data),
    }

    # Cálculos derivados
    annual_stats["avg_monthly_expenses"] = annual_stats["expenses"] / 12 if annual_stats["expenses"] > 0 else 0
    annual_stats["avg_savings_rate"] = (
        (annual_stats["savings"] / annual_stats["income"] * 100) 
        if annual_stats["income"] > 0 else 0
    )

    return {
        "year": year,
        "monthly_data": monthly_data,
        "annual_stats": annual_stats,
        'annual_savings_rule_labels': ['Savings', 'Fixed', 'Variable'],
        'annual_savings_rule_data': [
            max(0, float(annual_stats["savings"])), 
            float(annual_stats["fixed_total"]), 
            float(annual_stats["variable_total"])
        ]
    }

# 2. REPORTE INVERSIONES (Rendimiento)
def get_investment_annual_report(user, year):
    monthly_data = get_annual_portfolio_evolution(user, year)
    
    # Obtenemos el último mes disponible para valores de "Cierre" (Balance)
    last_month = monthly_data[-1] if monthly_data else {}
    
    annual_stats = {
        "total_contributions": sum(m.get("contributions", 0) for m in monthly_data),
        "total_profit": sum(m.get("profit_loss", 0) for m in monthly_data),
        "final_invested": last_month.get("invested", 0),
        "final_market_value": last_month.get("market_value", 0),
    }
    
    # ROI Anual basado en el beneficio total sobre el capital final invertido
    if annual_stats["final_invested"] > 0:
        annual_stats["annual_roi"] = (annual_stats["total_profit"] / annual_stats["final_invested"]) * 100
    else:
        annual_stats["annual_roi"] = 0
    
    return {
        "year": year,
        "monthly_data": monthly_data,
        "annual_stats": annual_stats
    }

# 3. REPORTE HOLDINGS (Saldos en cuenta)

def get_holdings_annual_report(user, year):
    # Asumimos que esta función devuelve la estructura con 'matrix' (cuentas) 
    # y 'month_names' (fechas) que ya usas en la tabla.
    report_data = get_annual_balance_evolution(user, year)
    
    # 1. Preparar etiquetas de los meses (Ene 24, Feb 24...)
    labels = [m.strftime("%b %y") for m in report_data['month_names']]
    
    # 2. Preparar Datasets para la gráfica de barras apiladas
    bar_datasets = []
    for row in report_data['matrix']:
        bar_datasets.append({
            "label": row['account_name'],
            "data": [float(b) for b in row['balances']]
        })
    
    return {
        "report": report_data,
        "bar_labels": labels,
        "bar_datasets": bar_datasets,
        "year": year,
        "monthly_data": report_data
    }