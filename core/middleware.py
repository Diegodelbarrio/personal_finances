from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone, translation

from core.currency import get_currency_display_suffix


class ResponseSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response


class UserPreferencesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_currency = "EUR"
        request.user_currency_symbol = get_currency_display_suffix(
            request.user_currency
        )
        if request.user.is_authenticated:
            user_settings = getattr(request.user, "settings", None)
            if user_settings:
                request.user_currency = user_settings.main_currency or "EUR"
                request.user_currency_symbol = get_currency_display_suffix(
                    request.user_currency
                )
                language_code = (user_settings.language_code or "").strip()
                if language_code:
                    translation.activate(language_code)
                    request.LANGUAGE_CODE = language_code

                timezone_name = (user_settings.timezone or "").strip()
                if timezone_name:
                    try:
                        timezone.activate(ZoneInfo(timezone_name))
                    except ZoneInfoNotFoundError:
                        timezone.deactivate()

        response = self.get_response(request)
        translation.deactivate()
        timezone.deactivate()
        return response
