from django.conf import settings


def feature_flags(request):
    """Expose public feature switches needed by shared templates."""
    return {
        "account_registration_open": settings.ACCOUNT_ALLOW_REGISTRATION,
    }
