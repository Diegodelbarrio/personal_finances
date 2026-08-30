from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from investments.models import Transaction, AssetHistory

def get_performance_history(user):
    transaction_records = list(
        Transaction.objects.filter(asset__user=user)
        .exclude(asset__exclude_from_totals=True)
        .order_by("date", "id")
        .values("asset_id", "date", "amount")
    )
    market_records = list(
        AssetHistory.objects.filter(asset__user=user)
        .exclude(asset__exclude_from_totals=True)
        .order_by("date", "id")
        .values("asset_id", "date", "total_value")
    )

    if not transaction_records and not market_records:
        return []

    def month_start(value):
        return date(value.year, value.month, 1)

    def next_month(value):
        if value.month == 12:
            return date(value.year + 1, 1, 1)
        return date(value.year, value.month + 1, 1)

    contributions_by_month = defaultdict(lambda: defaultdict(Decimal))
    latest_market_by_month = {}
    asset_ids = set()
    source_dates = []

    for record in transaction_records:
        month = month_start(record["date"])
        contributions_by_month[month][record["asset_id"]] += record["amount"]
        asset_ids.add(record["asset_id"])
        source_dates.append(record["date"])

    for record in market_records:
        month = month_start(record["date"])
        latest_market_by_month[(month, record["asset_id"])] = record["total_value"]
        asset_ids.add(record["asset_id"])
        source_dates.append(record["date"])

    history = []
    running_invested = Decimal("0")
    invested_by_asset = defaultdict(Decimal)
    latest_market_by_asset = {}
    current_month = month_start(min(source_dates))
    final_month = month_start(max(source_dates))

    while current_month <= final_month:
        for asset_id, contribution in contributions_by_month[current_month].items():
            invested_by_asset[asset_id] += contribution
            running_invested += contribution

        for asset_id in asset_ids:
            market_value = latest_market_by_month.get((current_month, asset_id))
            if market_value is not None:
                latest_market_by_asset[asset_id] = market_value

        market_total = sum(
            latest_market_by_asset.get(asset_id, invested_by_asset[asset_id])
            for asset_id in asset_ids
        )
        history.append(
            {
                "label": current_month.strftime("%b %y"),
                "invested": float(running_invested),
                "market": float(market_total),
            }
        )
        current_month = next_month(current_month)

    return history


def get_allocation_chart(chart_assets):
    sorted_assets = sorted(
        chart_assets,
        key=lambda x: x["current_value"],
        reverse=True
    )

    labels = [item["obj"].name for item in sorted_assets]
    data = [item["current_value"] for item in sorted_assets]

    return labels, data



def get_monthly_contributions_bar(user):
    contributions = (
        Transaction.objects
        .filter(asset__user=user)
        .exclude(asset__exclude_from_totals=True)
        .annotate(month=TruncMonth("date"))
        .values("month", "asset__name")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    months = sorted(set(c["month"] for c in contributions if c["month"]))
    labels = [m.strftime("%b %y") for m in months]
    asset_names = sorted(set(c["asset__name"] for c in contributions))

    datasets = []
    for asset in asset_names:
        data = []
        for m in months:
            val = next(
                (c["total"] for c in contributions
                 if c["month"] == m and c["asset__name"] == asset),
                0
            )
            data.append(float(val))
        datasets.append({"label": asset, "data": data})

    return labels, datasets
