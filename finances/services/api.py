# finances/services/api.py
from . import queries, metrics # Importamos tus utilidades internas existentes
from datetime import date

def get_annual_cashflow_summary(user, year):
    """
    Devuelve el desglose de ingresos, gastos y ahorro mes a mes.
    """
    monthly_data = []
    
    for month in range(1, 13):
        base_qs = queries.get_base_transaction_qs(user)
        period_qs = base_qs.filter(date__year=year, date__month=month)
        
        stats = metrics.get_period_metrics(period_qs)
        
        # Calcular tasa de ahorro
        savings_rate = 0
        if stats["income"] > 0:
            savings_rate = (stats["savings"] / stats["income"]) * 100

        monthly_data.append({
            "month": month,
            "date_obj": date(year, month, 1),
            "income": stats["income"],
            "expenses": stats["expenses"],
            "fixed": stats["fixed"],
            "variable": stats["variable"],
            "savings": stats["savings"],
            "savings_rate": savings_rate
        })
        
    return monthly_data

def get_available_transaction_years(user):
    """Exponemos la lista de años disponibles"""
    return queries.get_available_years(user)