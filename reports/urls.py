from django.urls import path
from . import views

app_name = 'reports'
urlpatterns = [
    path('finances/', views.financial_report, name='report_finance'),
    path('investments/', views.investment_report, name='report_investments'),
    path('holdings/', views.holdings_report, name='report_holdings'),
]