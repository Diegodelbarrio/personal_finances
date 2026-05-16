from calendar import monthrange
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from django.db.models import Q
from django.utils import timezone

from investments.models import Asset, AssetHistory, Transaction
from investments.services.api import EXCLUDE_ASSET_NAME, get_money_weighted_return


DEFAULT_PORTFOLIO_PERIOD = "1y"

PORTFOLIO_PERIOD_CONFIG = {
    "1mo": {"label": "1M", "months": 1, "max_points": 220},
    "3mo": {"label": "3M", "months": 3, "max_points": 260},
    "6mo": {"label": "6M", "months": 6, "max_points": 280},
    "ytd": {"label": "YTD", "mode": "ytd", "max_points": 300},
    "1y": {"label": "1Y", "months": 12, "max_points": 320},
    "5y": {"label": "5Y", "months": 60, "max_points": 360},
    "all": {"label": "ALL", "mode": "all", "max_points": 420},
}

CATEGORY_COLORS = {
    "CRYPTO": "#f59e0b",
    "INDEX_FUND": "#2563eb",
    "COMMODITY": "#dc2626",
    "STOCK": "#16a34a",
}


def normalize_portfolio_period(raw_period: Optional[str]) -> str:
    return raw_period if raw_period in PORTFOLIO_PERIOD_CONFIG else DEFAULT_PORTFOLIO_PERIOD


def portfolio_period_options() -> List[Dict[str, str]]:
    return [
        {"value": value, "label": config["label"]}
        for value, config in PORTFOLIO_PERIOD_CONFIG.items()
    ]


def get_portfolio_market_context(
    user,
    period: Optional[str],
    asset_id: Optional[str] = None,
    query: str = "",
) -> Dict:
    selected_period = normalize_portfolio_period(period)
    cleaned_query = (query or "").strip()
    portfolio_assets = list(Asset.objects.filter(user=user).order_by("name"))
    asset_options = _build_asset_options(portfolio_assets)
    searchable_assets = _filter_asset_options(asset_options, cleaned_query)

    selected_asset = _get_selected_asset(portfolio_assets, asset_id)
    selected_scope = "asset" if selected_asset else "portfolio"
    selected_asset_id = str(selected_asset.id) if selected_asset else "portfolio"
    portfolio_includes_family = False

    if selected_asset:
        series = _asset_value_series(user, selected_asset)
        scope_name = selected_asset.name
        scope_meta = selected_asset.get_category_display()
        color = CATEGORY_COLORS.get(selected_asset.category, "#2563eb")
        transactions = _transaction_rows(user, asset=selected_asset)
        first_available_date = series[0][0] if series else None
    else:
        non_family_assets = [
            asset for asset in portfolio_assets if asset.name != EXCLUDE_ASSET_NAME
        ]
        investable_assets = non_family_assets or portfolio_assets
        portfolio_includes_family = not non_family_assets
        series = _portfolio_value_series(user, investable_assets)
        scope_name = "Portfolio"
        scope_meta = f"{len(investable_assets)} assets"
        color = "#2563eb"
        transactions = _transaction_rows(
            user,
            asset=None,
            include_family=portfolio_includes_family,
        )
        first_available_date = series[0][0] if series else None

    performance = _build_performance_payload(
        user=user,
        series=series,
        transactions=transactions,
        period=selected_period,
        selected_asset=selected_asset,
        include_family=selected_scope == "portfolio" and portfolio_includes_family,
    )
    chart_payload = _build_chart_payload(
        series=performance["series"],
        transactions=performance["period_transactions"],
        color=color,
        scope_name=scope_name,
        max_points=PORTFOLIO_PERIOD_CONFIG[selected_period]["max_points"],
    )

    return {
        "asset_options": asset_options,
        "searchable_assets": searchable_assets,
        "chart_payload": chart_payload,
        "performance": performance,
        "period_options": portfolio_period_options(),
        "selected_period": selected_period,
        "selected_period_label": PORTFOLIO_PERIOD_CONFIG[selected_period]["label"],
        "selected_asset_id": selected_asset_id,
        "selected_scope": selected_scope,
        "selected_scope_name": scope_name,
        "selected_scope_meta": scope_meta,
        "query": cleaned_query,
        "portfolio_has_assets": bool(portfolio_assets),
        "first_available_date": first_available_date,
        "generated_at": timezone.localtime(),
    }


def _build_asset_options(assets: Iterable[Asset]) -> List[Dict]:
    options = []
    for asset in assets:
        histories = list(asset.history.order_by("date"))
        latest_history = histories[-1] if histories else None
        first_history = histories[0] if histories else None
        invested = _asset_invested_total(asset)
        current_value = float(latest_history.total_value) if latest_history else invested
        profit_loss = current_value - invested
        roi = (profit_loss / invested * 100) if invested else None
        searchable_text = " ".join(
            [
                asset.name,
                asset.platform,
                asset.get_category_display(),
                asset.isin or "",
            ]
        ).lower()

        options.append(
            {
                "id": str(asset.id),
                "name": asset.name,
                "platform": asset.platform,
                "category": asset.get_category_display(),
                "category_code": asset.category,
                "isin": asset.isin or "",
                "current_value": current_value,
                "profit_loss": profit_loss,
                "roi": roi,
                "roi_display": _format_percent(roi),
                "latest_date": latest_history.date if latest_history else None,
                "first_date": first_history.date if first_history else None,
                "history_count": len(histories),
                "searchable_text": searchable_text,
                "is_family": asset.name == EXCLUDE_ASSET_NAME,
            }
        )

    options.sort(key=lambda item: item["current_value"], reverse=True)
    return options


def _filter_asset_options(asset_options: List[Dict], query: str) -> List[Dict]:
    if not query:
        return asset_options
    query_terms = [term.lower() for term in query.split() if term.strip()]
    if not query_terms:
        return asset_options
    return [
        asset
        for asset in asset_options
        if all(term in asset["searchable_text"] for term in query_terms)
    ]


def _get_selected_asset(assets: List[Asset], asset_id: Optional[str]) -> Optional[Asset]:
    if not asset_id or asset_id == "portfolio":
        return None
    try:
        normalized_asset_id = int(asset_id)
    except (TypeError, ValueError):
        return None
    return next((asset for asset in assets if asset.id == normalized_asset_id), None)


def _asset_value_series(user, asset: Asset) -> List[Tuple[date, float]]:
    histories = (
        AssetHistory.objects.filter(user=user, asset=asset)
        .values_list("date", "total_value")
        .order_by("date")
    )
    return [(item_date, float(total_value)) for item_date, total_value in histories]


def _portfolio_value_series(user, assets: List[Asset]) -> List[Tuple[date, float]]:
    asset_ids = [asset.id for asset in assets]
    if not asset_ids:
        return []

    histories = (
        AssetHistory.objects.filter(user=user, asset_id__in=asset_ids)
        .values_list("date", "asset_id", "total_value")
        .order_by("date", "asset_id")
    )

    rows_by_date: Dict[date, List[Tuple[int, float]]] = {}
    for item_date, asset_id, total_value in histories:
        rows_by_date.setdefault(item_date, []).append((asset_id, float(total_value)))

    latest_by_asset: Dict[int, float] = {}
    series = []
    for item_date in sorted(rows_by_date):
        for asset_id, total_value in rows_by_date[item_date]:
            latest_by_asset[asset_id] = total_value
        if latest_by_asset:
            series.append((item_date, sum(latest_by_asset.values())))
    return series


def _transaction_rows(
    user,
    asset: Optional[Asset],
    include_family: bool = True,
) -> List[Transaction]:
    query = Q(user=user, asset__user=user)
    if asset:
        query &= Q(asset=asset)
    elif not include_family:
        query &= ~Q(asset__name=EXCLUDE_ASSET_NAME)
    return list(Transaction.objects.filter(query).select_related("asset").order_by("date"))


def _build_performance_payload(
    user,
    series: List[Tuple[date, float]],
    transactions: List[Transaction],
    period: str,
    selected_asset: Optional[Asset],
    include_family: bool,
) -> Dict:
    empty_payload = _empty_performance_payload()
    if not series:
        return empty_payload

    end_date = series[-1][0]
    target_start = _period_start_date(period, end_date, series[0][0])
    period_series, is_partial = _slice_series_for_period(series, target_start)

    if not period_series:
        return empty_payload

    start_date = period_series[0][0]
    start_value = period_series[0][1]
    end_value = period_series[-1][1]
    period_transactions = [
        tx for tx in transactions if start_date < tx.date <= end_date
    ]
    net_contributions = sum(_transaction_impact(tx) for tx in period_transactions)
    contributions_in = sum(
        max(_transaction_impact(tx), 0) for tx in period_transactions
    )
    withdrawals = abs(
        sum(min(_transaction_impact(tx), 0) for tx in period_transactions)
    )

    raw_change = end_value - start_value
    market_change = raw_change - net_contributions
    capital_base = start_value + contributions_in
    return_pct = (market_change / capital_base * 100) if capital_base else None

    mwrr = None
    if len(period_series) >= 2:
        mwrr = get_money_weighted_return(
            user=user,
            start_date=start_date,
            end_date=end_date,
            start_value=start_value,
            end_value=end_value,
            asset=selected_asset,
            include_family=include_family,
        )

    return {
        "has_data": True,
        "has_enough_data": len(period_series) >= 2,
        "series": period_series,
        "period_transactions": period_transactions,
        "start_date": start_date,
        "end_date": end_date,
        "target_start_date": target_start,
        "start_value": start_value,
        "current_value": end_value,
        "raw_change": raw_change,
        "market_change": market_change,
        "net_contributions": net_contributions,
        "contributions_in": contributions_in,
        "withdrawals": withdrawals,
        "return_pct": return_pct,
        "return_display": _format_percent(return_pct),
        "mwrr": mwrr,
        "mwrr_display": _format_percent(mwrr * 100 if mwrr is not None else None),
        "snapshots": len(period_series),
        "transaction_count": len(period_transactions),
        "is_partial": is_partial or start_date > target_start,
        "status": "success" if market_change >= 0 else "danger",
        "return_status": "success" if (return_pct or 0) >= 0 else "danger",
    }


def _empty_performance_payload() -> Dict:
    return {
        "has_data": False,
        "has_enough_data": False,
        "series": [],
        "period_transactions": [],
        "start_date": None,
        "end_date": None,
        "target_start_date": None,
        "start_value": 0,
        "current_value": 0,
        "raw_change": 0,
        "market_change": 0,
        "net_contributions": 0,
        "contributions_in": 0,
        "withdrawals": 0,
        "return_pct": None,
        "return_display": "N/A",
        "mwrr": None,
        "mwrr_display": "N/A",
        "snapshots": 0,
        "transaction_count": 0,
        "is_partial": False,
        "status": "secondary",
        "return_status": "secondary",
    }


def _build_chart_payload(
    series: List[Tuple[date, float]],
    transactions: List[Transaction],
    color: str,
    scope_name: str,
    max_points: int,
) -> Dict:
    if not series:
        return {
            "labels": [],
            "market_values": [],
            "capital_base_values": [],
            "scope_name": scope_name,
            "color": color,
        }

    labels = [item_date.strftime("%Y-%m-%d") for item_date, _ in series]
    values = [round(value, 2) for _, value in series]
    capital_base_values = _capital_base_series(series, transactions)
    labels, values, capital_base_values = _downsample_three_series(
        labels,
        values,
        capital_base_values,
        max_points=max_points,
    )

    return {
        "labels": labels,
        "market_values": values,
        "capital_base_values": capital_base_values,
        "scope_name": scope_name,
        "color": color,
    }


def _capital_base_series(
    series: List[Tuple[date, float]], transactions: List[Transaction]
) -> List[float]:
    if not series:
        return []
    running_base = series[0][1]
    tx_index = 0
    sorted_transactions = sorted(transactions, key=lambda tx: tx.date)
    base_values = []

    for item_date, _ in series:
        while (
            tx_index < len(sorted_transactions)
            and sorted_transactions[tx_index].date <= item_date
        ):
            running_base += _transaction_impact(sorted_transactions[tx_index])
            tx_index += 1
        base_values.append(round(running_base, 2))
    return base_values


def _slice_series_for_period(
    series: List[Tuple[date, float]],
    target_start: date,
) -> Tuple[List[Tuple[date, float]], bool]:
    if not series:
        return [], False

    baseline = None
    for item in series:
        if item[0] <= target_start:
            baseline = item
        else:
            break

    if baseline:
        sliced = [baseline] + [item for item in series if item[0] > baseline[0]]
        return sliced, baseline[0] < target_start

    sliced = [item for item in series if item[0] >= target_start]
    return sliced, True


def _period_start_date(period: str, end_date: date, first_available_date: date) -> date:
    config = PORTFOLIO_PERIOD_CONFIG[period]
    if config.get("mode") == "all":
        return first_available_date
    if config.get("mode") == "ytd":
        return date(end_date.year, 1, 1)
    if "days" in config:
        return end_date - timedelta(days=config["days"])
    if "months" in config:
        return _shift_months(end_date, -config["months"])
    return end_date


def _shift_months(source_date: date, months: int) -> date:
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _asset_invested_total(asset: Asset) -> float:
    total = 0.0
    for tx in asset.transactions.all():
        total += _transaction_impact(tx)
    return total


def _transaction_impact(transaction: Transaction) -> float:
    amount = float(transaction.amount or 0)
    if transaction.action == "SELL":
        return -abs(amount)
    return abs(amount)


def _format_percent(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def _downsample_three_series(
    labels: List[str],
    values: List[float],
    second_values: List[float],
    max_points: int,
) -> Tuple[List[str], List[float], List[float]]:
    total_points = len(values)
    if total_points <= max_points:
        return labels, values, second_values

    stride = max(1, (total_points + max_points - 1) // max_points)
    sampled_labels = labels[::stride]
    sampled_values = values[::stride]
    sampled_second_values = second_values[::stride]

    if sampled_labels[-1] != labels[-1]:
        sampled_labels.append(labels[-1])
        sampled_values.append(values[-1])
        sampled_second_values.append(second_values[-1])

    return sampled_labels, sampled_values, sampled_second_values
