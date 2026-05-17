from datetime import timedelta
from django.utils import timezone

from holdings.services.api import get_current_value as get_holdings_value
from investments.services.api import get_portfolio_overview


def calculate_net_worth(user):
    """
    Calculate the current total assets and the data update status..
    """

    # A. Cash (holdings)
    holdings_value, holdings_dates = get_holdings_value(user, dates_only_active=True)

    # B. Investments
    investments_data = get_portfolio_overview(user)
    investments_value = investments_data["global_current_value"]
    investments_min_date = investments_data.get("last_market_date")
    investments_max_date = investments_data.get("latest_market_date")

    snapshot_dates = []
    if holdings_dates:
        snapshot_dates.extend(holdings_dates)
    
    # Añadimos los extremos de inversiones para evaluar el rango completo
    if investments_min_date:
        snapshot_dates.append(investments_min_date)
    if investments_max_date:
        snapshot_dates.append(investments_max_date)

    current_net_worth = holdings_value + investments_value

    # Evaluamos el estado de los datos
    data_status = "ok"  # Posibles valores: 'ok', 'warning', 'danger'
    last_market_date = None

    if snapshot_dates:
        min_date = min(snapshot_dates)
        max_date = max(snapshot_dates)
        now = timezone.now().date()
        last_market_date = min_date

        # 1. Criterio clásico: Datos demasiado antiguos (> 30 días)
        if min_date < (now - timedelta(days=30)):
            data_status = "danger"
        # 2. Criterio de consistencia: Actualización parcial del mes
        # Si ya hay datos de este mes (max es actual) pero quedan datos viejos (min no es actual)
        elif max_date.month == now.month and max_date.year == now.year:
            if min_date.month != now.month or min_date.year != now.year:
                data_status = "warning"

    return {
        "current_net_worth": current_net_worth,
        "holdings_value": holdings_value,
        "holdings_dates": holdings_dates,
        "last_market_date": last_market_date,
        "data_status": data_status,
    }
