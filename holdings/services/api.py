from calendar import monthrange
from collections import defaultdict
from datetime import date

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from holdings.models import AccountBalanceSnapshot, BankAccount
from core.currency import get_user_currency


def get_currency_mismatches(user):
    reporting_currency = get_user_currency(user)
    return list(
        BankAccount.objects.filter(user=user)
        .exclude(currency=reporting_currency)
        .order_by("name", "id")
        .values("id", "name", "currency")
    )


def get_current_value(user, dates_only_active=False):
    """Return the latest balance total and the snapshot dates used."""
    latest_snapshot = AccountBalanceSnapshot.objects.filter(
        account=OuterRef("pk"),
    ).order_by("-date", "-id")
    accounts = BankAccount.objects.filter(
        user=user,
        currency=get_user_currency(user),
    ).annotate(
        latest_balance=Subquery(latest_snapshot.values("balance")[:1]),
        latest_date=Subquery(latest_snapshot.values("date")[:1]),
    )

    total = 0.0
    dates = []
    for account in accounts:
        if account.latest_balance is not None:
            total += float(account.latest_balance)
        if account.latest_date and ((not dates_only_active) or account.is_active):
            dates.append(account.latest_date)

    return total, dates


def _get_last_day_of_month(year, month):
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)


def get_annual_balance_evolution(user, year):
    """
    Return account balances at each month end.

    A balance recorded before the requested year remains valid until it is
    replaced. This avoids resetting January to zero when no new snapshot exists.
    """
    reporting_currency = get_user_currency(user)
    currency_mismatches = get_currency_mismatches(user)
    accounts = list(
        BankAccount.objects.filter(user=user, currency=reporting_currency).order_by("name", "id")
    )
    today = timezone.localdate()
    first_snapshot_date = (
        AccountBalanceSnapshot.objects.filter(
            account__user=user,
            account__currency=reporting_currency,
        )
        .order_by("date")
        .values_list("date", flat=True)
        .first()
    )

    if not first_snapshot_date or year < first_snapshot_date.year or year > today.year:
        months = []
    else:
        start_month = first_snapshot_date.month if year == first_snapshot_date.year else 1
        end_month = today.month if year == today.year else 12
        months = list(range(start_month, end_month + 1))

    if not months:
        return {
            "matrix": [],
            "monthly_totals": [],
            "month_names": [],
            "currency_mismatches": currency_mismatches,
        }

    final_cutoff = _get_last_day_of_month(year, months[-1])
    snapshots_by_account = defaultdict(list)
    snapshots = (
        AccountBalanceSnapshot.objects.filter(
            account__user=user,
            account__currency=reporting_currency,
            date__lte=final_cutoff,
        )
        .order_by("account_id", "date", "id")
        .values("account_id", "date", "balance")
    )
    for snapshot in snapshots:
        snapshots_by_account[snapshot["account_id"]].append(snapshot)

    matrix = []
    for account in accounts:
        account_snapshots = snapshots_by_account[account.id]
        snapshot_index = 0
        latest_balance = 0.0
        balances = []

        for month in months:
            cutoff = _get_last_day_of_month(year, month)
            while (
                snapshot_index < len(account_snapshots)
                and account_snapshots[snapshot_index]["date"] <= cutoff
            ):
                latest_balance = float(account_snapshots[snapshot_index]["balance"])
                snapshot_index += 1
            balances.append(latest_balance)

        matrix.append({"account_name": account.name, "balances": balances})

    monthly_totals = [
        sum(row["balances"][index] for row in matrix)
        for index in range(len(months))
    ]
    return {
        "matrix": matrix,
        "monthly_totals": monthly_totals,
        "month_names": [date(year, month, 1) for month in months],
        "currency_mismatches": currency_mismatches,
    }
