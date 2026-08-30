from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """Keep public registration closed unless it is explicitly enabled."""

    def is_open_for_signup(self, request):
        return settings.ACCOUNT_ALLOW_REGISTRATION
