from calendar import month_name
from django.utils import timezone
from . import queries, metrics
from holdings.services import api as holdings_api

def get_summary_page_data(user, year, month):
    """
    Orchestrator that collects all the necessary information for the summary page
    """
    base_qs = queries.get_base_transaction_qs(user)
    period_qs = base_qs.filter(date__year=year, date__month=month)
    
    # Search data
    years = queries.get_available_years(user)
    months_idx = queries.get_available_months_for_year(user, year)
    months_list = [(m, month_name[m]) for m in months_idx]
    
    # Calculations
    stats = metrics.get_period_metrics(period_qs)
    prev_income = metrics.get_previous_month_income(base_qs, year, month)
    exp_chart = metrics.get_expense_distribution_chart(period_qs)
    
    # KPI structure (Presentation logic moved here)
    kpis = [
        {'label': 'Net Savings', 'value': stats["savings"], 'class': 'soft-primary'},
        {'label': 'Total Income', 'value': stats["income"], 'class': 'soft-success'},
        {'label': 'Total Expenses', 'value': stats["expenses"], 'class': 'soft-danger'},
        {'label': 'Fixed Expenses', 'value': stats["fixed"], 'class': 'soft-secondary'},
        {'label': 'Variable Expenses', 'value': stats["variable"], 'class': 'soft-warning'},
        {'label': 'No Housing', 'value': stats["no_housing"], 'class': 'soft-info'},
    ]

    return {
        'transactions': period_qs.order_by('-date'),
        'years': years,
        'months': months_list,
        'sel_year': year,
        'sel_month': month,
        'prev_income': prev_income,
        'chart_labels': exp_chart["labels"],
        'chart_data': exp_chart["data"],
        'is_incomplete': stats["is_incomplete"],
        'savings_val': stats["savings"],
        'kpis': kpis,
        'savings_rule_labels': ['Savings', 'Fixed', 'Variable'],
        'savings_rule_data': [
            max(0, float(stats["savings"])), 
            float(stats["fixed"]), 
            float(stats["variable"])
        ]
    }

def get_emergency_fund_status(user):
    """
    Calculates the status of the emergency fund.
    Returns context data for the dashboard.
    """
    # 1. Get Target from Settings (default to 6 if not set)
    target_months = 6
    if hasattr(user, 'settings'):
        target_months = getattr(user.settings, 'emergency_fund_months', 6)

    # 2. Get Liquid Assets (Cash)
    total_cash, _ = holdings_api.get_current_value(user)

    # 3. Calculate Average Monthly Expenses (Year 2025)
    calc_year = 2025
    qs = queries.get_base_transaction_qs(user)
    period_qs = qs.filter(date__year=calc_year)
    
    stats = metrics.get_period_metrics(period_qs)
    avg_expenses = abs(float(stats.get("expenses", 0))) / 12.0

    months_covered = (total_cash / avg_expenses) if avg_expenses > 0 else 0
    progress = (months_covered / target_months * 100) if target_months > 0 else 0
    target_cash = avg_expenses * target_months

    return {
        "target_months": target_months,
        "months_covered": months_covered,
        "progress": min(progress, 100),
        "total_cash": total_cash,
        "target_cash": target_cash,
        "avg_expenses": avg_expenses,
        "is_ready": months_covered >= target_months,
        "calc_year": calc_year
    }