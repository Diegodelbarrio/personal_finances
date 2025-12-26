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
        "last_market_date": max(last_market_dates) if last_market_dates else None,
        "chart_assets": no_family,
    }
