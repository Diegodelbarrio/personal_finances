from django.shortcuts import render
from holdings.views import get_net_worth_evolution

def home(request):
    # Obtenemos el historial consolidado
    net_worth_history = get_net_worth_evolution()
    
    # El Net Worth actual es el último punto del gráfico
    current_net_worth = net_worth_history[-1]['value'] if net_worth_history else 0
    
    context = {
        'net_worth_history': net_worth_history,
        'current_net_worth': current_net_worth,
    }
    
    # Asegúrate de que tu template en core se llame landing.html o cámbialo aquí
    return render(request, 'core/index.html', context)