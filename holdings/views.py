from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.forms import CSVUploadForm
from core.services.csv_import import (
    HOLDING_SNAPSHOTS_CSV_FORMAT,
    import_holding_snapshots_csv,
)
from holdings.forms import BankConnectionStartForm
from holdings.models import BankConnection
from holdings.services.bank_sync import (
    BankSyncError,
    complete_bank_connection as complete_bank_connection_service,
    create_bank_connection,
    list_bank_institutions,
    refresh_bank_connection,
    sync_bank_connection,
)
from holdings.services.history import get_net_worth_evolution

__all__ = [
    "bank_sync_dashboard",
    "complete_bank_connection",
    "delete_bank_connection_view",
    "get_net_worth_evolution",
    "import_snapshots_csv",
    "start_bank_connection",
    "sync_bank_connection_view",
]


def _get_safe_next_url(request, fallback_name):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return resolve_url(fallback_name)


@login_required
def import_snapshots_csv(request):
    next_url = _get_safe_next_url(request, "reports:report_holdings")

    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = import_holding_snapshots_csv(
                request.user,
                form.cleaned_data["csv_file"],
            )
            if result.success:
                summary_parts = [f"{result.created} snapshots created"]
                if result.updated:
                    summary_parts.append(f"{result.updated} snapshots updated")
                if result.details.get("accounts_created"):
                    summary_parts.append(
                        f"{result.details['accounts_created']} accounts created"
                    )
                messages.success(
                    request,
                    f"Holdings CSV imported successfully ({', '.join(summary_parts)}).",
                    extra_tags="reports_holdings",
                )
                return redirect(next_url)

            for error in result.errors[:10]:
                messages.error(request, error, extra_tags="reports_holdings")
            if len(result.errors) > 10:
                messages.error(
                    request,
                    f"{len(result.errors) - 10} more validation errors were found.",
                    extra_tags="reports_holdings",
                )
        else:
            messages.error(
                request,
                "Please upload a valid CSV file.",
                extra_tags="reports_holdings",
            )
    else:
        form = CSVUploadForm()

    context = {
        "form": form,
        "page_title": "Import Holdings Snapshots",
        "page_subtitle": (
            "Upload monthly balance snapshots in CSV format. Data is imported only if all rows are valid."
        ),
        "next_url": next_url,
        "submit_label": "Import CSV",
        "required_columns": HOLDING_SNAPSHOTS_CSV_FORMAT["required_columns"],
        "optional_columns": HOLDING_SNAPSHOTS_CSV_FORMAT["optional_columns"],
        "columns_help": HOLDING_SNAPSHOTS_CSV_FORMAT["columns_help"],
        "sample_csv": HOLDING_SNAPSHOTS_CSV_FORMAT["sample_csv"],
        "template_key": "holding-snapshots",
        "message_tag": "reports_holdings",
    }
    return render(request, "shared/csv_import_form.html", context)


@login_required
def bank_sync_dashboard(request):
    provider = (request.GET.get("provider") or settings.BANK_SYNC_PROVIDER).upper()
    country_code = (request.GET.get("country") or settings.BANK_SYNC_COUNTRY_CODE).upper()
    institution_choices = []
    institution_lookup = {}

    if settings.BANK_SYNC_ENABLED and provider == BankConnection.PROVIDER_YAPILY:
        try:
            institutions = list_bank_institutions(provider, country_code=country_code)
        except BankSyncError as exc:
            messages.warning(request, str(exc), extra_tags="bank_sync")
            institutions = []
        institution_choices = [
            (
                institution.get("id", ""),
                institution.get("fullName") or institution.get("name") or institution.get("id", ""),
            )
            for institution in institutions
            if institution.get("id")
        ]
        institution_lookup = {
            institution.get("id"): institution.get("fullName") or institution.get("name")
            for institution in institutions
            if institution.get("id")
        }

    connections = (
        BankConnection.objects
        .filter(user=request.user)
        .prefetch_related("bank_accounts")
        .order_by("-created_at")
    )
    context = {
        "form": BankConnectionStartForm(
            initial={"provider": provider, "country_code": country_code},
            institution_choices=institution_choices,
        ),
        "connections": connections,
        "bank_sync_enabled": settings.BANK_SYNC_ENABLED,
        "institution_count": len(institution_choices),
        "institution_lookup": institution_lookup,
        "institutions_loaded": provider == BankConnection.PROVIDER_YAPILY,
        "page_title": "Bank Sync",
    }
    return render(request, "holdings/bank_sync.html", context)


@login_required
@require_POST
def start_bank_connection(request):
    form = BankConnectionStartForm(request.POST)
    if not form.is_valid():
        connections = BankConnection.objects.filter(user=request.user).order_by("-created_at")
        return render(
            request,
            "holdings/bank_sync.html",
            {
                "form": form,
                "connections": connections,
                "bank_sync_enabled": settings.BANK_SYNC_ENABLED,
                "institution_count": 0,
                "institution_lookup": {},
                "institutions_loaded": False,
                "page_title": "Bank Sync",
            },
            status=400,
        )

    callback_url = request.build_absolute_uri(
        resolve_url(
            "holdings:bank_sync_callback",
            reference="00000000-0000-0000-0000-000000000000",
        )
    ).replace("00000000-0000-0000-0000-000000000000", "{reference}")

    institution_name = form.cleaned_data["institution_name"]
    if (
        form.cleaned_data["provider"] == BankConnection.PROVIDER_YAPILY
        and form.cleaned_data["institution_id"]
        and not institution_name
    ):
        institution_name = _get_institution_name(
            form.cleaned_data["provider"],
            form.cleaned_data["country_code"],
            form.cleaned_data["institution_id"],
        )

    try:
        connection = create_bank_connection(
            user=request.user,
            provider_key=form.cleaned_data["provider"],
            institution_id=form.cleaned_data["institution_id"],
            institution_name=institution_name,
            redirect_url=callback_url,
            country_code=form.cleaned_data["country_code"],
        )
    except BankSyncError as exc:
        messages.error(request, str(exc), extra_tags="bank_sync")
        return redirect("holdings:bank_sync")

    if connection.provider == BankConnection.PROVIDER_MOCK:
        try:
            result = sync_bank_connection(connection)
        except BankSyncError as exc:
            messages.error(request, str(exc), extra_tags="bank_sync")
        else:
            messages.success(
                request,
                (
                    f"Mock bank sync completed: {result.accounts_seen} accounts, "
                    f"{result.snapshots_created} snapshots created, "
                    f"{result.snapshots_updated} snapshots updated."
                ),
                extra_tags="bank_sync",
            )
        return redirect("holdings:bank_sync")

    if connection.consent_url:
        return redirect(connection.consent_url)

    messages.info(request, "Bank connection created.", extra_tags="bank_sync")
    return redirect("holdings:bank_sync")


def _get_institution_name(provider, country_code, institution_id):
    try:
        institutions = list_bank_institutions(provider, country_code=country_code)
    except BankSyncError:
        return institution_id

    for institution in institutions:
        if institution.get("id") == institution_id:
            return institution.get("fullName") or institution.get("name") or institution_id
    return institution_id


@login_required
def complete_bank_connection(request, reference):
    connection = get_object_or_404(BankConnection, user=request.user, reference=reference)
    try:
        if connection.provider == BankConnection.PROVIDER_YAPILY:
            complete_bank_connection_service(connection, request.GET)
        else:
            refresh_bank_connection(connection)
        if connection.status == BankConnection.STATUS_LINKED:
            result = sync_bank_connection(connection)
            messages.success(
                request,
                (
                    f"Bank connection linked: {result.accounts_seen} accounts synced "
                    f"for {result.snapshot_date}."
                ),
                extra_tags="bank_sync",
            )
        else:
            messages.info(
                request,
                f"Connection status is {connection.get_status_display()}.",
                extra_tags="bank_sync",
            )
    except BankSyncError as exc:
        messages.error(request, str(exc), extra_tags="bank_sync")
    return redirect("holdings:bank_sync")


@login_required
@require_POST
def sync_bank_connection_view(request, connection_id):
    connection = get_object_or_404(BankConnection, id=connection_id, user=request.user)
    try:
        result = sync_bank_connection(connection)
    except BankSyncError as exc:
        messages.error(request, str(exc), extra_tags="bank_sync")
    else:
        messages.success(
            request,
            (
                f"Synced {result.accounts_seen} accounts: "
                f"{result.snapshots_created} snapshots created, "
                f"{result.snapshots_updated} snapshots updated."
            ),
            extra_tags="bank_sync",
        )
    return redirect("holdings:bank_sync")


@login_required
@require_POST
def delete_bank_connection_view(request, connection_id):
    connection = get_object_or_404(BankConnection, id=connection_id, user=request.user)
    institution = (
        connection.institution_name
        or connection.institution_id
        or connection.get_provider_display()
    )
    connection.delete()
    messages.success(
        request,
        f"Deleted bank connection for {institution}. Existing accounts and snapshots were kept.",
        extra_tags="bank_sync",
    )
    return redirect("holdings:bank_sync")
