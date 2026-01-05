from calendar import monthrange
from datetime import date
from django.db.models import Sum, Min, Max
from django.utils import timezone
from ..models import Asset, Transaction

EXCLUDE_ASSET_NAME = "Family Investments"

def _get_last_day_of_month(year, month):
    """Utility to obtain the last day of the month."""
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)

def get_portfolio_overview(user):
    """Current portfolio summary (Holdings)."""
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
        current_value = (last_market_record.total_value if last_market_record else invested)

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

    for item in temp:
        allocation = (item["current_value"] / global_current_value * 100 if global_current_value > 0 else 0)
        item["allocation_display"] = round(allocation, 1)
        item["allocation_css"] = f"{round(allocation, 0)}%"
        portfolio.append(item)

    no_family = [p for p in temp if p["obj"].name != EXCLUDE_ASSET_NAME]
    no_family_invested = sum(p["invested"] for p in no_family)
    no_family_value = sum(p["current_value"] for p in no_family)

    return {
        "portfolio": portfolio,
        "global_invested": global_invested,
        "global_current_value": global_current_value,
        "global_profit_loss": global_current_value - global_invested,
        "global_roi": ((global_current_value - global_invested) / global_invested * 100 if global_invested != 0 else 0),
        "no_family_invested": no_family_invested,
        "no_family_value": no_family_value,
        "no_family_profit_loss": no_family_value - no_family_invested,
        "no_family_roi": ((no_family_value - no_family_invested) / no_family_invested * 100 if no_family_invested != 0 else 0),
        "last_market_date": min(last_market_dates) if last_market_dates else None,
        "latest_market_date": max(last_market_dates) if last_market_dates else None,
        "chart_assets": no_family,
    }

def get_annual_portfolio_evolution(user, year):
    """Monthly global performance (Invested vs Market) for the graph and summary table."""
    assets = Asset.objects.filter(user=user)
    now = timezone.now().date()
    
    first_tx = Transaction.objects.filter(asset__user=user).order_by('date').first()
    if not first_tx or year < first_tx.date.year or year > now.year:
        months = range(1, now.month + 1) if year == now.year else []
    else:
        start_month = first_tx.date.month if year == first_tx.date.year else 1
        end_month = now.month if year == now.year else 12
        months = range(start_month, end_month + 1)

    if not months: return []

    # Valor inicial previo al periodo
    day_before_start = date(year, list(months)[0], 1) - timezone.timedelta(days=1)
    previous_market_value = 0.0
    for asset in assets:
        if asset.name == EXCLUDE_ASSET_NAME: continue
        h = asset.history.filter(date__lte=day_before_start).order_by('-date').first()
        previous_market_value += float(h.total_value if h else 0)

    monthly_data = []
    for month in months:
        cutoff_date = _get_last_day_of_month(year, month)
        monthly_stats = {"month": month, "date_obj": date(year, month, 1), "invested": 0.0, "market_value": 0.0, "contributions": 0.0, "profit_loss": 0.0, "roi": 0.0}

        for asset in assets:
            if asset.name == EXCLUDE_ASSET_NAME: continue
            invested = asset.transactions.filter(date__lte=cutoff_date).aggregate(t=Sum("amount"))["t"] or 0
            contrib = asset.transactions.filter(date__year=year, date__month=month).aggregate(t=Sum("amount"))["t"] or 0
            history = asset.history.filter(date__lte=cutoff_date).order_by('-date').first()
            market_val = history.total_value if history else invested

            monthly_stats["invested"] += float(invested)
            monthly_stats["market_value"] += float(market_val)
            monthly_stats["contributions"] += float(contrib)

        monthly_stats["profit_loss"] = monthly_stats["market_value"] - previous_market_value - monthly_stats["contributions"]
        divisor = previous_market_value + monthly_stats["contributions"]
        if divisor > 0:
            monthly_stats["roi"] = (monthly_stats["profit_loss"] / divisor) * 100

        previous_market_value = monthly_stats["market_value"]
        monthly_data.append(monthly_stats)

    return monthly_data

def get_investment_detailed_evolution(user, year):
    """Breakdown by asset for the detailed performance table."""
    assets = Asset.objects.filter(user=user).exclude(name=EXCLUDE_ASSET_NAME)
    now = timezone.now().date()
    
    first_tx = Transaction.objects.filter(asset__user=user).order_by('date').first()
    if not first_tx or year < first_tx.date.year or year > now.year:
        months_range = range(1, now.month + 1) if year == now.year else []
    else:
        start_month = first_tx.date.month if year == first_tx.date.year else 1
        end_month = now.month if year == now.year else 12
        months_range = range(start_month, end_month + 1)

    asset_matrix = []
    for asset in assets:
        asset_row = {"name": asset.name, "monthly_data": [], "annual_profit": 0.0, "annual_contributions": 0.0, "annual_roi": 0.0}
        
        # Valor inicial al empezar el año/periodo
        first_m = list(months_range)[0] if months_range else 1
        day_before = date(year, first_m, 1) - timezone.timedelta(days=1)
        h_prev = asset.history.filter(date__lte=day_before).order_by('-date').first()
        prev_mv = float(h_prev.total_value if h_prev else 0)
        initial_year_value = prev_mv

        for month in months_range:
            cutoff = _get_last_day_of_month(year, month)
            contrib = float(asset.transactions.filter(date__year=year, date__month=month).aggregate(t=Sum("amount"))["t"] or 0)
            h_current = asset.history.filter(date__lte=cutoff).order_by('-date').first()
            current_mv = float(h_current.total_value if h_current else (asset.transactions.filter(date__lte=cutoff).aggregate(t=Sum("amount"))["t"] or 0))

            profit = current_mv - prev_mv - contrib
            roi = (profit / (prev_mv + contrib) * 100) if (prev_mv + contrib) > 0 else 0
            
            asset_row["monthly_data"].append({"profit": profit, "roi": roi})
            asset_row["annual_profit"] += profit
            asset_row["annual_contributions"] += contrib
            prev_mv = current_mv

        # Cálculo de ROI anual
        investment_base = initial_year_value + asset_row["annual_contributions"]
        if investment_base > 0:
            asset_row["annual_roi"] = (asset_row["annual_profit"] / investment_base) * 100
        
        asset_matrix.append(asset_row)

    return {
        "assets": asset_matrix,
        "month_names": [date(year, m, 1) for m in months_range]
    }

def get_family_investment_performance(user, year):
    """Calculates annual performance for the excluded Family Investments asset."""
    try:
        asset = Asset.objects.get(user=user, name=EXCLUDE_ASSET_NAME)
    except Asset.DoesNotExist:
        return None

    now = timezone.now().date()
    
    if year > now.year:
        return None
        
    if year == now.year:
        cutoff_date = now
    else:
        cutoff_date = date(year, 12, 31)

    # Value at start of year (end of previous year)
    start_of_year = date(year, 1, 1)
    day_before_start = start_of_year - timezone.timedelta(days=1)
    
    h_prev = asset.history.filter(date__lte=day_before_start).order_by('-date').first()
    prev_mv = float(h_prev.total_value if h_prev else 0)

    # Contributions in the year
    contrib = asset.transactions.filter(date__year=year, date__lte=cutoff_date).aggregate(t=Sum("amount"))["t"] or 0
    contrib = float(contrib)

    # Value at end of period
    h_curr = asset.history.filter(date__lte=cutoff_date).order_by('-date').first()
    
    if h_curr:
        current_mv = float(h_curr.total_value)
    else:
        invested_total = asset.transactions.filter(date__lte=cutoff_date).aggregate(t=Sum("amount"))["t"] or 0
        current_mv = float(invested_total)

    profit = current_mv - prev_mv - contrib
    invested_base = prev_mv + contrib
    
    roi = (profit / invested_base * 100) if invested_base > 0 else 0

    return {
        "name": asset.name,
        "current_value": current_mv,
        "profit": profit,
        "roi": roi,
        "profit_status": "success" if profit >= 0 else "danger",
        "roi_status": "success" if roi >= 0 else "danger",
        "profit_prefix": "+" if profit > 0 else ("" if profit < 0 else ""),
        "roi_prefix": "+" if roi > 0 else ("" if roi < 0 else ""),
        "roi_icon": "bi-graph-up-arrow" if roi >= 0 else "bi-graph-down-arrow",
    }