from django.shortcuts import render
from .models import Transaction
from django.db.models import Sum

def summary(request):
    transactions = Transaction.objects.all().order_by('-date')

    # We calculate the total of the 'amount' column
    # .aggregate() returns a dictionary, e.g., {'amount__sum': 150.50}
    total_balance = Transaction.objects.aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'transactions': transactions,
        'total_balance': total_balance, # We send it to the HTML
        'user_name': 'Diego del Barrio',
    }
    return render(request, 'finances/summary.html', context)