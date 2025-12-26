from calendar import month_name
from . import queries, metrics

def get_summary_page_data(user, year, month):
    """
    Orquestador que recolecta toda la información necesaria para la página de resumen.
    """
    base_qs = queries.get_base_transaction_qs(user)
    period_qs = base_qs.filter(date__year=year, date__month=month)
    
    # Datos de navegación
    years = queries.get_available_years(user)
    months_idx = queries.get_available_months_for_year(user, year)
    months_list = [(m, month_name[m]) for m in months_idx]
    
    # Cálculos
    stats = metrics.get_period_metrics(period_qs)
    prev_income = metrics.get_previous_month_income(base_qs, year, month)
    exp_chart = metrics.get_expense_distribution_chart(period_qs)
    
    # Estructura de KPIs (Lógica de presentación movida aquí)
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