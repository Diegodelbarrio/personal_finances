from django.urls import path
from . import views

urlpatterns = [
    path('', views.summary, name='summary'),
    path('transactions/new/', views.create_transaction, name='create_transaction'),
    path(
        'transactions/import/',
        views.import_transactions_csv,
        name='import_transactions_csv',
    ),
    path(
        'transactions/<int:transaction_id>/edit/',
        views.edit_transaction,
        name='edit_transaction',
    ),
    path(
        'transactions/<int:transaction_id>/delete/',
        views.delete_transaction,
        name='delete_transaction',
    ),
    path('locations/new/', views.create_location, name='create_location'),
    path('categories/', views.manage_categories, name='manage_categories'),
    path('categories/new/', views.create_category, name='create_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('subcategories/new/', views.create_subcategory, name='create_subcategory'),
    path(
        'subcategories/<int:subcategory_id>/edit/',
        views.edit_subcategory,
        name='edit_subcategory',
    ),
]
