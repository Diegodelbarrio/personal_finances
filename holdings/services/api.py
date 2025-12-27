from holdings.models import AccountBalanceSnapshot, BankAccount


def get_current_value(user):
    """
    Devuelve el valor total actual de las cuentas (cash)
    y las fechas usadas para el cálculo.
    """
    total = 0
    dates = []

    accounts = BankAccount.objects.filter(user=user)
    for acc in accounts:
        last_snapshot = (
            AccountBalanceSnapshot.objects
            .filter(account=acc)
            .order_by('-date')
            .first()
        )
        if last_snapshot:
            total += float(last_snapshot.balance)
            dates.append(last_snapshot.date)

    return total, dates


# holdings/services/api.py
from calendar import monthrange
from datetime import date
from ..models import BankAccount, AccountBalanceSnapshot

def _get_last_day_of_month(year, month):
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)

def get_annual_balance_evolution(user, year):
    accounts = BankAccount.objects.filter(user=user)
    months = range(1, 13)
    
    # 1. Estructura para la tabla: Una fila por cuenta
    matrix = []
    for acc in accounts:
        row = {'account_name': acc.name, 'balances': []}
        for month in months:
            cutoff = _get_last_day_of_month(year, month)
            snapshot = AccountBalanceSnapshot.objects.filter(
                account=acc,
                date__lte=cutoff
            ).order_by('-date').first()
            
            balance = float(snapshot.balance) if snapshot else 0.0
            row['balances'].append(balance)
        matrix.append(row)

    # 2. Totales mensuales (Fila inferior de la tabla)
    monthly_totals = []
    for month_idx in range(12): # 0 a 11
        total_month = sum(row['balances'][month_idx] for row in matrix)
        monthly_totals.append(total_month)

    return {
        "matrix": matrix,
        "monthly_totals": monthly_totals,
        "month_names": [date(year, m, 1) for m in months]
    }