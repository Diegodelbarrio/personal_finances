from django.urls import path
from . import views

urlpatterns = [
    path('', views.investments_dashboard, name='investment_dashboard'),
]