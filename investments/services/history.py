from django.db.models import Sum
from django.db.models.functions import TruncMonth

from investments.models import Transaction, AssetHistory

EXCLUDE_ASSET_NAME = "Family Investments"


def get_performance_history(user):
    contributions = (
        Transaction.objects
        .filter(asset__user=user)
        .exclude(asset__name=EXCLUDE_ASSET_NAME)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    market_history = (
        AssetHistory.objects
        .filter(asset__user=user)
        .exclude(asset__name=EXCLUDE_ASSET_NAME)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("total_value"))
        .order_by("month")
    )

    all_months = sorted(set(
        [c["month"] for c in contributions if c["month"]] +
        [m["month"] for m in market_history if m["month"]]
    ))

    history = []
    running_invested = 0
    last_market_value = 0

    for m in all_months:
        contrib = next((c["total"] for c in contributions if c["month"] == m), 0)
        running_invested += float(contrib or 0)

        market = next((mh["total"] for mh in market_history if mh["month"] == m), None)
        if market is not None:
            last_market_value = float(market)
        else:
            last_market_value = max(last_market_value, running_invested)

        history.append({
            "label": m.strftime("%b %y"),
            "invested": running_invested,
            "market": last_market_value,
        })

    return history


def get_allocation_chart(chart_assets):
    # ORDENAR de mayor a menor valor actual
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
        .exclude(asset__name=EXCLUDE_ASSET_NAME)
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
