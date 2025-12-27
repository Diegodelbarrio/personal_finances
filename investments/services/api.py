from django.db.models import Sum
from investments.models import Asset, Transaction

EXCLUDE_ASSET_NAME = "Family Investments"


def get_portfolio_overview(user):
    assets = Asset.objects.filter(user=user)

    portfolio = []
    global_invested = 0
    global_current_value = 0
    last_market_dates = []

    temp = []

    for asset in assets:
        last_market_record = asset.history.order_by("-date").first()
        last_market_date = last_market_record.date if last_market_record else None

        if last_market_date:
            last_market_dates.append(last_market_date)

        tx_qs = asset.transactions.all()
        if last_market_date:
            tx_qs = tx_qs.filter(date__lte=last_market_date)

        invested = tx_qs.aggregate(total=Sum("amount"))["total"] or 0
        current_value = (
            last_market_record.total_value if last_market_record else invested
        )

        profit_loss = current_value - invested
        roi = (profit_loss / invested * 100) if invested != 0 else 0

        temp.append({
            "obj": asset,
            "invested": float(invested),
            "current_value": float(current_value),
            "profit_loss": float(profit_loss),
            "roi": float(roi),
        })

        global_invested += float(invested)
        global_current_value += float(current_value)

    # Allocation %
    for item in temp:
        allocation = (
            item["current_value"] / global_current_value * 100
            if global_current_value > 0 else 0
        )
        item["allocation_display"] = round(allocation, 1)
        item["allocation_css"] = f"{round(allocation, 0)}%"
        portfolio.append(item)

    # Excluding Family Investments
    no_family = [p for p in temp if p["obj"].name != EXCLUDE_ASSET_NAME]

    no_family_invested = sum(p["invested"] for p in no_family)
    no_family_value = sum(p["current_value"] for p in no_family)
    no_family_profit_loss = no_family_value - no_family_invested
    no_family_roi = (
        no_family_profit_loss / no_family_invested * 100
        if no_family_invested != 0 else 0
    )

    return {
        "portfolio": portfolio,
        "global_invested": global_invested,
        "global_current_value": global_current_value,
        "global_profit_loss": global_current_value - global_invested,
        "global_roi": (
            (global_current_value - global_invested) / global_invested * 100
            if global_invested != 0 else 0
        ),
        "no_family_invested": no_family_invested,
        "no_family_value": no_family_value,
        "no_family_profit_loss": no_family_profit_loss,
        "no_family_roi": no_family_roi,
        "last_market_date": min(last_market_dates) if last_market_dates else None,
        "chart_assets": no_family,
    }


from calendar import monthrange
from datetime import date
from django.db.models import Sum
from ..models import Asset 

def _get_last_day_of_month(year, month):
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)

def get_annual_portfolio_evolution(user, year):
    assets = Asset.objects.filter(user=user)
    monthly_data = []
    EXCLUDE_NAME = "Family Investments"

    # Variable para arrastrar el valor del mes anterior
    previous_market_value = 0.0

    for month in range(1, 13):
        cutoff_date = _get_last_day_of_month(year, month)
        
        monthly_stats = {
            "month": month,
            "date_obj": date(year, month, 1),
            "invested": 0.0,
            "market_value": 0.0,
            "contributions": 0.0,
            "profit_loss": 0.0,
            "roi": 0.0
        }

        for asset in assets:
            if asset.name == EXCLUDE_NAME:
                continue

            # 1. Invertido ACUMULADO hasta hoy
            invested = asset.transactions.filter(
                date__lte=cutoff_date
            ).aggregate(t=Sum("amount"))["t"] or 0

            # 2. Aportaciones del mes
            month_contrib = asset.transactions.filter(
                date__year=year, 
                date__month=month
            ).aggregate(t=Sum("amount"))["t"] or 0

            # 3. Valor de mercado fin de mes
            history = asset.history.filter(
                date__lte=cutoff_date
            ).order_by('-date').first()
            
            market_val = history.total_value if history else invested

            monthly_stats["invested"] += float(invested)
            monthly_stats["market_value"] += float(market_val)
            monthly_stats["contributions"] += float(month_contrib)

        # --- CÁLCULO CORREGIDO DE PROFIT/LOSS MENSUAL ---
        # Formula: MV(actual) - MV(anterior) - Aportaciones(mes)
        if month == 1:
            # Para enero, el MV anterior es el MV del 31 de diciembre del año pasado
            last_day_prev_year = date(year - 1, 12, 31)
            # Reutilizamos lógica para buscar el valor de cierre del año pasado
            prev_mv_total = 0
            for asset in assets:
                if asset.name == EXCLUDE_NAME: continue
                h = asset.history.filter(date__lte=last_day_prev_year).order_by('-date').first()
                prev_mv_total += float(h.total_value if h else 0)
            previous_market_value = prev_mv_total

        monthly_stats["profit_loss"] = (
            monthly_stats["market_value"] - previous_market_value - monthly_stats["contributions"]
        )

        # ROI mensual: (Beneficio del mes / Valor al inicio del mes + aportaciones)
        # Una forma simple es: beneficio / valor anterior (si valor anterior > 0)
        divisor = previous_market_value + monthly_stats["contributions"]
        if divisor > 0:
            monthly_stats["roi"] = (monthly_stats["profit_loss"] / divisor) * 100

        # Actualizamos para el siguiente mes
        previous_market_value = monthly_stats["market_value"]

        monthly_data.append(monthly_stats)

    return monthly_data