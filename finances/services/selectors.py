from calendar import month_name
from datetime import date

from django.utils import timezone

from finances.models import Category
from . import queries, metrics
from holdings.services import api as holdings_api


def get_summary_page_data(user, year, month):
    """
    Orchestrator that collects all the necessary information for the summary page
    """
    base_qs = queries.get_base_transaction_qs(user)
    period_qs = base_qs.filter(date__year=year, date__month=month)
    
    # Search data
    years = list(queries.get_available_years(user))
    if year not in years:
        years.insert(0, year)
    months_list = [(m, month_name[m]) for m in range(1, 13)]
    
    # Calculations
    stats = metrics.get_period_metrics(period_qs)
    prev_income = metrics.get_previous_month_income(base_qs, year, month)
    exp_chart = metrics.get_expense_distribution_chart(period_qs)
    transactions = list(period_qs.order_by('-date'))
    
    # KPI structure (Presentation logic moved here)
    kpis = [
        {'label': 'Net Savings', 'value': stats["savings"], 'class': 'soft-primary'},
        {'label': 'Total Income', 'value': stats["income"], 'class': 'soft-success'},
        {'label': 'Total Expenses', 'value': stats["expenses"], 'class': 'soft-danger'},
        {'label': 'Fixed Expenses', 'value': stats["fixed"], 'class': 'soft-secondary'},
        {'label': 'Variable Expenses', 'value': stats["variable"], 'class': 'soft-warning'},
        {'label': 'No Housing', 'value': stats["no_housing"], 'class': 'soft-info'},
        {'label': 'Needs', 'value': stats["needs"], 'class': 'soft-secondary'},
        {'label': 'Wants', 'value': stats["wants"], 'class': 'soft-warning'},
        {'label': '50-30-20 Savings', 'value': stats["rule_savings"], 'class': 'soft-primary'},
    ]

    return {
        'transactions': transactions,
        'years': years,
        'months': months_list,
        'selected_month_name': month_name[month],
        'transaction_count': len(transactions),
        'sel_year': year,
        'sel_month': month,
        'prev_income': prev_income,
        'chart_labels': exp_chart["labels"],
        'chart_data': exp_chart["data"],
        'is_incomplete': stats["is_incomplete"],
        'savings_val': stats["savings"],
        'budget_alerts': stats["budget_alerts"],
        'budget_rule': {
            'needs': stats["needs"],
            'wants': stats["wants"],
            'savings': stats["rule_savings"],
            'needs_pct': stats["needs_pct"],
            'wants_pct': stats["wants_pct"],
            'savings_pct': stats["savings_pct"],
            'needs_target': stats["needs_target"],
            'wants_target': stats["wants_target"],
            'savings_target': stats["savings_target"],
        },
        'kpis': kpis,
        'savings_rule_labels': ['Needs', 'Wants', 'Savings'],
        'savings_rule_data': [
            float(stats["needs"]),
            float(stats["wants"]),
            float(stats["rule_savings"]),
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

    # 3. Calculate a rolling average from the current and previous 11 months.
    # Divide by months that actually contain expense data so a partially
    # onboarded user is not presented with an artificially low average.
    today = timezone.localdate()
    start_month_index = (today.year * 12 + today.month - 1) - 11
    start_year, zero_based_month = divmod(start_month_index, 12)
    start_date = date(start_year, zero_based_month + 1, 1)

    qs = queries.get_base_transaction_qs(user)
    period_qs = qs.filter(date__gte=start_date, date__lte=today)
    stats = metrics.get_period_metrics(period_qs)
    expense_months = (
        period_qs.filter(
            subcategory__parent_category__transaction_type=Category.TransactionType.EXPENSE
        )
        .dates("date", "month")
        .count()
    )
    avg_expenses = (
        abs(float(stats.get("expenses", 0))) / expense_months
        if expense_months
        else 0.0
    )

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
        "calc_period_label": f"{start_date:%b %Y}–{today:%b %Y}",
        "months_used": expense_months,
    }
