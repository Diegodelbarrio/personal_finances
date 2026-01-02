# finances/services/api.py
from . import queries, metrics # Importamos tus utilidades internas existentes
from datetime import date
from django.utils import timezone

from django.db.models import Max, Min
from django.utils import timezone
from datetime import date
from . import queries, metrics

def get_annual_cashflow_summary(user, year):
    """
    Devuelve el desglose de ingresos, gastos y ahorro mes a mes,
    ajustando el rango de meses según la actividad real y proyecciones.
    """
    now = timezone.now().date()
    base_qs = queries.get_base_transaction_qs(user)
    
    # 1. Buscamos los límites de la historia del usuario
    # ¿Cuándo fue su primera transacción y cuándo es la última (incluyendo futuras)?
    activity_limits = base_qs.aggregate(
        first_date=Min('date'),
        last_date=Max('date')
    )
    
    first_date = activity_limits['first_date']
    last_date = activity_limits['last_date']

    # 2. Definir el mes de INICIO para el año consultado
    if first_date and year == first_date.year:
        start_month = first_date.month
    elif first_date and year < first_date.year:
        return [] # El año es anterior a que el usuario empezara
    else:
        start_month = 1 # Año posterior al inicio, empezamos en Enero

    # 3. Definir el mes de FIN para el año consultado
    if year < now.year:
        end_month = 12 # Años pasados se muestran completos
    elif year == now.year:
        # En el año actual, mostramos hasta "Hoy" o hasta la última transacción futura
        last_month_with_data = last_date.month if (last_date and last_date.year == year) else 0
        end_month = max(now.month, last_month_with_data)
    else:
        # Para años futuros, solo mostramos si hay transacciones planificadas
        if last_date and year == last_date.year:
            end_month = last_date.month
        else:
            return [] # Año futuro sin transacciones

    # 4. Generar los datos para el rango calculado
    months = range(start_month, end_month + 1)
    monthly_data = []
    
    for month in months:
        period_qs = base_qs.filter(date__year=year, date__month=month)
        stats = metrics.get_period_metrics(period_qs)
        
        # Calcular tasa de ahorro
        savings_rate = (stats["savings"] / stats["income"] * 100) if stats["income"] > 0 else 0

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