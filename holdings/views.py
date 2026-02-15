from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

from core.forms import CSVUploadForm
from core.services.csv_import import (
    HOLDING_SNAPSHOTS_CSV_FORMAT,
    import_holding_snapshots_csv,
)
from holdings.services.history import get_net_worth_evolution

__all__ = ["get_net_worth_evolution", "import_snapshots_csv"]


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
