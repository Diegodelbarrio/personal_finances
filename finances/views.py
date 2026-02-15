from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Abs
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from core.forms import CSVUploadForm
from core.services.csv_import import (
    FINANCE_TRANSACTIONS_CSV_FORMAT,
    import_finance_transactions_csv,
)

from .forms import (
    CategoryForm,
    DefaultCategoryPresetForm,
    LocationForm,
    SubCategoryForm,
    TransactionForm,
)
from .models import Category, SubCategory, Transaction
from .services.selectors import get_summary_page_data


def _normalize_transactions_for_subcategories(subcategories_qs, transaction_type):
    amount_field = DecimalField(max_digits=12, decimal_places=2)
    transactions_qs = Transaction.objects.filter(subcategory__in=subcategories_qs)

    if transaction_type == "INCOME":
        return transactions_qs.update(amount=Abs(F("amount")))

    return transactions_qs.update(
        amount=ExpressionWrapper(-Abs(F("amount")), output_field=amount_field)
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


def _create_subcategories_for_category(user, category, subcategories_data):
    existing_names = {
        name.casefold()
        for name in SubCategory.objects.filter(
            user=user,
            parent_category=category,
        ).values_list("name", flat=True)
    }
    to_create = []

    for item in subcategories_data:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
            is_essential = bool(item.get("is_essential"))
        else:
            name = str(item).strip()
            is_essential = False

        if not name:
            continue

        normalized = name.casefold()
        if normalized in existing_names:
            continue
        existing_names.add(normalized)
        to_create.append(
            SubCategory(
                user=user,
                parent_category=category,
                name=name,
                is_essential=is_essential,
            )
        )

    if to_create:
        SubCategory.objects.bulk_create(to_create)
    return len(to_create)


def _build_default_setup_state(form):
    if form.is_bound:
        selected_categories = set(form.data.getlist("category_keys"))
        selected_subcategories = set(form.data.getlist("subcategory_keys"))
    else:
        selected_categories = {category["key"] for category in form.blueprints}
        selected_subcategories = {
            subcategory["key"]
            for category in form.blueprints
            for subcategory in category["subcategories"]
        }

    return selected_categories, selected_subcategories


def _create_default_categories(user, payload):
    created_categories = 0
    created_subcategories = 0

    for category_data in payload:
        if Category.objects.filter(user=user, name__iexact=category_data["name"]).exists():
            continue

        category = Category.objects.create(
            user=user,
            name=category_data["name"],
            transaction_type=category_data["transaction_type"],
            expense_type=category_data["expense_type"],
            is_housing=category_data["is_housing"],
        )
        created_categories += 1
        created_subcategories += _create_subcategories_for_category(
            user,
            category,
            category_data["subcategories"],
        )

    return created_categories, created_subcategories


@login_required
def summary(request):
    # 1. Entrada de datos (Input)
    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    
    # 2. Lógica de negocio/selección (Process)
    context = get_summary_page_data(request.user, year, month)
    context["current_path"] = request.get_full_path()
    
    # 3. Respuesta (Output)
    return render(request, 'finances/summary.html', context)


@login_required
def manage_categories(request):
    user_has_categories = Category.objects.filter(user=request.user).exists()
    default_setup_form = DefaultCategoryPresetForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete_category":
            category_id = request.POST.get("category_id")
            category = get_object_or_404(Category, id=category_id, user=request.user)
            try:
                category.delete()
                messages.success(
                    request,
                    "Category deleted successfully.",
                    extra_tags="finances_categories",
                )
            except ProtectedError:
                messages.error(
                    request,
                    "This category cannot be deleted because it has subcategories with linked transactions.",
                    extra_tags="finances_categories",
                )
            return redirect("manage_categories")
        elif action == "delete_subcategory":
            subcategory_id = request.POST.get("subcategory_id")
            subcategory = get_object_or_404(
                SubCategory,
                id=subcategory_id,
                user=request.user,
            )
            try:
                subcategory.delete()
                messages.success(
                    request,
                    "Subcategory deleted successfully.",
                    extra_tags="finances_categories",
                )
            except ProtectedError:
                messages.error(
                    request,
                    "This subcategory cannot be deleted because it has linked transactions.",
                    extra_tags="finances_categories",
                )
            return redirect("manage_categories")
        elif action == "create_default_categories":
            if user_has_categories:
                messages.warning(
                    request,
                    "Default categories can only be created when your category list is empty.",
                    extra_tags="finances_categories",
                )
                return redirect("manage_categories")

            default_setup_form = DefaultCategoryPresetForm(request.POST)
            if default_setup_form.is_valid():
                with db_transaction.atomic():
                    created_categories, created_subcategories = _create_default_categories(
                        request.user,
                        default_setup_form.get_creation_payload(),
                    )

                if created_categories:
                    messages.success(
                        request,
                        (
                            "Default categories created successfully: "
                            f"{created_categories} categories and {created_subcategories} subcategories."
                        ),
                        extra_tags="finances_categories",
                    )
                else:
                    messages.info(
                        request,
                        "No categories were created because matching names already exist.",
                        extra_tags="finances_categories",
                    )
                return redirect("manage_categories")

            messages.error(
                request,
                "Please review your default category selection.",
                extra_tags="finances_categories",
            )

    categories = (
        Category.objects.filter(user=request.user)
        .annotate(
            subcategories_count=Count("subcategories", distinct=True),
            transactions_count=Count("subcategories__transactions", distinct=True),
        )
        .order_by("name")
    )

    subcategories = (
        SubCategory.objects.filter(user=request.user)
        .select_related("parent_category")
        .annotate(transactions_count=Count("transactions", distinct=True))
        .order_by("parent_category__name", "name")
    )

    selected_category_keys, selected_subcategory_keys = _build_default_setup_state(
        default_setup_form
    )

    context = {
        "categories": categories,
        "subcategories": subcategories,
        "category_filter_choices": Category.objects.filter(user=request.user).order_by("name"),
        "has_categories": categories.exists(),
        "default_setup_form": default_setup_form,
        "default_category_options": default_setup_form.blueprints,
        "default_required_category_keys": default_setup_form.required_category_keys,
        "default_selected_category_keys": selected_category_keys,
        "default_selected_subcategory_keys": selected_subcategory_keys,
        "current_path": request.get_full_path(),
    }

    return render(request, "finances/manage_categories.html", context)


@login_required
def create_category(request):
    next_url = _get_safe_next_url(request, "manage_categories")
    if request.method == "POST":
        form = CategoryForm(request.POST, user=request.user, allow_subcategories=True)
        if form.is_valid():
            with db_transaction.atomic():
                category = form.save()
                created_subcategories = _create_subcategories_for_category(
                    request.user,
                    category,
                    form.get_subcategory_names(),
                )

            if created_subcategories:
                success_message = (
                    f"Category created successfully with {created_subcategories} subcategories."
                )
            else:
                success_message = "Category created successfully."
            messages.success(
                request,
                success_message,
                extra_tags="finances_categories",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_categories",
        )
    else:
        form = CategoryForm(user=request.user, allow_subcategories=True)

    return render(
        request,
        "finances/category_form.html",
        {
            "form": form,
            "is_edit": False,
            "next_url": next_url,
        },
    )


@login_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    current_transaction_type = category.transaction_type
    next_url = _get_safe_next_url(request, "manage_categories")

    if request.method == "POST":
        form = CategoryForm(
            request.POST,
            instance=category,
            user=request.user,
            lock_name=True,
        )
        if form.is_valid():
            with db_transaction.atomic():
                updated_category = form.save()
                updated_transactions = 0
                if current_transaction_type != updated_category.transaction_type:
                    updated_transactions = _normalize_transactions_for_subcategories(
                        SubCategory.objects.filter(parent_category=updated_category),
                        updated_category.transaction_type,
                    )

            messages.success(
                request,
                "Category updated successfully.",
                extra_tags="finances_categories",
            )
            if updated_transactions:
                messages.info(
                    request,
                    f"{updated_transactions} transactions were updated to match the new category type.",
                    extra_tags="finances_categories",
                )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_categories",
        )
    else:
        form = CategoryForm(instance=category, user=request.user, lock_name=True)

    return render(
        request,
        "finances/category_form.html",
        {
            "form": form,
            "is_edit": True,
            "category": category,
            "next_url": next_url,
        },
    )


@login_required
def create_subcategory(request):
    next_url = _get_safe_next_url(request, "manage_categories")
    if request.method == "POST":
        form = SubCategoryForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Subcategory created successfully.",
                extra_tags="finances_categories",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_categories",
        )
    else:
        form = SubCategoryForm(user=request.user)

    return render(
        request,
        "finances/subcategory_form.html",
        {
            "form": form,
            "is_edit": False,
            "next_url": next_url,
            "current_path": request.get_full_path(),
        },
    )


@login_required
def edit_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id, user=request.user)
    current_transaction_type = subcategory.parent_category.transaction_type
    next_url = _get_safe_next_url(request, "manage_categories")

    if request.method == "POST":
        form = SubCategoryForm(
            request.POST,
            instance=subcategory,
            user=request.user,
            lock_name=True,
        )
        if form.is_valid():
            with db_transaction.atomic():
                updated_subcategory = form.save()
                updated_transactions = 0
                updated_transaction_type = updated_subcategory.parent_category.transaction_type
                if current_transaction_type != updated_transaction_type:
                    updated_transactions = _normalize_transactions_for_subcategories(
                        SubCategory.objects.filter(id=updated_subcategory.id),
                        updated_transaction_type,
                    )

            messages.success(
                request,
                "Subcategory updated successfully.",
                extra_tags="finances_categories",
            )
            if updated_transactions:
                messages.info(
                    request,
                    f"{updated_transactions} transactions were updated to match the new parent category type.",
                    extra_tags="finances_categories",
                )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_categories",
        )
    else:
        form = SubCategoryForm(instance=subcategory, user=request.user, lock_name=True)

    return render(
        request,
        "finances/subcategory_form.html",
        {
            "form": form,
            "is_edit": True,
            "subcategory": subcategory,
            "next_url": next_url,
            "current_path": request.get_full_path(),
        },
    )


@login_required
def create_location(request):
    next_url = _get_safe_next_url(request, "summary")
    if request.method == "POST":
        form = LocationForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Location created successfully.",
                extra_tags="finances_transactions",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_transactions",
        )
    else:
        form = LocationForm(user=request.user)

    return render(
        request,
        "finances/location_form.html",
        {
            "form": form,
            "next_url": next_url,
        },
    )


@login_required
def create_transaction(request):
    next_url = _get_safe_next_url(request, "summary")
    if request.method == "POST":
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Transaction saved successfully.",
                extra_tags="finances_transactions",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_transactions",
        )
    else:
        form = TransactionForm(user=request.user)

    return render(
        request,
        "finances/transaction_form.html",
        {
            "form": form,
            "is_edit": False,
            "next_url": next_url,
            "return_to_form_url": request.get_full_path(),
            "has_subcategories": form.fields["subcategory"].queryset.exists(),
        },
    )


@login_required
def edit_transaction(request, transaction_id):
    tx = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    next_url = _get_safe_next_url(request, "summary")
    if request.method == "POST":
        form = TransactionForm(request.POST, instance=tx, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Transaction updated successfully.",
                extra_tags="finances_transactions",
            )
            return redirect(next_url)
        messages.error(
            request,
            "Please review the form fields.",
            extra_tags="finances_transactions",
        )
    else:
        form = TransactionForm(instance=tx, user=request.user)

    return render(
        request,
        "finances/transaction_form.html",
        {
            "form": form,
            "is_edit": True,
            "transaction": tx,
            "next_url": next_url,
            "return_to_form_url": request.get_full_path(),
            "has_subcategories": form.fields["subcategory"].queryset.exists(),
        },
    )


@login_required
def delete_transaction(request, transaction_id):
    tx = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    next_url = _get_safe_next_url(request, "summary")

    if request.method == "POST":
        tx.delete()
        messages.success(
            request,
            "Transaction deleted successfully.",
            extra_tags="finances_transactions",
        )
        return redirect(next_url)

    return render(
        request,
        "finances/transaction_confirm_delete.html",
        {
            "transaction": tx,
            "next_url": next_url,
        },
    )


@login_required
def import_transactions_csv(request):
    next_url = _get_safe_next_url(request, "summary")

    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = import_finance_transactions_csv(
                request.user,
                form.cleaned_data["csv_file"],
            )
            if result.success:
                summary_parts = [f"{result.created} created"]
                if result.skipped:
                    summary_parts.append(f"{result.skipped} skipped (already existed)")
                messages.success(
                    request,
                    f"Finance CSV imported successfully ({', '.join(summary_parts)}).",
                    extra_tags="finances_transactions",
                )
                return redirect(next_url)

            for error in result.errors[:10]:
                messages.error(request, error, extra_tags="finances_transactions")
            if len(result.errors) > 10:
                messages.error(
                    request,
                    f"{len(result.errors) - 10} more validation errors were found.",
                    extra_tags="finances_transactions",
                )
        else:
            messages.error(
                request,
                "Please upload a valid CSV file.",
                extra_tags="finances_transactions",
            )
    else:
        form = CSVUploadForm()

    context = {
        "form": form,
        "page_title": "Import Finance Transactions",
        "page_subtitle": (
            "Upload a CSV with validated format. Data is only imported when all rows are valid."
        ),
        "next_url": next_url,
        "submit_label": "Import CSV",
        "required_columns": FINANCE_TRANSACTIONS_CSV_FORMAT["required_columns"],
        "optional_columns": FINANCE_TRANSACTIONS_CSV_FORMAT["optional_columns"],
        "columns_help": FINANCE_TRANSACTIONS_CSV_FORMAT["columns_help"],
        "sample_csv": FINANCE_TRANSACTIONS_CSV_FORMAT["sample_csv"],
        "template_key": "finance-transactions",
        "message_tag": "finances_transactions",
    }
    return render(request, "shared/csv_import_form.html", context)
