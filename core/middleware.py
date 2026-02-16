from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone, translation


class UserPreferencesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            user_settings = getattr(request.user, "settings", None)
            if user_settings:
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
