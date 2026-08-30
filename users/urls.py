from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("export/", views.export_account_data, name="export_account_data"),
    path("delete/", views.delete_account, name="delete_account"),
]
