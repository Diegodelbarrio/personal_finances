from django.db.models import OuterRef, Subquery

from holdings.models import AccountBalanceSnapshot, BankAccount


def get_current_value(user, dates_only_active=False):
    """
    Devuelve el valor total actual de las cuentas (cash)
    y las fechas usadas para el cálculo.
    """
    latest_snapshot = AccountBalanceSnapshot.objects.filter(
        account=OuterRef("pk"),
    ).order_by("-date")
    accounts = BankAccount.objects.filter(user=user).annotate(
        latest_balance=Subquery(latest_snapshot.values("balance")[:1]),
        latest_date=Subquery(latest_snapshot.values("date")[:1]),
    )

    total = 0.0
    dates = []

    for acc in accounts:
        if acc.latest_balance is not None:
            total += float(acc.latest_balance)
        if acc.latest_date and ((not dates_only_active) or acc.is_active):
            dates.append(acc.latest_date)

    return total, dates

from calendar import monthrange
from datetime import date
from ..models import BankAccount, AccountBalanceSnapshot
from django.utils import timezone

def _get_last_day_of_month(year, month):
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)

def get_annual_balance_evolution(user, year):
    accounts = BankAccount.objects.filter(user=user)
    now = timezone.now().date()
    
    # 1. Buscamos cuándo empezó el usuario para no mostrar meses vacíos al inicio del histórico
    first_snapshot = AccountBalanceSnapshot.objects.filter(
        account__user=user
    ).order_by('date').first()
    
    # 2. Definir el rango de meses (Start / End)
    if not first_snapshot or year < first_snapshot.date.year or year > now.year:
        # Si el año consultado es previo a su historia o es futuro total
        months_range = []
    else:
        # Mes de inicio: si es el primer año, empezamos en su primer mes. Si no, en Enero (1).
        start_month = first_snapshot.date.month if year == first_snapshot.date.year else 1
        
        # Mes de fin: si es el año actual, llegamos hasta hoy. Si es pasado, hasta Diciembre (12).
        end_month = now.month if year == now.year else 12
        
        months_range = range(start_month, end_month + 1)

    # 3. Construcción de la Matrix
    matrix = []
    for acc in accounts:
        row = {'account_name': acc.name, 'balances': []}
        for month in months_range:
            cutoff = _get_last_day_of_month(year, month)
            
            # Buscamos el último balance dentro del año actual para evitar arrastres de años previos
            snapshot = AccountBalanceSnapshot.objects.filter(
                account=acc,
                date__lte=cutoff,
                date__year=year  # Restringe la búsqueda al año del reporte
            ).order_by('-date').first()
            
            balance = float(snapshot.balance) if snapshot else 0.0
            row['balances'].append(balance)
        matrix.append(row)

    # 4. Totales mensuales (solo para los meses calculados)
    monthly_totals = []
    for i in range(len(months_range)):
        total_month = sum(row['balances'][i] for row in matrix)
        monthly_totals.append(total_month)

    return {
        "matrix": matrix,
        "monthly_totals": monthly_totals,
        "month_names": [date(year, m, 1) for m in months_range]
    }
