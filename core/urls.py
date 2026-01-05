from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('home/', views.home, name='home'),
    path('tools/compound-interest/', views.compound_interest_calculator, name='compound_interest'),
]