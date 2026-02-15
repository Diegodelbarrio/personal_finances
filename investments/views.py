from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

from core.forms import CSVUploadForm
from core.services.csv_import import (
    INVESTMENT_HISTORY_CSV_FORMAT,
    INVESTMENT_TRANSACTIONS_CSV_FORMAT,
    import_investment_history_csv,
    import_investment_transactions_csv,
)
from investments.forms import AssetForm, AssetHistoryForm, InvestmentTransactionForm
from investments.services.api import get_portfolio_overview
from investments.services.history import (
    get_performance_history,
    get_allocation_chart,
    get_monthly_contributions_bar,
)


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
def investments_dashboard(request):
    portfolio_data = get_portfolio_overview(request.user)

    allocation_labels, allocation_data = get_allocation_chart(
        portfolio_data["chart_assets"]
    )

    bar_labels, bar_datasets = get_monthly_contributions_bar(request.user)

    context = {
        **portfolio_data,
        "performance_history": get_performance_history(request.user),
        "allocation_labels": allocation_labels,
        "allocation_data": allocation_data,
        "bar_labels": bar_labels,
        "bar_datasets": bar_datasets,
        "current_path": request.get_full_path(),
    }

    return render(request, "investments/investment_dashboard.html", context)


@login_required
def create_asset(request):
    next_url = _get_safe_next_url(request, "investments:investment_dashboard")
    if request.method == "POST":
        form = AssetForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Asset created successfully.",
                extra_tags="investments_assets",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="investments_assets",
        )
    else:
        form = AssetForm(user=request.user)

    return render(
        request,
        "investments/asset_form.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )


@login_required
def create_transaction(request):
    next_url = _get_safe_next_url(request, "investments:investment_dashboard")
    if request.method == "POST":
        form = InvestmentTransactionForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Investment transaction saved successfully.",
                extra_tags="investments_transactions",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="investments_transactions",
        )
    else:
        form = InvestmentTransactionForm(user=request.user)

    return render(
        request,
        "investments/transaction_form.html",
        {
            "form": form,
            "next_url": next_url,
            "return_to_form_url": request.get_full_path(),
            "has_assets": form.fields["asset"].queryset.exists(),
        },
    )


@login_required
def create_asset_history(request):
    next_url = _get_safe_next_url(request, "investments:investment_dashboard")
    if request.method == "POST":
        form = AssetHistoryForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Asset snapshot saved successfully.",
                extra_tags="investments_history",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="investments_history",
        )
    else:
        form = AssetHistoryForm(user=request.user)

    return render(
        request,
        "investments/asset_history_form.html",
        {
            "form": form,
            "next_url": next_url,
            "return_to_form_url": request.get_full_path(),
            "has_assets": form.fields["asset"].queryset.exists(),
        },
    )


@login_required
def import_transactions_csv(request):
    next_url = _get_safe_next_url(request, "investments:investment_dashboard")

    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = import_investment_transactions_csv(
                request.user,
                form.cleaned_data["csv_file"],
            )
            if result.success:
                summary_parts = [f"{result.created} created"]
                if result.skipped:
                    summary_parts.append(f"{result.skipped} skipped (already existed)")
                messages.success(
                    request,
                    f"Investment transactions CSV imported successfully ({', '.join(summary_parts)}).",
                    extra_tags="investments_transactions",
                )
                return redirect(next_url)

            for error in result.errors[:10]:
                messages.error(request, error, extra_tags="investments_transactions")
            if len(result.errors) > 10:
                messages.error(
                    request,
                    f"{len(result.errors) - 10} more validation errors were found.",
                    extra_tags="investments_transactions",
                )
        else:
            messages.error(
                request,
                "Please upload a valid CSV file.",
                extra_tags="investments_transactions",
            )
    else:
        form = CSVUploadForm()

    context = {
        "form": form,
        "page_title": "Import Investment Transactions",
        "page_subtitle": (
            "Upload a CSV with validated format. Data is only imported when all rows are valid."
        ),
        "next_url": next_url,
        "submit_label": "Import CSV",
        "required_columns": INVESTMENT_TRANSACTIONS_CSV_FORMAT["required_columns"],
        "optional_columns": INVESTMENT_TRANSACTIONS_CSV_FORMAT["optional_columns"],
        "columns_help": INVESTMENT_TRANSACTIONS_CSV_FORMAT["columns_help"],
        "sample_csv": INVESTMENT_TRANSACTIONS_CSV_FORMAT["sample_csv"],
        "template_key": "investment-transactions",
        "message_tag": "investments_transactions",
    }
    return render(request, "shared/csv_import_form.html", context)


@login_required
def import_asset_history_csv(request):
    next_url = _get_safe_next_url(request, "investments:investment_dashboard")

    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = import_investment_history_csv(
                request.user,
                form.cleaned_data["csv_file"],
            )
            if result.success:
                summary_parts = [f"{result.created} created"]
                if result.updated:
                    summary_parts.append(f"{result.updated} updated")
                if result.skipped:
                    summary_parts.append(f"{result.skipped} skipped (same value)")
                messages.success(
                    request,
                    f"Investment history CSV imported successfully ({', '.join(summary_parts)}).",
                    extra_tags="investments_history",
                )
                return redirect(next_url)

            for error in result.errors[:10]:
                messages.error(request, error, extra_tags="investments_history")
            if len(result.errors) > 10:
                messages.error(
                    request,
                    f"{len(result.errors) - 10} more validation errors were found.",
                    extra_tags="investments_history",
                )
        else:
            messages.error(
                request,
                "Please upload a valid CSV file.",
                extra_tags="investments_history",
            )
    else:
        form = CSVUploadForm()

    context = {
        "form": form,
        "page_title": "Import Investment History",
        "page_subtitle": (
            "Upload asset valuation snapshots in CSV format. The import is all-or-nothing."
        ),
        "next_url": next_url,
        "submit_label": "Import CSV",
        "required_columns": INVESTMENT_HISTORY_CSV_FORMAT["required_columns"],
        "optional_columns": INVESTMENT_HISTORY_CSV_FORMAT["optional_columns"],
        "columns_help": INVESTMENT_HISTORY_CSV_FORMAT["columns_help"],
        "sample_csv": INVESTMENT_HISTORY_CSV_FORMAT["sample_csv"],
        "template_key": "investment-history",
        "message_tag": "investments_history",
    }
    return render(request, "shared/csv_import_form.html", context)
