from datetime import date

from holdings.models import AccountBalanceSnapshot
from investments.models import AssetHistory


def _month_start(value):
    return date(value.year, value.month, 1)


def _next_month(value):
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _latest_records_by_owner_and_month(records, owner_key, value_key):
    """Return one value per owner/month, keeping the latest dated record."""
    latest = {}
    for record in records:
        month = _month_start(record["date"])
        latest[(record[owner_key], month)] = record[value_key]
    return latest


def get_net_worth_evolution(user):
    """
    Build a continuous monthly net-worth history.

    Each account/asset contributes at most one snapshot per month and its last
    known value is carried forward until a newer snapshot is available.
    """
    cash_records = list(
        AccountBalanceSnapshot.objects.filter(account__user=user)
        .order_by("date", "id")
        .values("account_id", "date", "balance")
    )
    investment_records = list(
        AssetHistory.objects.filter(asset__user=user)
        .order_by("date", "id")
        .values("asset_id", "date", "total_value")
    )

    if not cash_records and not investment_records:
        return []

    cash_by_month = _latest_records_by_owner_and_month(
        cash_records, "account_id", "balance"
    )
    investments_by_month = _latest_records_by_owner_and_month(
        investment_records, "asset_id", "total_value"
    )

    all_dates = [record["date"] for record in cash_records + investment_records]
    current_month = _month_start(min(all_dates))
    last_month = _month_start(max(all_dates))
    current_cash = {}
    current_investments = {}
    history = []

    while current_month <= last_month:
        for (account_id, month), balance in cash_by_month.items():
            if month == current_month:
                current_cash[account_id] = balance
        for (asset_id, month), total_value in investments_by_month.items():
            if month == current_month:
                current_investments[asset_id] = total_value

        cash = float(sum(current_cash.values()))
        investments = float(sum(current_investments.values()))
        history.append(
            {
                "date": current_month,
                "label": current_month.strftime("%b %y"),
                "savings": cash,
                "investments": investments,
                "value": cash + investments,
            }
        )
        current_month = _next_month(current_month)

    return history
