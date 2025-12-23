from django.shortcuts import render
from holdings.views import get_net_worth_evolution
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    # 1. Pasamos el usuario actual a la función de evolución
    # Ahora la función solo sumará sus cuentas y sus inversiones
    net_worth_history = get_net_worth_evolution(request.user)
    
    # 2. Obtenemos el Net Worth actual (último dato del array)
    # Usamos un condicional para evitar errores si el usuario no tiene datos aún
    if net_worth_history:
        current_net_worth = net_worth_history[-1]['value']
    else:
        current_net_worth = 0
    
    context = {
        'net_worth_history': net_worth_history,
        'current_net_worth': current_net_worth,
        'user_name': request.user.username, # Útil para el saludo inicial
    }
    
    return render(request, 'core/index.html', context)