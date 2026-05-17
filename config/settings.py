"""
Django settings for config project.
"""

import importlib.util
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

try:
    import dj_database_url
except ImportError:  # pragma: no cover
    dj_database_url = None

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
IS_RUNNING_TESTS = "test" in sys.argv


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name, default=0):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc


DEBUG = env_bool("DEBUG", default=False)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-secret-key-change-before-deploy"
    else:
        raise ImproperlyConfigured("SECRET_KEY is required when DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if not ALLOWED_HOSTS and DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS cannot be empty when DEBUG=False.")

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default="https://*.trycloudflare.com,http://localhost:8000,http://127.0.0.1:8000",
)

IS_WHITENOISE_AVAILABLE = importlib.util.find_spec("whitenoise") is not None


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "finances",
    "investments",
    "knowledge",
    "users",
    "core",
    "holdings",
    "reports",
    "settings",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]
if IS_WHITENOISE_AVAILABLE:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.UserPreferencesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


database_url = os.getenv("DATABASE_URL")
if database_url and dj_database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "600")),
            ssl_require=env_bool("DB_SSL_REQUIRE", default=not DEBUG),
        )
    }
elif database_url and not dj_database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL is set but dj-database-url is not installed."
    )
elif os.getenv("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.getenv("DB_NAME"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

if (
    DATABASES["default"]["ENGINE"].endswith("postgresql")
    and not DEBUG
    and env_bool("DB_SSL_REQUIRE", default=True)
):
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"]["sslmode"] = "require"


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / ".django_cache",
        "TIMEOUT": 300,
        "OPTIONS": {
            "MAX_ENTRIES": 2000,
        },
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en-us", "English"),
    ("es", "Spanish"),
]
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
if IS_WHITENOISE_AVAILABLE:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_HSTS_SECONDS = int(
    os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", default=not DEBUG)


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AUTH_USER_MODEL = "users.User"
SITE_ID = int(os.getenv("SITE_ID", "1"))

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_EMAIL_VERIFICATION = os.getenv("ACCOUNT_EMAIL_VERIFICATION", "none")
ACCOUNT_UNIQUE_EMAIL = env_bool("ACCOUNT_UNIQUE_EMAIL", default=True)
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https" if not DEBUG else "http"
ACCOUNT_EMAIL_SUBJECT_PREFIX = os.getenv("ACCOUNT_EMAIL_SUBJECT_PREFIX", "[FinOrbit] ")

# Email delivery:
# - In local development (DEBUG=True), default to console backend
#   so email flows (allauth verification/reset) don't fail due to missing SMTP.
# - In production, default to SMTP and configure via env vars.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@finorbit.app")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[FinOrbit] ")
EMAIL_FAIL_SILENTLY = env_bool("EMAIL_FAIL_SILENTLY", default=False)

# macOS + python.org builds may miss a system OpenSSL CA path.
# If SMTP is enabled and SSL_CERT_FILE is not set, use certifi bundle when available.
if EMAIL_BACKEND.endswith("smtp.EmailBackend") and "SSL_CERT_FILE" not in os.environ:
    certifi_where = getattr(certifi, "where", None) if certifi is not None else None
    if callable(certifi_where):
        os.environ["SSL_CERT_FILE"] = certifi_where()

if EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
    EMAIL_PORT = env_int("EMAIL_PORT", 25)
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=False)
    EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", default=False)
    EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)

# Transactional mail settings (verification, password reset, alerts)
EMAIL_TRANSACTIONAL_FROM_EMAIL = os.getenv(
    "EMAIL_TRANSACTIONAL_FROM_EMAIL",
    DEFAULT_FROM_EMAIL,
)
EMAIL_TRANSACTIONAL_REPLY_TO = env_list("EMAIL_TRANSACTIONAL_REPLY_TO")
NEW_USER_NOTIFICATION_ENABLED = env_bool(
    "NEW_USER_NOTIFICATION_ENABLED",
    default=not IS_RUNNING_TESTS,
)
NEW_USER_NOTIFICATION_RECIPIENTS = env_list(
    "NEW_USER_NOTIFICATION_RECIPIENTS",
    default=SERVER_EMAIL,
)
NEW_USER_WELCOME_EMAIL_ENABLED = env_bool(
    "NEW_USER_WELCOME_EMAIL_ENABLED",
    default=not IS_RUNNING_TESTS,
)

# Marketing/bulk mail settings (newsletters, campaigns)
EMAIL_MARKETING_ENABLED = env_bool("EMAIL_MARKETING_ENABLED", default=False)
EMAIL_MARKETING_BACKEND = os.getenv("EMAIL_MARKETING_BACKEND", EMAIL_BACKEND)
EMAIL_MARKETING_FROM_EMAIL = os.getenv(
    "EMAIL_MARKETING_FROM_EMAIL",
    EMAIL_TRANSACTIONAL_FROM_EMAIL,
)
EMAIL_MARKETING_REPLY_TO = env_list("EMAIL_MARKETING_REPLY_TO")
EMAIL_MARKETING_BATCH_SIZE = env_int("EMAIL_MARKETING_BATCH_SIZE", 500)

if EMAIL_MARKETING_BACKEND.endswith("smtp.EmailBackend"):
    EMAIL_MARKETING_HOST = os.getenv("EMAIL_MARKETING_HOST", os.getenv("EMAIL_HOST", "localhost"))
    EMAIL_MARKETING_PORT = env_int(
        "EMAIL_MARKETING_PORT",
        env_int("EMAIL_PORT", 25),
    )
    EMAIL_MARKETING_HOST_USER = os.getenv(
        "EMAIL_MARKETING_HOST_USER",
        os.getenv("EMAIL_HOST_USER", ""),
    )
    EMAIL_MARKETING_HOST_PASSWORD = os.getenv(
        "EMAIL_MARKETING_HOST_PASSWORD",
        os.getenv("EMAIL_HOST_PASSWORD", ""),
    )
    EMAIL_MARKETING_USE_TLS = env_bool(
        "EMAIL_MARKETING_USE_TLS",
        default=env_bool("EMAIL_USE_TLS", default=False),
    )
    EMAIL_MARKETING_USE_SSL = env_bool(
        "EMAIL_MARKETING_USE_SSL",
        default=env_bool("EMAIL_USE_SSL", default=False),
    )
    EMAIL_MARKETING_TIMEOUT = env_int(
        "EMAIL_MARKETING_TIMEOUT",
        env_int("EMAIL_TIMEOUT", 10),
    )

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SILENCED_SYSTEM_CHECKS = ["account.W001"]
ACCOUNT_SIGNUP_FIELDS = [
    "username*",
    "email",
    "password1*",
    "password2*",
]

SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")


# Bank account data sync
BANK_SYNC_ENABLED = env_bool("BANK_SYNC_ENABLED", default=DEBUG)
BANK_SYNC_PROVIDER = os.getenv("BANK_SYNC_PROVIDER", "mock").strip().lower()
BANK_SYNC_COUNTRY_CODE = os.getenv("BANK_SYNC_COUNTRY_CODE", "ES").strip().upper()
BANK_SYNC_HTTP_TIMEOUT = env_int("BANK_SYNC_HTTP_TIMEOUT", 20)

GOCARDLESS_BASE_URL = os.getenv(
    "GOCARDLESS_BASE_URL",
    "https://bankaccountdata.gocardless.com/api/v2",
).rstrip("/")
GOCARDLESS_SECRET_ID = os.getenv("GOCARDLESS_SECRET_ID", "")
GOCARDLESS_SECRET_KEY = os.getenv("GOCARDLESS_SECRET_KEY", "")
GOCARDLESS_REFRESH_TOKEN = os.getenv("GOCARDLESS_REFRESH_TOKEN", "")

YAPILY_BASE_URL = os.getenv("YAPILY_BASE_URL", "https://api.yapily.com").rstrip("/")
YAPILY_APPLICATION_ID = os.getenv("YAPILY_APPLICATION_ID", "")
YAPILY_APPLICATION_SECRET = os.getenv("YAPILY_APPLICATION_SECRET", "")
