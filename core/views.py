from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from core.services.net_worth import calculate_net_worth
from holdings.services.history import get_net_worth_evolution


@login_required
def home(request):
    net_worth_history = get_net_worth_evolution(request.user)
    net_worth = calculate_net_worth(request.user)

    context = {
        "net_worth_history": net_worth_history,
        **net_worth,
        "user_name": request.user.username,
    }

    return render(request, "core/index.html", context)
