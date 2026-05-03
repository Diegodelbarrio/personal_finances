# finances/services/api.py
from datetime import date

from django.db.models import Max, Min, Q, Sum
from django.utils import timezone

from . import queries, metrics

def get_annual_cashflow_summary(user, year):
    """
    Returns a breakdown of income, expenditure, and savings month by month,
    adjusting the range of months according to actual activity and projections.
    """
    now = timezone.now().date()
    base_qs = queries.get_base_transaction_qs(user)
    
    # 1. We explore the limits of the user's story
    # When was your first transaction and when is your last (including future ones)?
    activity_limits = base_qs.aggregate(
        first_date=Min('date'),
        last_date=Max('date')
    )
    
    first_date = activity_limits['first_date']
    last_date = activity_limits['last_date']

    # 2. Define the START month for the year consulted
    if first_date and year == first_date.year:
        start_month = first_date.month
    elif first_date and year < first_date.year:
        return [] #The year is prior to the user starting
    else:
        start_month = 1 # One year after commencement, we begin in January.

    # 3. Define the END month for the year consulted
    if year < now.year:
        end_month = 12 # Past years are shown in full
    elif year == now.year:
        # In the current year, we show up to "Today" or up to the last future transaction.
        last_month_with_data = last_date.month if (last_date and last_date.year == year) else 0
        end_month = max(now.month, last_month_with_data)
    else:
        # For future years, we only show if there are planned transactions
        if last_date and year == last_date.year:
            end_month = last_date.month
        else:
            return [] # Future year without transactions

    # 4. Generate the data for the calculated range
    months = range(start_month, end_month + 1)
    monthly_data = []
    
    for month in months:
        period_qs = base_qs.filter(date__year=year, date__month=month)
        stats = metrics.get_period_metrics(period_qs)

        category_breakdown = metrics.get_category_breakdown(period_qs, transaction_type='EXPENSE')
        subcategory_breakdown = metrics.get_subcategory_breakdown(period_qs, transaction_type='EXPENSE')
        budget_group_breakdown = metrics.get_budget_group_breakdown(period_qs)
        
        income_category_breakdown = metrics.get_category_breakdown(period_qs, transaction_type='INCOME')
        income_subcategory_breakdown = metrics.get_subcategory_breakdown(period_qs, transaction_type='INCOME')
        
        # Breakdown by location for Travel (Trip expenses)
        travel_breakdown = {}
        travel_qs = period_qs.filter(
            Q(subcategory__name="Travel")
            | Q(subcategory__parent_category__name="Travel")
        ).exclude(location__isnull=True)
        if travel_qs.exists():
            loc_stats = travel_qs.values('location__name').annotate(total=Sum('amount'))
            travel_breakdown = {item['location__name']: item['total'] for item in loc_stats}

        # Calculate savings rate
        savings_rate = (stats["savings"] / stats["income"] * 100) if stats["income"] > 0 else 0

        monthly_data.append({
            "month": month,
            "date_obj": date(year, month, 1),
            "income": stats["income"],
            "expenses": stats["expenses"],
            "fixed": stats["fixed"],
            "variable": stats["variable"],
            "needs": stats["needs"],
            "wants": stats["wants"],
            "allocated_savings": stats["allocated_savings"],
            "rule_savings": stats["rule_savings"],
            "needs_pct": stats["needs_pct"],
            "wants_pct": stats["wants_pct"],
            "savings_pct": stats["savings_pct"],
            "budget_alerts": stats["budget_alerts"],
            "savings": stats["savings"],
            "savings_rate": savings_rate,
            "categories": category_breakdown,
            "subcategories": subcategory_breakdown,
            "budget_groups": budget_group_breakdown,
            "income_categories": income_category_breakdown,
            "income_subcategories": income_subcategory_breakdown,
            "travel_breakdown": travel_breakdown,
        })
        
    return monthly_data

def get_available_transaction_years(user):
    """We present the list of available years"""
    return queries.get_available_years(user)
