import logging
from urllib.parse import urljoin

from django.conf import settings
from django.utils import timezone

from core.services.email_delivery import send_transactional_email


logger = logging.getLogger(__name__)


def _site_url(path=""):
    base_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/") + "/"
    return urljoin(base_url, path.lstrip("/"))


def _new_user_context(user):
    joined_at = timezone.localtime(user.date_joined) if user.date_joined else timezone.localtime()
    return {
        "user": user,
        "username": user.get_username(),
        "email": user.email or "Not provided",
        "full_name": user.get_full_name() or "Not provided",
        "joined_at": joined_at,
        "admin_user_url": _site_url(f"/admin/users/user/{user.pk}/change/"),
        "login_url": _site_url("/accounts/login/"),
    }


def send_new_user_welcome_email(user):
    if not getattr(settings, "NEW_USER_WELCOME_EMAIL_ENABLED", True):
        return None

    if not user.email:
        logger.info(
            "New user welcome email skipped because user_id=%s has no email.",
            getattr(user, "pk", None),
        )
        return None

    context = _new_user_context(user)
    try:
        return send_transactional_email(
            subject="Welcome to FinOrbit",
            to=[user.email],
            template_base="core/email/new_user_welcome",
            context=context,
            headers={"X-FinOrbit-Notification": "new-user-welcome"},
        )
    except Exception:
        logger.exception(
            "Unable to send welcome email for user_id=%s.",
            getattr(user, "pk", None),
        )
        return None


def notify_new_user_signup(user):
    if not getattr(settings, "NEW_USER_NOTIFICATION_ENABLED", True):
        return None

    recipients = list(getattr(settings, "NEW_USER_NOTIFICATION_RECIPIENTS", []))
    if not recipients:
        logger.info("New user admin notification skipped because no recipients are configured.")
        return None

    context = _new_user_context(user)
    try:
        return send_transactional_email(
            subject=f"New user registered: {context['username']}",
            to=recipients,
            template_base="core/email/new_user_notification",
            context=context,
            headers={"X-FinOrbit-Notification": "new-user"},
        )
    except Exception:
        logger.exception(
            "Unable to send new user notification for user_id=%s.",
            getattr(user, "pk", None),
        )
        return None


def send_new_user_signup_emails(user):
    return {
        "welcome": send_new_user_welcome_email(user),
        "admin_notification": notify_new_user_signup(user),
    }
