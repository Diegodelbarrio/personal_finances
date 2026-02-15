from django.urls import path
from . import views

app_name = 'investments'

urlpatterns = [
    path('', views.investments_dashboard, name='investment_dashboard'),
    path('assets/new/', views.create_asset, name='create_asset'),
    path('transactions/new/', views.create_transaction, name='create_transaction'),
    path('transactions/import/', views.import_transactions_csv, name='import_transactions_csv'),
    path('history/new/', views.create_asset_history, name='create_asset_history'),
    path('history/import/', views.import_asset_history_csv, name='import_asset_history_csv'),
]
