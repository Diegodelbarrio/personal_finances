from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from investments.services.api import get_portfolio_overview
from investments.services.history import (
    get_performance_history,
    get_allocation_chart,
    get_monthly_contributions_bar,
)


@login_required
def investments_dashboard(request):
    portfolio_data = get_portfolio_overview(request.user)

    allocation_labels, allocation_data = get_allocation_chart(
        portfolio_data["chart_assets"]
    )

    bar_labels, bar_datasets = get_monthly_contributions_bar(request.user)

    context = {
        **portfolio_data,
        "performance_history": get_performance_history(request.user),
        "allocation_labels": allocation_labels,
        "allocation_data": allocation_data,
        "bar_labels": bar_labels,
        "bar_datasets": bar_datasets,
    }

    return render(request, "investments/investment_dashboard.html", context)
