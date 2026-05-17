from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import SettingsForm
from settings.services.api import SettingsService


@login_required
def settings_home(request):
    user_settings = SettingsService.get_settings(request.user)

    if request.method == 'POST':
        form = SettingsForm(request.POST, instance=user_settings)

        if form.is_valid():
            if not form.has_changed():
                messages.info(request, "No changes detected. Nothing to update.", extra_tags='settings')
                return redirect('settings:settings_home')

            form.save()
            messages.success(request, 'Settings updated successfully!', extra_tags='settings')
            return redirect('settings:settings_home')

        messages.error(request, 'Please correct the errors below.', extra_tags='settings')
    else:
        form = SettingsForm(instance=user_settings)

    phase3_data = SettingsService.get_phase3_insights(request.user)

    progress_data = SettingsService.calculate_goals_progress(
        request.user,
        current_net_worth=phase3_data["simulator"]["current_net_worth"],
        current_annual_savings=phase3_data["snapshot"]["window_total_savings"],
    )
    currency_symbol = "$" if user_settings.main_currency == "USD" else "€"

    context = {
        'form': form,
        'stats': progress_data,
        'phase3': phase3_data,
        'currency_symbol': currency_symbol,
    }
    return render(request, 'settings/settings_home.html', context)
