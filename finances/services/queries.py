from django.db.models.functions import ExtractYear, ExtractMonth
from ..models import Transaction

def get_base_transaction_qs(user):
    return Transaction.objects.filter(user=user).select_related('subcategory__parent_category')

def get_available_years(user):
    return get_base_transaction_qs(user).annotate(
        y=ExtractYear('date')
    ).values_list('y', flat=True).distinct().order_by('-y')

def get_available_months_for_year(user, year):
    return get_base_transaction_qs(user).filter(
        date__year=year
    ).annotate(
        m=ExtractMonth('date')
    ).values_list('m', flat=True).distinct().order_by('m')