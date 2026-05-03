from decimal import Decimal

from django.db.models import Sum, Q
from django.db.models.functions import Abs

from finances.models import Category, SubCategory

NEEDS_TARGET_RATE = Decimal("0.50")
WANTS_TARGET_RATE = Decimal("0.30")
SAVINGS_TARGET_RATE = Decimal("0.20")

def _clean(val):
    return abs(val or 0)


def _percentage(part, whole):
    return (part / whole * 100) if whole else 0

def get_period_metrics(qs):
    metrics = qs.aggregate(
        income=Sum(
            'amount',
            filter=Q(subcategory__parent_category__transaction_type=Category.TransactionType.INCOME),
        ),
        expenses=Sum(
            'amount',
            filter=Q(subcategory__parent_category__transaction_type=Category.TransactionType.EXPENSE),
        ),
        fixed=Sum(
            'amount',
            filter=Q(subcategory__expense_nature=SubCategory.ExpenseNature.FIXED),
        ),
        variable=Sum(
            'amount',
            filter=Q(subcategory__expense_nature=SubCategory.ExpenseNature.VARIABLE),
        ),
        no_housing=Sum(
            'amount',
            filter=Q(subcategory__parent_category__transaction_type=Category.TransactionType.EXPENSE)
            & Q(subcategory__parent_category__is_housing=False),
        ),
        needs=Sum(
            'amount',
            filter=Q(subcategory__budget_group=SubCategory.BudgetGroup.NEEDS),
        ),
        wants=Sum(
            'amount',
            filter=Q(subcategory__budget_group=SubCategory.BudgetGroup.WANTS),
        ),
        allocated_savings=Sum(
            'amount',
            filter=Q(subcategory__budget_group=SubCategory.BudgetGroup.SAVINGS),
        ),
    )
    
    inc = _clean(metrics['income'])
    exp = _clean(metrics['expenses'])
    cash_surplus = inc - exp
    needs = _clean(metrics["needs"])
    wants = _clean(metrics["wants"])
    allocated_savings = _clean(metrics["allocated_savings"])
    rule_savings = allocated_savings + max(0, cash_surplus)
    
    return {
        "income": inc,
        "expenses": exp,
        "fixed": _clean(metrics['fixed']),
        "variable": _clean(metrics['variable']),
        "no_housing": _clean(metrics['no_housing']),
        "needs": needs,
        "wants": wants,
        "allocated_savings": allocated_savings,
        "rule_savings": rule_savings,
        "needs_pct": _percentage(needs, inc),
        "wants_pct": _percentage(wants, inc),
        "savings_pct": _percentage(rule_savings, inc),
        "needs_target": inc * NEEDS_TARGET_RATE,
        "wants_target": inc * WANTS_TARGET_RATE,
        "savings_target": inc * SAVINGS_TARGET_RATE,
        "needs_delta": needs - (inc * NEEDS_TARGET_RATE),
        "wants_delta": wants - (inc * WANTS_TARGET_RATE),
        "savings_delta": rule_savings - (inc * SAVINGS_TARGET_RATE),
        "savings": cash_surplus,
        "is_incomplete": cash_surplus < 0 and inc < 2000,
        "budget_alerts": _build_budget_alerts(needs, wants, rule_savings, inc),
    }


def _build_budget_alerts(needs, wants, rule_savings, income):
    if not income:
        return []

    alerts = []
    if needs > income * NEEDS_TARGET_RATE:
        alerts.append(
            {
                "group": SubCategory.BudgetGroup.NEEDS,
                "message": "Needs are above the recommended 50%.",
            }
        )
    if wants > income * WANTS_TARGET_RATE:
        alerts.append(
            {
                "group": SubCategory.BudgetGroup.WANTS,
                "message": "Wants are above the recommended 30%.",
            }
        )
    if rule_savings < income * SAVINGS_TARGET_RATE:
        alerts.append(
            {
                "group": SubCategory.BudgetGroup.SAVINGS,
                "message": "Savings are below the recommended 20%.",
            }
        )
    return alerts

def get_previous_month_income(base_qs, year, month):
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    data = base_qs.filter(
        date__year=prev_year,
        date__month=prev_month,
        subcategory__parent_category__transaction_type=Category.TransactionType.INCOME,
    ).aggregate(total=Sum('amount'))
    
    return _clean(data['total'])

def get_expense_distribution_chart(qs):
    expense_stats = qs.filter(
        subcategory__parent_category__transaction_type=Category.TransactionType.EXPENSE,
    ).values(
        'subcategory__parent_category__name'
    ).annotate(total=Sum('amount')).order_by('-total')

    return {
        "labels": [item['subcategory__parent_category__name'] for item in expense_stats],
        "data": [float(_clean(item['total'])) for item in expense_stats]
    }


def get_category_breakdown(qs, transaction_type='EXPENSE'):
    """
    Returns a dictionary { 'Category Name': total_amount }
    for the provided queryset.
    """
    filters = {}
    if transaction_type:
        filters['subcategory__parent_category__transaction_type'] = transaction_type

    data = qs.filter(**filters).values(
        'subcategory__parent_category__name'
    ).annotate(total=Sum('amount'))
    
    return {item['subcategory__parent_category__name']: _clean(item['total']) for item in data}

def get_subcategory_breakdown(qs, transaction_type='EXPENSE'):
    """
    Returns a nested dictionary { 'Category': { 'Subcategory': total_amount } }
    for the provided queryset.
    """
    filters = {}
    if transaction_type:
        filters['subcategory__parent_category__transaction_type'] = transaction_type

    data = qs.filter(**filters).values(
        'subcategory__parent_category__name',
        'subcategory__name'
    ).annotate(total=Sum('amount'))

    breakdown = {}
    for item in data:
        cat_name = item['subcategory__parent_category__name']
        sub_name = item['subcategory__name']
        if cat_name not in breakdown:
            breakdown[cat_name] = {}
        breakdown[cat_name][sub_name] = _clean(item['total'])

    return breakdown


def get_budget_group_breakdown(qs):
    data = (
        qs.exclude(subcategory__budget_group=SubCategory.BudgetGroup.NOT_APPLICABLE)
        .values("subcategory__budget_group")
        .annotate(total=Sum("amount"))
    )
    return {
        item["subcategory__budget_group"]: _clean(item["total"])
        for item in data
    }


def get_monthly_groceries_evolution(qs):
    data = (
        qs.filter(
            subcategory__parent_category__transaction_type=Category.TransactionType.EXPENSE,
            subcategory__budget_group=SubCategory.BudgetGroup.NEEDS,
            subcategory__expense_nature=SubCategory.ExpenseNature.VARIABLE,
        )
        .filter(
            Q(subcategory__name__icontains="grocer")
            | Q(subcategory__name__icontains="supermarket")
            | Q(subcategory__name__icontains="market")
            | Q(subcategory__name__icontains="mercado")
            | Q(subcategory__name__icontains="supermercado")
        )
        .annotate(abs_amount=Abs("amount"))
        .values("date__year", "date__month")
        .annotate(total=Sum("abs_amount"))
        .order_by("date__year", "date__month")
    )
    return [
        {
            "year": item["date__year"],
            "month": item["date__month"],
            "total": item["total"] or 0,
        }
        for item in data
    ]
