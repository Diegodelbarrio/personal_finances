from django.urls import path

from . import views

app_name = "holdings"

urlpatterns = [
    path("bank-sync/", views.bank_sync_dashboard, name="bank_sync"),
    path("bank-sync/start/", views.start_bank_connection, name="bank_sync_start"),
    path(
        "bank-sync/callback/<uuid:reference>/",
        views.complete_bank_connection,
        name="bank_sync_callback",
    ),
    path(
        "bank-sync/<int:connection_id>/sync/",
        views.sync_bank_connection_view,
        name="bank_sync_connection",
    ),
    path(
        "bank-sync/<int:connection_id>/delete/",
        views.delete_bank_connection_view,
        name="bank_sync_delete_connection",
    ),
    path("snapshots/import/", views.import_snapshots_csv, name="import_snapshots_csv"),
]
