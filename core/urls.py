from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('home/', views.home, name='home'),
    path('tools/compound-interest/', views.compound_interest_calculator, name='compound_interest'),
    path('tools/market_data/', views.investment_dashboard, name='market_data'),
    path('tools/live_market_data/', views.live_market_dashboard, name='live_market_data'),
    path(
        'tools/csv-templates/<slug:template_key>/',
        views.download_csv_template,
        name='download_csv_template',
    ),
]
