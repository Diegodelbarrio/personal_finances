# reports/services.py

from calendar import monthrange
from datetime import date
from finances.services.api import get_annual_cashflow_summary, get_available_transaction_years
from investments.services.api import (
    get_annual_portfolio_evolution,
    get_investment_detailed_evolution,
    get_family_investment_performance,
    get_money_weighted_return,
)
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

    # 1. Identificar todas las categorías y sus subcategorías
    expense_map = {}
    income_map = {}

    for m in monthly_data:
        # EXPENSES
        for cat_name, subs in m.get("subcategories", {}).items():
            if cat_name not in expense_map: expense_map[cat_name] = set()
            expense_map[cat_name].update(subs.keys())
        for cat_name in m["categories"].keys():
            if cat_name not in expense_map: expense_map[cat_name] = set()
            
        # INCOME
        for cat_name, subs in m.get("income_subcategories", {}).items():
            if cat_name not in income_map: income_map[cat_name] = set()
            income_map[cat_name].update(subs.keys())
        for cat_name in m.get("income_categories", {}).keys():
            if cat_name not in income_map: income_map[cat_name] = set()
    
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
    total_income_year = annual_stats["income"]
    detailed_categories = []
    detailed_income = []

    # --- PROCESAR GASTOS (EXPENSES) ---
    for cat_name in sorted(expense_map.keys()):
        cat_monthly_series = []
        total_ytd = 0
        
        subs_list = []
        for sub_name in sorted(list(expense_map[cat_name])):
            sub_monthly_series = []
            sub_total_ytd = 0
            
            # Accumulator for trips (Travel subcategory)
            trip_accumulator = {}

            for m in monthly_data:
                val = m.get("subcategories", {}).get(cat_name, {}).get(sub_name, 0)
                sub_total_ytd += val
                sub_monthly_series.append(val)
                
                if sub_name == "Travel":
                    t_data = m.get("travel_breakdown", {})
                    for loc, amount in t_data.items():
                        trip_accumulator[loc] = trip_accumulator.get(loc, 0) + amount
            
            trips = []
            if sub_name == "Travel" and trip_accumulator:
                for loc, amount in trip_accumulator.items():
                    trips.append({'name': loc, 'total': abs(amount)})
                trips.sort(key=lambda x: x['total'], reverse=True)

            subs_list.append({
                "name": sub_name,
                "monthly_data": sub_monthly_series,
                "total_ytd": sub_total_ytd,
                "monthly_avg": sub_total_ytd / active_months if active_months > 0 else 0,
                "trips": trips
            })

        for m in monthly_data:
            val = m["categories"].get(cat_name, 0)
            total_ytd += val
            cat_monthly_series.append(val)
        
        monthly_avg = total_ytd / active_months

        weight = (total_ytd / total_expenses_year * 100) if total_expenses_year > 0 else 0
        detailed_categories.append({
            "name": cat_name,
            "monthly_data": cat_monthly_series,
            "total_ytd": total_ytd,
            "weight": weight,
            "monthly_avg": monthly_avg, 
            "subcategories": subs_list,
        })

    # --- PROCESAR INGRESOS (INCOME) ---
    for cat_name in sorted(income_map.keys()):
        cat_monthly_series = []
        total_ytd = 0
        
        subs_list = []
        for sub_name in sorted(list(income_map[cat_name])):
            sub_monthly_series = []
            sub_total_ytd = 0
            for m in monthly_data:
                val = m.get("income_subcategories", {}).get(cat_name, {}).get(sub_name, 0)
                sub_total_ytd += val
                sub_monthly_series.append(val)
            
            subs_list.append({
                "name": sub_name,
                "monthly_data": sub_monthly_series,
                "total_ytd": sub_total_ytd,
                "monthly_avg": sub_total_ytd / active_months if active_months > 0 else 0,
            })

        for m in monthly_data:
            val = m.get("income_categories", {}).get(cat_name, 0)
            total_ytd += val
            cat_monthly_series.append(val)
        
        monthly_avg = total_ytd / active_months
        weight = (total_ytd / total_income_year * 100) if total_income_year > 0 else 0
        
        detailed_income.append({
            "name": cat_name,
            "monthly_data": cat_monthly_series,
            "total_ytd": total_ytd,
            "weight": weight,
            "monthly_avg": monthly_avg, 
            "subcategories": subs_list,
        })

    return {
        "year": year,
        "monthly_data": monthly_data,
        "annual_stats": annual_stats,
        "month_names": month_names, 
        "detailed_categories": detailed_categories, 
        "detailed_income": detailed_income,
        "active_months": active_months_count,
        'annual_savings_rule_labels': ['Savings', 'Fixed', 'Variable'],
        'annual_savings_rule_data': [
            max(0, float(annual_stats["savings"])), 
            float(annual_stats["fixed_total"]), 
            float(annual_stats["variable_total"])
        ],
        "annual_category_labels": [c["name"] for c in detailed_categories if c["total_ytd"] != 0],
        "annual_category_data": [abs(float(c["total_ytd"])) for c in detailed_categories if c["total_ytd"] != 0],
    }

# 2 REPORTE INVERSIONES (Rendimiento)
def get_investment_annual_report(user, year):
    # monthly_data ahora solo contiene los meses pasados/con actividad
    monthly_data = get_annual_portfolio_evolution(user, year)
    detailed_data = get_investment_detailed_evolution(user, year) 
    
    if not monthly_data:
        return {"year": year, "monthly_data": [], "annual_stats": None}

    first_month = monthly_data[0]
    last_month = monthly_data[-1]
    active_months_count = len(monthly_data) 
    
    total_contributions = sum(m.get("contributions", 0) for m in monthly_data)
    total_profit = sum(m.get("profit_loss", 0) for m in monthly_data)
    
    # Para que el ROI anual coincida con la lógica de rendimiento real, 
    # calculamos sobre el capital neto invertido (Cost Basis).
    # Si estamos en el primer mes, esto alineará el KPI con la fila de la tabla.
    current_market_value = last_month.get("market_value", 0)
    cost_basis = current_market_value - total_profit
    annual_roi = (total_profit / cost_basis * 100) if cost_basis > 0 else 0

    start_value = (
        first_month.get("market_value", 0)
        - first_month.get("profit_loss", 0)
        - first_month.get("contributions", 0)
    )
    _, last_day = monthrange(year, last_month["month"])
    period_start = date(year, first_month["month"], 1)
    period_end = date(year, last_month["month"], last_day)
    mwrr = get_money_weighted_return(
        user=user,
        start_date=period_start,
        end_date=period_end,
        start_value=start_value,
        end_value=current_market_value,
    )

    if mwrr is None:
        mwrr_display = "N/A"
        mwrr_suffix = ""
        mwrr_prefix = ""
        mwrr_status = "secondary"
        mwrr_icon = "bi-dash-circle"
    else:
        mwrr_display = f"{abs(mwrr) * 100:.2f}"
        mwrr_suffix = " %"
        mwrr_prefix = "+" if mwrr > 0 else ("" if mwrr < 0 else "")
        mwrr_status = "success" if mwrr >= 0 else "danger"
        mwrr_icon = "bi-percent"
    
    annual_stats = {
        "total_contributions": total_contributions,
        "total_profit": total_profit,
        "total_profit_abs": abs(total_profit),
        "final_market_value": last_month.get("market_value", 0),
        "annual_roi": annual_roi,
        "annual_roi_abs": abs(annual_roi),
        "mwrr": mwrr,
        "mwrr_display": mwrr_display,
        "mwrr_suffix": mwrr_suffix,
        "mwrr_prefix": mwrr_prefix,
        "mwrr_status": mwrr_status,
        "mwrr_icon": mwrr_icon,
        "avg_profit_subtitle": f"{(total_profit / active_months_count):,.0f} €/mes",
        "avg_contribution_subtitle": f"{(total_contributions / active_months_count):,.0f} €/mes",
        "profit_status": "success" if total_profit >= 0 else "danger",
        "roi_status": "success" if annual_roi >= 0 else "danger",
        "profit_icon": "bi-graph-up-arrow" if total_profit >= 0 else "bi-graph-down-arrow",
        "roi_icon": "bi-trophy" if annual_roi >= 0 else "bi-exclamation-triangle",
        "profit_prefix": "+" if total_profit > 0 else ("" if total_profit < 0 else ""),
        "roi_prefix": "+" if annual_roi > 0 else ("" if annual_roi < 0 else ""),   
    }

    performance_chart_data = []
    for m in monthly_data:
        performance_chart_data.append({
            "label": m["date_obj"].strftime("%b"),
            "market": m["market_value"],
            "invested": m["invested"]
        })

    family_stats = get_family_investment_performance(user, year)
    
    return {
        "year": year,
        "monthly_data": monthly_data,
        "annual_stats": annual_stats,
        "performance_chart_data": performance_chart_data,
        "family_stats": family_stats,
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
