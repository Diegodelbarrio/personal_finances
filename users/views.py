import json

from allauth.account.models import EmailAddress
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Count
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone as django_timezone
from django.utils.translation import activate as activate_language
from django.utils.text import slugify
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from settings.services.api import SettingsService

from finances.models import Category, Location, SubCategory, Transaction as FinanceTransaction
from holdings.models import AccountBalanceSnapshot, BankAccount
from investments.models import Asset, AssetHistory, Transaction as InvestmentTransaction
from settings.models import UserSettings

from .forms import AccountDeletionForm, ProfileForm, ProfilePreferencesForm


User = get_user_model()


def _profile_display_name(user):
    full_name = user.get_full_name().strip()
    return full_name or user.username


def _profile_initials(user):
    display_name = _profile_display_name(user)
    parts = [part for part in display_name.split() if part]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return display_name[:2].upper()


def _account_email_status(user):
    primary_address = (
        EmailAddress.objects
        .filter(user=user, primary=True)
        .order_by("-verified", "email")
        .first()
    )
    selected_address = primary_address
    if selected_address is None and user.email:
        selected_address = (
            EmailAddress.objects
            .filter(user=user, email__iexact=user.email)
            .order_by("-primary", "-verified")
            .first()
        )

    if selected_address:
        return {
            "email": selected_address.email,
            "is_verified": selected_address.verified,
            "is_primary": selected_address.primary,
            "label": "Verified" if selected_address.verified else "Needs verification",
            "tone": "success" if selected_address.verified else "warning",
        }

    return {
        "email": user.email,
        "is_verified": False,
        "is_primary": False,
        "label": "Not managed",
        "tone": "muted",
    }


def _workspace_counts(user):
    counts = (
        User.objects
        .filter(pk=user.pk)
        .annotate(
            finances_transactions_count=Count("finances_transactions", distinct=True),
            assets_count=Count("assets", distinct=True),
            investment_transactions_count=Count("investment_transactions", distinct=True),
            bank_accounts_count=Count("accounts", distinct=True),
        )
        .values(
            "finances_transactions_count",
            "assets_count",
            "investment_transactions_count",
            "bank_accounts_count",
        )
        .get()
    )
    return {
        "finances_transactions": counts["finances_transactions_count"],
        "assets": counts["assets_count"],
        "investment_transactions": counts["investment_transactions_count"],
        "bank_accounts": counts["bank_accounts_count"],
    }


@login_required
def profile(request):
    user_settings = SettingsService.get_settings(request.user)

    if request.method == "POST":
        profile_form = ProfileForm(
            request.POST,
            request.FILES,
            instance=request.user,
            prefix="profile",
        )
        preferences_form = ProfilePreferencesForm(
            request.POST,
            instance=user_settings,
            prefix="prefs",
        )

        if profile_form.is_valid() and preferences_form.is_valid():
            if not profile_form.has_changed() and not preferences_form.has_changed():
                messages.info(
                    request,
                    "No changes detected. Nothing to update.",
                    extra_tags="users_profile",
                )
                return redirect("users:profile")

            with db_transaction.atomic():
                if profile_form.has_changed():
                    profile_form.save()
                preferences = (
                    preferences_form.save()
                    if preferences_form.has_changed()
                    else user_settings
                )

            activate_language(preferences.language_code)
            request.LANGUAGE_CODE = preferences.language_code
            try:
                django_timezone.activate(ZoneInfo(preferences.timezone))
            except ZoneInfoNotFoundError:
                django_timezone.deactivate()
            messages.success(
                request,
                "Profile updated successfully.",
                extra_tags="users_profile",
            )
            return redirect("users:profile")

        messages.error(
            request,
            "Please correct the highlighted fields.",
            extra_tags="users_profile",
        )
    else:
        profile_form = ProfileForm(instance=request.user, prefix="profile")
        preferences_form = ProfilePreferencesForm(instance=user_settings, prefix="prefs")

    workspace_counts = _workspace_counts(request.user)
    email_status = _account_email_status(request.user)
    context = {
        "profile_form": profile_form,
        "preferences_form": preferences_form,
        "profile_meta": {
            "display_name": _profile_display_name(request.user),
            "initials": _profile_initials(request.user),
            "email_status": email_status,
            "completion_items": [
                {
                    "label": "Name",
                    "is_complete": bool(request.user.first_name and request.user.last_name),
                },
                {
                    "label": "Email",
                    "is_complete": bool(request.user.email),
                },
                {
                    "label": "Avatar",
                    "is_complete": bool(request.user.avatar),
                },
                {
                    "label": "Verified email",
                    "is_complete": email_status["is_verified"],
                },
            ],
        },
        "profile_stats": {
            "member_since": request.user.date_joined,
            "last_login": request.user.last_login,
            "main_currency": user_settings.main_currency,
            **workspace_counts,
        },
    }
    return render(request, "users/profile.html", context)


def _ordered_values(queryset, *fields):
    return list(queryset.order_by("id").values(*fields))


@login_required
def export_account_data(request):
    user = request.user
    payload = {
        "format": "finorbit-account-export-v1",
        "exported_at": django_timezone.now(),
        "profile": {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "avatar_file": user.avatar.name if user.avatar else None,
        },
        "email_addresses": _ordered_values(
            EmailAddress.objects.filter(user=user),
            "email",
            "verified",
            "primary",
        ),
        "settings": _ordered_values(
            UserSettings.objects.filter(user=user),
            "annual_savings_target",
            "monthly_budget",
            "net_worth_target",
            "savings_rate_target",
            "target_date",
            "retirement_age",
            "main_currency",
            "financial_profile",
            "emergency_fund_months",
            "language_code",
            "timezone",
            "updated_at",
        ),
        "finances": {
            "categories": _ordered_values(
                Category.objects.filter(user=user),
                "id",
                "name",
                "transaction_type",
                "expense_type",
                "is_housing",
            ),
            "subcategories": _ordered_values(
                SubCategory.objects.filter(user=user),
                "id",
                "parent_category_id",
                "name",
                "budget_group",
                "expense_nature",
                "is_essential",
            ),
            "locations": _ordered_values(
                Location.objects.filter(user=user),
                "id",
                "name",
            ),
            "transactions": _ordered_values(
                FinanceTransaction.objects.filter(user=user),
                "id",
                "date",
                "amount",
                "description",
                "subcategory_id",
                "location_id",
            ),
        },
        "investments": {
            "assets": _ordered_values(
                Asset.objects.filter(user=user),
                "id",
                "name",
                "isin",
                "market_symbol",
                "category",
                "platform",
                "exclude_from_totals",
            ),
            "transactions": _ordered_values(
                InvestmentTransaction.objects.filter(user=user),
                "id",
                "asset_id",
                "date",
                "action",
                "shares",
                "price_per_share",
                "amount",
                "notes",
            ),
            "history": _ordered_values(
                AssetHistory.objects.filter(user=user),
                "id",
                "asset_id",
                "date",
                "total_value",
            ),
        },
        "holdings": {
            "accounts": _ordered_values(
                BankAccount.objects.filter(user=user),
                "id",
                "name",
                "institution",
                "account_type",
                "currency",
                "iban",
                "notes",
                "is_active",
            ),
            "snapshots": _ordered_values(
                AccountBalanceSnapshot.objects.filter(user=user),
                "id",
                "account_id",
                "date",
                "balance",
                "interest_earned",
            ),
        },
    }
    content = json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
    username_slug = slugify(user.username) or "account"
    export_date = django_timezone.localdate().isoformat()
    response = HttpResponse(content, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="finorbit-{username_slug}-{export_date}.json"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def delete_account(request):
    if request.method == "POST":
        form = AccountDeletionForm(request.POST, user=request.user)
        if form.is_valid():
            user = request.user
            avatar_storage = user.avatar.storage if user.avatar else None
            avatar_name = user.avatar.name if user.avatar else None

            logout(request)
            user.delete()
            if avatar_storage and avatar_name:
                avatar_storage.delete(avatar_name)

            messages.success(request, "Your FinOrbit account and stored data were deleted.")
            return redirect("account_login")
    else:
        form = AccountDeletionForm(user=request.user)

    return render(request, "users/account_delete.html", {"form": form})
