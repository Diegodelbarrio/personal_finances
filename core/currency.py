CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
}


def get_user_currency(user):
    user_settings = getattr(user, "settings", None)
    code = getattr(user_settings, "main_currency", "EUR") or "EUR"
    return code.upper()


def get_currency_symbol(currency_code):
    code = (currency_code or "EUR").upper()
    return CURRENCY_SYMBOLS.get(code, code)


def get_currency_display_suffix(currency_code):
    """Return an unambiguous suffix for server-rendered monetary amounts."""
    code = (currency_code or "EUR").upper()
    return f"\u00a0{code}"
