from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .services.selectors import get_summary_page_data

@login_required
def summary(request):
    # 1. Entrada de datos (Input)
    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    
    # 2. Lógica de negocio/selección (Process)
    context = get_summary_page_data(request.user, year, month)
    
    # 3. Respuesta (Output)
    return render(request, 'finances/summary.html', context)