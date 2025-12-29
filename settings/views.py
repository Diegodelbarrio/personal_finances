from django.shortcuts import render, redirect
from django.contrib import messages  # Para los mensajes
from django.contrib.auth.decorators import login_required
from .forms import SettingsForm
from settings.services.api import SettingsService

@login_required
def settings_home(request):
    # Usamos el service para obtener el objeto existente (o crearlo si no existe)
    user_settings = SettingsService.get_settings(request.user)

    if request.method == 'POST':
        form = SettingsForm(request.POST, instance=user_settings)
        
        # 1. Verificamos si el formulario ha cambiado respecto a la instancia
        if not form.has_changed():
            messages.info(request, "No changes detected. Nothing to update.", extra_tags='settings')
            return redirect('settings:settings_home')

        # 2. Si hay cambios, validamos y guardamos
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully!', extra_tags='settings')
            return redirect('settings:settings_home')
        else:
            messages.error(request, 'Please correct the errors below.', extra_tags='settings')
    else:
        form = SettingsForm(instance=user_settings)

    # Obtenemos progreso real para los gráficos
    progress_data = SettingsService.calculate_goals_progress(request.user)

    context = {
        'form': form,
        'stats': progress_data
    }
    return render(request, 'settings/settings_home.html', context)