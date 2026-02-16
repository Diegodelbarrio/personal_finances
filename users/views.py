from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import redirect, render
from django.utils import timezone as django_timezone
from django.utils.translation import activate as activate_language
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from settings.services.api import SettingsService

from .forms import ProfileForm, ProfilePreferencesForm


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

        if not profile_form.has_changed() and not preferences_form.has_changed():
            messages.info(
                request,
                "No changes detected. Nothing to update.",
                extra_tags="users_profile",
            )
            return redirect("users:profile")

        if profile_form.is_valid() and preferences_form.is_valid():
            with db_transaction.atomic():
                profile_form.save()
                preferences = preferences_form.save()

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

    context = {
        "profile_form": profile_form,
        "preferences_form": preferences_form,
        "profile_stats": {
            "member_since": request.user.date_joined,
            "last_login": request.user.last_login,
            "main_currency": user_settings.main_currency,
            "finances_transactions": request.user.finances_transactions.count(),
            "assets": request.user.assets.count(),
            "investment_transactions": request.user.investment_transactions.count(),
            "bank_accounts": request.user.accounts.count(),
        },
    }
    return render(request, "users/profile.html", context)
