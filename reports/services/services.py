# reports/services.py

from finances.services.api import get_annual_cashflow_summary, get_available_transaction_years
from investments.services.api import get_annual_portfolio_evolution, get_investment_detailed_evolution
from holdings.services.api import get_annual_balance_evolution

def get_available_years(user):
    return get_available_transaction_years(user)

# 1. REPORTE FINANCIERO (Flujo de caja)
def get_financial_annual_report(user, year):
    # It comes pre-cut (e.g. if it is January, it only contains 1 item)
    monthly_data = get_annual_cashflow_summary(user, year)
    # Generamos la lista de objetos fecha para las cabeceras de la tabla
    month_names = [m["date_obj"] for m in monthly_data]
    active_months = len(monthly_data) if len(monthly_data) > 0 else 1

    # 1. Identificar todas las categorías únicas que han tenido gastos este año
    all_categories = set()
    for m in monthly_data:
        all_categories.update(m["categories"].keys())
    
    # We count months with actual activity for fair averages.
    active_months_count = sum(1 for m in monthly_data if m["income"] > 0 or m["expenses"] > 0)
    divisor = active_months_count if active_months_count > 0 else 1

    annual_stats = {
        "income": sum(m["income"] for m in monthly_data),
        "expenses": sum(m["expenses"] for m in monthly_data),
        "fixed_total": sum(m["fixed"] for m in monthly_data),
        "variable_total": sum(m["variable"] for m in monthly_data),
        "savings": sum(m["savings"] for m in monthly_data),
    }

    # Annual averages based only on months with activity
    annual_stats["avg_income"] = annual_stats["income"] / divisor
    annual_stats["avg_expenses"] = annual_stats["expenses"] / divisor
    annual_stats["avg_fixed"] = annual_stats["fixed_total"] / divisor
    annual_stats["avg_variable"] = annual_stats["variable_total"] / divisor
    annual_stats["avg_savings"] = annual_stats["savings"] / divisor

    annual_stats["avg_savings_rate"] = (
        (annual_stats["savings"] / annual_stats["income"] * 100) 
        if annual_stats["income"] > 0 else 0
    )


    total_expenses_year = annual_stats["expenses"]
    detailed_categories = []
    for cat_name in sorted(list(all_categories)):
        cat_monthly_series = []
        total_ytd = 0
        
        for m in monthly_data:
            val = m["categories"].get(cat_name, 0)
            total_ytd += val
            cat_monthly_series.append(val)
        
        # Calculamos el peso de esta categoría en el año
        weight = (total_ytd / total_expenses_year * 100) if total_expenses_year > 0 else 0
        monthly_avg = total_ytd / active_months

        detailed_categories.append({
            "name": cat_name,
            "monthly_data": cat_monthly_series,
            "total_ytd": total_ytd,
            "weight": weight,
            "monthly_avg": monthly_avg, 
        })

    return {
        "year": year,
        "monthly_data": monthly_data,
        "annual_stats": annual_stats,
        "month_names": month_names, # <--- Ahora disponible para el template
        "detailed_categories": detailed_categories, 
        "active_months": active_months_count,
        'annual_savings_rule_labels': ['Savings', 'Fixed', 'Variable'],
        'annual_savings_rule_data': [
            max(0, float(annual_stats["savings"])), 
            float(annual_stats["fixed_total"]), 
            float(annual_stats["variable_total"])
        ]
    }

# 2 REPORTE INVERSIONES (Rendimiento)
def get_investment_annual_report(user, year):
    # monthly_data ahora solo contiene los meses pasados/con actividad
    monthly_data = get_annual_portfolio_evolution(user, year)
    detailed_data = get_investment_detailed_evolution(user, year) 
    
    if not monthly_data:
        return {"year": year, "monthly_data": [], "annual_stats": None}

    last_month = monthly_data[-1]
    active_months_count = len(monthly_data) 
    
    total_contributions = sum(m.get("contributions", 0) for m in monthly_data)
    total_profit = sum(m.get("profit_loss", 0) for m in monthly_data)
    final_invested = last_month.get("invested", 0)
    annual_roi = (total_profit / final_invested * 100) if final_invested > 0 else 0
    
    annual_stats = {
        "total_contributions": total_contributions,
        "total_profit": total_profit,
        "total_profit_abs": abs(total_profit),
        "final_market_value": last_month.get("market_value", 0),
        "annual_roi": annual_roi,
        "annual_roi_abs": abs(annual_roi),
        "avg_profit_subtitle": f"{(total_profit / active_months_count):,.0f} €/mes",
        "avg_contribution_subtitle": f"{(total_contributions / active_months_count):,.0f} €/mes",
        "profit_status": "success" if total_profit >= 0 else "danger",
        "roi_status": "success" if annual_roi >= 0 else "danger",
        "profit_icon": "bi-graph-up-arrow" if total_profit >= 0 else "bi-graph-down-arrow",
        "roi_icon": "bi-trophy" if annual_roi >= 0 else "bi-exclamation-triangle",
        "profit_prefix": "+" if total_profit > 0 else ("-" if total_profit < 0 else ""),
        "roi_prefix": "+" if annual_roi > 0 else ("-" if annual_roi < 0 else ""),   
    }
    
    return {
        "year": year,
        "monthly_data": monthly_data,
        "annual_stats": annual_stats,
        "detailed_assets": detailed_data["assets"],
        "month_names": detailed_data["month_names"]
    }


# 3. REPORTE HOLDINGS (Saldos en cuenta)
def get_holdings_annual_report(user, year):
    # report_data ahora ya viene con las listas (matrix, month_names, etc.) 
    # recortadas dinámicamente según el mes actual o el año.
    report_data = get_annual_balance_evolution(user, year)
    
    # 1. Etiquetas de meses: simplemente mapeamos lo que viene de la API
    # Si estamos en Enero, month_names solo tiene 1 elemento, labels tendrá 1 elemento.
    labels = [m.strftime("%b %y") for m in report_data['month_names']]
    
    # 2. Datasets para la gráfica
    # Al estar report_data['matrix'] ya recortado, la gráfica no mostrará meses vacíos.
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
        # Importante: enviamos report_data como monthly_data para que el template 
        # encuentre las llaves que espera (matrix, monthly_totals, etc.)
        "monthly_data": report_data 
    }