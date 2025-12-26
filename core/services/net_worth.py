from datetime import timedelta
from django.utils import timezone

from holdings.services.api import get_current_value as get_holdings_value
from investments.services.api import get_portfolio_overview


def calculate_net_worth(user):
    """
    Calcula el patrimonio total actual y el estado de actualización de los datos.
    """

    # A. Cash (holdings)
    holdings_value, holdings_dates = get_holdings_value(user)

    # B. Investments
    investments_data = get_portfolio_overview(user)
    investments_value = investments_data["global_current_value"]
    investments_date = investments_data["last_market_date"]

    snapshot_dates = []
    if holdings_dates:
        snapshot_dates.extend(holdings_dates)
    if investments_date:
        snapshot_dates.append(investments_date)

    current_net_worth = holdings_value + investments_value

    # Fecha de referencia (la más antigua)
    last_market_date = min(snapshot_dates) if snapshot_dates else None

    # Indicador de desactualización
    is_stale = False
    if last_market_date:
        if last_market_date < (timezone.now().date() - timedelta(days=30)):
            is_stale = True

    return {
        "current_net_worth": current_net_worth,
        "last_market_date": last_market_date,
        "is_stale": is_stale,
    }
