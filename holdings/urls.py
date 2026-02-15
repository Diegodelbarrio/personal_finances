from django.urls import path

from . import views

app_name = "holdings"

urlpatterns = [
    path("snapshots/import/", views.import_snapshots_csv, name="import_snapshots_csv"),
]
