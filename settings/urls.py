from django.urls import path
from settings.views import settings_home

app_name = 'settings'

urlpatterns = [
    path('', settings_home, name='settings_home'),
]