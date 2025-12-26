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
