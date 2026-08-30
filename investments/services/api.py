from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from math import isfinite
from django.utils import timezone
from ..models import Asset, AssetHistory, Transaction

def _xnpv(rate, cash_flows):
    if rate <= -0.999999:
        return float("inf")
    t0 = cash_flows[0][0]
    total = 0.0
    for flow_date, amount in cash_flows:
        days = (flow_date - t0).days
        total += amount / ((1 + rate) ** (days / 365.0))
    return total

def _xirr(cash_flows, tol=1e-7, max_iter=100):
    if not cash_flows:
        return None
    cash_flows = sorted(cash_flows, key=lambda x: x[0])
    has_pos = any(amount > 0 for _, amount in cash_flows)
    has_neg = any(amount < 0 for _, amount in cash_flows)
    if not (has_pos and has_neg):
        return None

    low = -0.9999
    high = 10.0
    f_low = _xnpv(low, cash_flows)
    f_high = _xnpv(high, cash_flows)

    attempts = 0
    while f_low * f_high > 0 and attempts < 20 and isfinite(f_high):
        high *= 2
        f_high = _xnpv(high, cash_flows)
        attempts += 1

    if f_low * f_high > 0:
        return None

    mid = None
    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = _xnpv(mid, cash_flows)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid < 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return mid

def get_money_weighted_return(user, start_date, end_date, start_value, end_value, asset=None, include_family=False):
    """
    Money-weighted return (IRR) for the period, including initial value,
    intermediate cash flows, and ending market value.
    """
    if start_date > end_date:
        return None

    cash_flows = []
    if start_value:
        cash_flows.append((start_date, -float(start_value)))

    txs = Transaction.objects.filter(
        asset__user=user,
        date__gte=start_date,
        date__lte=end_date,
    )
    if asset is not None:
        txs = txs.filter(asset=asset)
    elif not include_family:
        txs = txs.exclude(asset__exclude_from_totals=True)
    txs = txs.values("date", "action", "amount")
    for tx in txs:
        amount = float(tx["amount"] or 0)
        if amount == 0:
            continue
        sign = -1 if tx["action"] == "BUY" else 1
        cash_flows.append((tx["date"], sign * abs(amount)))

    if end_value:
        cash_flows.append((end_date, float(end_value)))

    return _xirr(cash_flows)

def _get_last_day_of_month(year, month):
    """Utility to obtain the last day of the month."""
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)

def get_portfolio_overview(user):
    """Current portfolio summary (Holdings)."""
    assets = list(Asset.objects.filter(user=user).order_by("id"))
    latest_history_by_asset = {}
    for record in (
        AssetHistory.objects.filter(asset__user=user)
        .order_by("asset_id", "-date", "-id")
        .values("asset_id", "date", "total_value")
    ):
        latest_history_by_asset.setdefault(record["asset_id"], record)

    transaction_records = list(
        Transaction.objects.filter(asset__user=user).values("asset_id", "date", "amount")
    )
    transactions_by_asset = defaultdict(list)
    for record in transaction_records:
        transactions_by_asset[record["asset_id"]].append(record)

    portfolio = []
    global_invested = 0
    global_current_value = 0
    last_market_dates = []
    temp = []

    for asset in assets:
        last_market_record = latest_history_by_asset.get(asset.id)
        last_market_date = last_market_record["date"] if last_market_record else None
        if last_market_date:
            last_market_dates.append(last_market_date)

        invested = sum(
            (
                record["amount"]
                for record in transactions_by_asset[asset.id]
                if last_market_date is None or record["date"] <= last_market_date
            ),
            Decimal("0"),
        )
        current_value = (
            last_market_record["total_value"] if last_market_record else invested
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

    for item in temp:
        allocation = (item["current_value"] / global_current_value * 100 if global_current_value > 0 else 0)
        item["allocation_display"] = round(allocation, 1)
        item["allocation_css"] = f"{round(allocation, 0)}%"
        portfolio.append(item)

    no_family = [p for p in temp if not p["obj"].exclude_from_totals]
    no_family_dates = [
        latest_history_by_asset[item["obj"].id]["date"]
        for item in no_family
        if item["obj"].id in latest_history_by_asset
    ]
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
        "personal_last_market_date": min(no_family_dates) if no_family_dates else None,
        "personal_latest_market_date": max(no_family_dates) if no_family_dates else None,
        "personal_asset_count": len(no_family),
        "chart_assets": no_family,
    }

def _build_annual_asset_series(user, year):
    """Build monthly asset series with three queries regardless of asset count."""
    assets = list(
        Asset.objects.filter(user=user, exclude_from_totals=False).order_by("name", "id")
    )
    if not assets:
        return {"months": [], "assets": []}

    asset_ids = [asset.id for asset in assets]
    transaction_records = list(
        Transaction.objects.filter(asset_id__in=asset_ids)
        .order_by("asset_id", "date", "id")
        .values("asset_id", "date", "id", "amount")
    )
    history_records = list(
        AssetHistory.objects.filter(asset_id__in=asset_ids)
        .order_by("asset_id", "date", "id")
        .values("asset_id", "date", "id", "total_value")
    )
    source_dates = [record["date"] for record in transaction_records + history_records]
    now = timezone.localdate()
    if not source_dates or year < min(source_dates).year or year > now.year:
        return {"months": [], "assets": []}

    first_source_date = min(source_dates)
    start_month = first_source_date.month if year == first_source_date.year else 1
    end_month = now.month if year == now.year else 12
    months = list(range(start_month, end_month + 1))
    if not months:
        return {"months": [], "assets": []}

    events_by_asset = defaultdict(list)
    for record in transaction_records:
        events_by_asset[record["asset_id"]].append(
            (record["date"], 0, record["id"], "transaction", record["amount"])
        )
    for record in history_records:
        events_by_asset[record["asset_id"]].append(
            (record["date"], 1, record["id"], "history", record["total_value"])
        )
    for events in events_by_asset.values():
        events.sort(key=lambda event: (event[0], event[1], event[2]))

    day_before_start = date(year, months[0], 1) - timezone.timedelta(days=1)
    asset_series = []
    for asset in assets:
        events = events_by_asset[asset.id]
        event_index = 0
        invested = Decimal("0")
        estimated_market = Decimal("0")
        has_history = False

        while event_index < len(events) and events[event_index][0] <= day_before_start:
            _event_date, _order, _event_id, event_type, value = events[event_index]
            if event_type == "transaction":
                invested += value
                estimated_market = estimated_market + value if has_history else invested
            else:
                estimated_market = value
                has_history = True
            event_index += 1

        previous_market = estimated_market
        initial_value = float(previous_market)
        monthly_values = []
        annual_profit = 0.0
        annual_contributions = 0.0

        for month in months:
            cutoff = _get_last_day_of_month(year, month)
            contributions = Decimal("0")
            had_value_before_month = has_history or invested != 0
            while event_index < len(events) and events[event_index][0] <= cutoff:
                _event_date, _order, _event_id, event_type, value = events[event_index]
                if event_type == "transaction":
                    invested += value
                    contributions += value
                    estimated_market = estimated_market + value if has_history else invested
                else:
                    estimated_market = value
                    has_history = True
                event_index += 1

            opening_value = Decimal("0")
            if not had_value_before_month and contributions == 0 and has_history:
                opening_value = estimated_market
                if initial_value == 0:
                    initial_value = float(opening_value)
            profit = estimated_market - previous_market - contributions - opening_value
            divisor = previous_market + contributions + opening_value
            roi = (profit / divisor * 100) if divisor > 0 else Decimal("0")
            month_data = {
                "invested": float(invested),
                "market_value": float(estimated_market),
                "contributions": float(contributions),
                "opening_value": float(opening_value),
                "profit": float(profit),
                "roi": float(roi),
            }
            monthly_values.append(month_data)
            annual_profit += month_data["profit"]
            annual_contributions += month_data["contributions"]
            previous_market = estimated_market

        investment_base = initial_value + annual_contributions
        asset_series.append(
            {
                "name": asset.name,
                "initial_value": initial_value,
                "monthly_values": monthly_values,
                "annual_profit": annual_profit,
                "annual_contributions": annual_contributions,
                "annual_roi": (
                    annual_profit / investment_base * 100 if investment_base > 0 else 0.0
                ),
            }
        )

    return {"months": months, "assets": asset_series}


def get_annual_portfolio_evolution(user, year):
    """Monthly global performance without per-asset/per-month database queries."""
    series = _build_annual_asset_series(user, year)
    months = series["months"]
    assets = series["assets"]
    if not months:
        return []

    previous_market_value = sum(asset["initial_value"] for asset in assets)
    monthly_data = []
    for index, month in enumerate(months):
        invested = sum(asset["monthly_values"][index]["invested"] for asset in assets)
        market_value = sum(
            asset["monthly_values"][index]["market_value"] for asset in assets
        )
        contributions = sum(
            asset["monthly_values"][index]["contributions"] for asset in assets
        )
        opening_value = sum(
            asset["monthly_values"][index]["opening_value"] for asset in assets
        )
        profit_loss = sum(asset["monthly_values"][index]["profit"] for asset in assets)
        divisor = previous_market_value + contributions + opening_value
        monthly_data.append(
            {
                "month": month,
                "date_obj": date(year, month, 1),
                "invested": invested,
                "market_value": market_value,
                "contributions": contributions,
                "profit_loss": profit_loss,
                "roi": profit_loss / divisor * 100 if divisor > 0 else 0.0,
            }
        )
        previous_market_value = market_value

    return monthly_data


def get_investment_detailed_evolution(user, year):
    """Breakdown by asset using the same constant-query monthly model."""
    series = _build_annual_asset_series(user, year)
    return {
        "assets": [
            {
                "name": asset["name"],
                "monthly_data": [
                    {"profit": item["profit"], "roi": item["roi"]}
                    for item in asset["monthly_values"]
                ],
                "annual_profit": asset["annual_profit"],
                "annual_contributions": asset["annual_contributions"],
                "annual_roi": asset["annual_roi"],
            }
            for asset in series["assets"]
        ],
        "month_names": [date(year, month, 1) for month in series["months"]],
    }

def get_family_investment_performance(user, year):
    """Calculate combined annual performance for all excluded assets."""
    assets = list(
        Asset.objects.filter(user=user, exclude_from_totals=True).order_by("id")
    )
    if not assets:
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

    asset_ids = [asset.id for asset in assets]
    history_records = list(
        AssetHistory.objects.filter(
            asset_id__in=asset_ids,
            date__lte=cutoff_date,
        )
        .order_by("asset_id", "date", "id")
        .values("asset_id", "date", "total_value")
    )
    transaction_records = list(
        Transaction.objects.filter(
            asset_id__in=asset_ids,
            date__lte=cutoff_date,
        )
        .order_by("asset_id", "date", "id")
        .values("asset_id", "date", "action", "amount")
    )

    previous_history = {}
    current_history = {}
    for record in history_records:
        current_history[record["asset_id"]] = record
        if record["date"] <= day_before_start:
            previous_history[record["asset_id"]] = record

    previous_value = Decimal("0")
    current_value = Decimal("0")
    contributions = Decimal("0")
    for asset in assets:
        asset_transactions = [
            record
            for record in transaction_records
            if record["asset_id"] == asset.id
        ]
        opening_snapshot = previous_history.get(asset.id)
        current_snapshot = current_history.get(asset.id)

        opening_value = (
            opening_snapshot["total_value"] if opening_snapshot else Decimal("0")
        )
        opening_snapshot_date = (
            opening_snapshot["date"] if opening_snapshot else None
        )
        opening_value += sum(
            (
                record["amount"]
                for record in asset_transactions
                if record["date"] <= day_before_start
                and (
                    opening_snapshot_date is None
                    or record["date"] > opening_snapshot_date
                )
            ),
            Decimal("0"),
        )

        closing_value = (
            current_snapshot["total_value"] if current_snapshot else Decimal("0")
        )
        current_snapshot_date = (
            current_snapshot["date"] if current_snapshot else None
        )
        closing_value += sum(
            (
                record["amount"]
                for record in asset_transactions
                if current_snapshot_date is None
                or record["date"] > current_snapshot_date
            ),
            Decimal("0"),
        )

        previous_value += opening_value
        current_value += closing_value
        contributions += sum(
            (
                record["amount"]
                for record in asset_transactions
                if start_of_year <= record["date"] <= cutoff_date
            ),
            Decimal("0"),
        )

    prev_mv = float(previous_value)
    current_mv = float(current_value)
    contrib = float(contributions)

    profit = current_mv - prev_mv - contrib
    invested_base = prev_mv + contrib
    
    roi = (profit / invested_base * 100) if invested_base > 0 else 0

    cash_flows = []
    if prev_mv:
        cash_flows.append((start_of_year, -prev_mv))
    for record in transaction_records:
        if start_of_year <= record["date"] <= cutoff_date:
            amount = float(record["amount"] or 0)
            sign = -1 if record["action"] == "BUY" else 1
            cash_flows.append((record["date"], sign * abs(amount)))
    if current_mv:
        cash_flows.append((cutoff_date, current_mv))
    mwrr = _xirr(cash_flows)

    if mwrr is None:
        mwrr_display = "N/A"
        mwrr_suffix = ""
        mwrr_prefix = ""
        mwrr_status = "secondary"
        mwrr_icon = "bi-dash-circle"
    else:
        mwrr_display = f"{abs(mwrr) * 100:.2f}"
        mwrr_suffix = "%"
        mwrr_prefix = "+" if mwrr > 0 else ("" if mwrr < 0 else "")
        mwrr_status = "success" if mwrr >= 0 else "danger"
        mwrr_icon = "bi-percent"

    return {
        "name": assets[0].name if len(assets) == 1 else "Excluded assets",
        "current_value": current_mv,
        "profit": profit,
        "roi": roi,
        "mwrr": mwrr,
        "mwrr_display": mwrr_display,
        "mwrr_suffix": mwrr_suffix,
        "mwrr_prefix": mwrr_prefix,
        "mwrr_status": mwrr_status,
        "mwrr_icon": mwrr_icon,
        "profit_status": "success" if profit >= 0 else "danger",
        "roi_status": "success" if roi >= 0 else "danger",
        "profit_prefix": "+" if profit > 0 else ("" if profit < 0 else ""),
        "roi_prefix": "+" if roi > 0 else ("" if roi < 0 else ""),
        "roi_icon": "bi-graph-up-arrow" if roi >= 0 else "bi-graph-down-arrow",
    }
