from django.shortcuts import render
from finances.models import Transaction
from django.db.models import Sum

def home(request):
    # Datos de Finances
    balance = Transaction.objects.aggregate(total=Sum('amount'))['total'] or 0
    
    # Aquí irás sumando datos de otras apps según las crees
    # Ej: investments_total = Investment.objects.all().total()
    
    context = {
        'balance': balance,
        # 'invest_total': 0,
        # 'knowledge_count': 0,
    }
    return render(request, 'core/index.html', context)