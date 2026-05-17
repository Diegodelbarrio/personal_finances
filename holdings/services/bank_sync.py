import base64
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from holdings.models import AccountBalanceSnapshot, BankAccount, BankConnection


class BankSyncError(Exception):
    pass


class BankSyncConfigurationError(BankSyncError):
    pass


class BankSyncProviderError(BankSyncError):
    pass


@dataclass
class BankAccountData:
    external_id: str
    name: str
    institution_name: str
    currency: str
    balance: Decimal
    account_type: str = "CHECKING"
    iban: str = ""
    reference_date: Optional[date] = None
    raw_details: Optional[dict] = None
    raw_balances: Optional[list] = None


@dataclass
class BankSyncResult:
    accounts_seen: int = 0
    accounts_created: int = 0
    snapshots_created: int = 0
    snapshots_updated: int = 0
    snapshot_date: Optional[date] = None


def _provider_key(value):
    return (value or "").strip().upper()


def _ensure_enabled():
    if not getattr(settings, "BANK_SYNC_ENABLED", False):
        raise BankSyncConfigurationError("Bank sync is disabled. Set BANK_SYNC_ENABLED=True.")


def _parse_decimal(value, context):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BankSyncProviderError(f"Invalid balance amount from provider for {context}.") from exc


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _infer_account_type(details):
    raw_type = str(details.get("cashAccountType") or details.get("accountType") or "").upper()
    if raw_type in {"SVGS", "SAVINGS"}:
        return "SAVINGS"
    if raw_type in {"LOAN", "LLSV", "DEBT"}:
        return "DEBT"
    return "CHECKING"


class BaseBankDataProvider:
    key = None

    def prepare_connection(self, connection, redirect_url, country_code):
        raise NotImplementedError

    def refresh_connection(self, connection):
        raise NotImplementedError

    def complete_connection(self, connection, callback_params):
        return self.refresh_connection(connection)

    def fetch_accounts(self, connection):
        raise NotImplementedError


class MockBankDataProvider(BaseBankDataProvider):
    key = BankConnection.PROVIDER_MOCK

    def prepare_connection(self, connection, redirect_url, country_code):
        connection.external_id = f"mock-{connection.reference}"
        connection.redirect_url = redirect_url
        connection.consent_url = redirect_url
        connection.status = BankConnection.STATUS_LINKED
        connection.accounts = ["mock-checking", "mock-savings"]
        connection.institution_id = connection.institution_id or "SANDBOXFINANCE_SFIN0000"
        connection.institution_name = connection.institution_name or "Sandbox Finance"
        connection.metadata = {
            "country_code": country_code,
            "mode": "mock",
        }
        connection.error_message = ""
        connection.save(
            update_fields=[
                "external_id",
                "redirect_url",
                "consent_url",
                "status",
                "accounts",
                "institution_id",
                "institution_name",
                "metadata",
                "error_message",
                "updated_at",
            ]
        )
        return connection

    def refresh_connection(self, connection):
        if connection.status != BankConnection.STATUS_LINKED:
            connection.status = BankConnection.STATUS_LINKED
            connection.error_message = ""
            connection.save(update_fields=["status", "error_message", "updated_at"])
        return connection

    def fetch_accounts(self, connection):
        today = timezone.localdate()
        institution_name = connection.institution_name or "Sandbox Finance"
        return [
            BankAccountData(
                external_id="mock-checking",
                name="Mock Checking",
                institution_name=institution_name,
                currency="EUR",
                balance=Decimal("3210.45"),
                account_type="CHECKING",
                iban="MOCK-CHECKING",
                reference_date=today,
                raw_details={"mode": "mock"},
                raw_balances=[],
            ),
            BankAccountData(
                external_id="mock-savings",
                name="Mock Emergency Fund",
                institution_name=institution_name,
                currency="EUR",
                balance=Decimal("8400.10"),
                account_type="SAVINGS",
                iban="MOCK-SAVINGS",
                reference_date=today,
                raw_details={"mode": "mock"},
                raw_balances=[],
            ),
        ]


class GoCardlessBankDataProvider(BaseBankDataProvider):
    key = BankConnection.PROVIDER_GOCARDLESS

    def __init__(self):
        self.base_url = settings.GOCARDLESS_BASE_URL.rstrip("/")
        self.secret_id = settings.GOCARDLESS_SECRET_ID
        self.secret_key = settings.GOCARDLESS_SECRET_KEY
        self.refresh_token = settings.GOCARDLESS_REFRESH_TOKEN
        self.timeout = getattr(settings, "BANK_SYNC_HTTP_TIMEOUT", 20)

    def prepare_connection(self, connection, redirect_url, country_code):
        if not connection.institution_id:
            raise BankSyncConfigurationError("A GoCardless institution ID is required.")

        access_token = self._get_access_token()
        agreement = self._request_json(
            "POST",
            "/agreements/enduser/",
            access_token=access_token,
            payload={
                "institution_id": connection.institution_id,
                "max_historical_days": 90,
                "access_valid_for_days": 90,
                "access_scope": ["balances", "details"],
            },
        )
        requisition = self._request_json(
            "POST",
            "/requisitions/",
            access_token=access_token,
            payload={
                "redirect": redirect_url,
                "institution_id": connection.institution_id,
                "reference": str(connection.reference),
                "agreement": agreement.get("id"),
                "user_language": "EN",
            },
        )

        connection.external_id = requisition.get("id", "")
        connection.agreement_id = agreement.get("id", "")
        connection.redirect_url = redirect_url
        connection.consent_url = requisition.get("link", "")
        connection.status = BankConnection.STATUS_CREATED
        connection.accounts = requisition.get("accounts") or []
        connection.metadata = {
            "country_code": country_code,
            "provider_status": requisition.get("status", ""),
        }
        connection.error_message = ""
        connection.save(
            update_fields=[
                "external_id",
                "agreement_id",
                "redirect_url",
                "consent_url",
                "status",
                "accounts",
                "metadata",
                "error_message",
                "updated_at",
            ]
        )
        return connection

    def refresh_connection(self, connection):
        if not connection.external_id:
            raise BankSyncProviderError("The bank connection has no provider requisition ID.")

        requisition = self._request_json(
            "GET",
            f"/requisitions/{connection.external_id}/",
            access_token=self._get_access_token(),
        )
        provider_status = requisition.get("status", "")
        connection.accounts = requisition.get("accounts") or []
        connection.metadata = {
            **(connection.metadata or {}),
            "provider_status": provider_status,
        }
        connection.status = self._map_requisition_status(provider_status)
        connection.error_message = "" if connection.status != BankConnection.STATUS_ERROR else "Bank rejected the connection."
        connection.save(
            update_fields=["accounts", "metadata", "status", "error_message", "updated_at"]
        )
        return connection

    def fetch_accounts(self, connection):
        connection = self.refresh_connection(connection)
        if connection.status != BankConnection.STATUS_LINKED:
            raise BankSyncProviderError("The bank connection is not linked yet.")

        access_token = self._get_access_token()
        accounts = []
        for account_id in connection.accounts:
            details_response = self._request_json(
                "GET",
                f"/accounts/{account_id}/details/",
                access_token=access_token,
            )
            balances_response = self._request_json(
                "GET",
                f"/accounts/{account_id}/balances/",
                access_token=access_token,
            )
            details = details_response.get("account") or details_response
            balances = balances_response.get("balances") or []
            balance = self._select_balance(balances)
            amount = balance.get("balanceAmount") or {}
            currency = amount.get("currency") or details.get("currency") or "EUR"
            name = (
                details.get("displayName")
                or details.get("name")
                or details.get("details")
                or f"{connection.institution_name or connection.institution_id} account"
            )
            accounts.append(
                BankAccountData(
                    external_id=account_id,
                    name=name,
                    institution_name=connection.institution_name or connection.institution_id,
                    currency=currency,
                    balance=_parse_decimal(amount.get("amount"), account_id),
                    account_type=_infer_account_type(details),
                    iban=details.get("iban") or details.get("bban") or "",
                    reference_date=_parse_date(
                        balance.get("referenceDate") or balance.get("lastChangeDateTime")
                    ),
                    raw_details=details,
                    raw_balances=balances,
                )
            )
        return accounts

    def list_institutions(self, country_code):
        query = urlencode({"country": country_code})
        return self._request_json(
            "GET",
            f"/institutions/?{query}",
            access_token=self._get_access_token(),
        )

    def _get_access_token(self):
        refresh_token = self.refresh_token
        if not refresh_token:
            if not self.secret_id or not self.secret_key:
                raise BankSyncConfigurationError(
                    "Set GOCARDLESS_SECRET_ID and GOCARDLESS_SECRET_KEY, or set GOCARDLESS_REFRESH_TOKEN."
                )
            token_response = self._request_json(
                "POST",
                "/token/new/",
                payload={
                    "secret_id": self.secret_id,
                    "secret_key": self.secret_key,
                },
            )
            refresh_token = token_response.get("refresh")

        if not refresh_token:
            raise BankSyncProviderError("GoCardless did not return a refresh token.")

        access_response = self._request_json(
            "POST",
            "/token/refresh/",
            payload={"refresh": refresh_token},
        )
        access_token = access_response.get("access")
        if not access_token:
            raise BankSyncProviderError("GoCardless did not return an access token.")
        return access_token

    def _request_json(self, method, path, payload=None, access_token=None):
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "FinOrbit bank sync",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise BankSyncProviderError(f"GoCardless API error {exc.code}: {body}") from exc
        except URLError as exc:
            raise BankSyncProviderError(f"Could not reach GoCardless: {exc.reason}") from exc

        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise BankSyncProviderError("GoCardless returned invalid JSON.") from exc

    def _select_balance(self, balances):
        if not balances:
            raise BankSyncProviderError("GoCardless returned no balances for an account.")
        preferred_types = ["closingBooked", "interimBooked", "expected", "interimAvailable"]
        for balance_type in preferred_types:
            for balance in balances:
                if balance.get("balanceType") == balance_type:
                    return balance
        return balances[0]

    def _map_requisition_status(self, provider_status):
        if provider_status == "LN":
            return BankConnection.STATUS_LINKED
        if provider_status == "EX":
            return BankConnection.STATUS_EXPIRED
        if provider_status == "RJ":
            return BankConnection.STATUS_ERROR
        return BankConnection.STATUS_CREATED


class YapilyBankDataProvider(BaseBankDataProvider):
    key = BankConnection.PROVIDER_YAPILY

    def __init__(self):
        self.base_url = settings.YAPILY_BASE_URL.rstrip("/")
        self.application_id = settings.YAPILY_APPLICATION_ID
        self.application_secret = settings.YAPILY_APPLICATION_SECRET
        self.timeout = getattr(settings, "BANK_SYNC_HTTP_TIMEOUT", 20)

    def prepare_connection(self, connection, redirect_url, country_code):
        if not self.application_id or not self.application_secret:
            raise BankSyncConfigurationError(
                "Set YAPILY_APPLICATION_ID and YAPILY_APPLICATION_SECRET."
            )
        if not connection.institution_id:
            connection.institution_id = "modelo-sandbox"
        if not connection.institution_name:
            connection.institution_name = connection.institution_id

        auth_request = self._request_json(
            "POST",
            "/account-auth-requests",
            payload={
                "applicationUserId": f"finorbit-{connection.user_id}",
                "institutionId": connection.institution_id,
                "callback": redirect_url,
            },
        )
        data = auth_request.get("data") or {}
        connection.external_id = data.get("id", "")
        connection.agreement_id = data.get("institutionConsentId", "")
        connection.redirect_url = redirect_url
        connection.consent_url = data.get("authorisationUrl", "")
        connection.status = BankConnection.STATUS_CREATED
        connection.metadata = {
            "country_code": country_code,
            "provider_status": data.get("status", ""),
            "state": data.get("state", ""),
            "user_uuid": data.get("userUuid", ""),
        }
        connection.error_message = ""
        connection.save(
            update_fields=[
                "external_id",
                "agreement_id",
                "redirect_url",
                "consent_url",
                "status",
                "institution_id",
                "institution_name",
                "metadata",
                "error_message",
                "updated_at",
            ]
        )
        return connection

    def complete_connection(self, connection, callback_params):
        consent_token = callback_params.get("consent") or callback_params.get("consentToken")
        error = callback_params.get("error")
        if error:
            connection.status = BankConnection.STATUS_ERROR
            connection.error_message = error
            connection.metadata = {
                **(connection.metadata or {}),
                "error_source": callback_params.get("error-source", ""),
                "institution": callback_params.get("institution", ""),
            }
            connection.save(
                update_fields=["status", "error_message", "metadata", "updated_at"]
            )
            raise BankSyncProviderError(f"Yapily authorisation failed: {error}")

        if not consent_token:
            raise BankSyncProviderError("Yapily callback did not include a consent token.")

        connection.consent_token = consent_token
        connection.status = BankConnection.STATUS_LINKED
        connection.error_message = ""
        connection.metadata = {
            **(connection.metadata or {}),
            "application_user_id": callback_params.get("application-user-id", ""),
            "user_uuid": callback_params.get("user-uuid", ""),
            "institution": callback_params.get("institution", connection.institution_id),
        }
        connection.save(
            update_fields=[
                "consent_token",
                "status",
                "error_message",
                "metadata",
                "updated_at",
            ]
        )
        return connection

    def refresh_connection(self, connection):
        if connection.consent_token:
            connection.status = BankConnection.STATUS_LINKED
            connection.error_message = ""
        else:
            connection.status = BankConnection.STATUS_CREATED
        connection.save(update_fields=["status", "error_message", "updated_at"])
        return connection

    def fetch_accounts(self, connection):
        if not connection.consent_token:
            raise BankSyncProviderError("The Yapily connection has no consent token yet.")

        response = self._request_json(
            "GET",
            "/accounts",
            consent_token=connection.consent_token,
        )
        provider_accounts = response.get("data") or []
        accounts = []
        for account in provider_accounts:
            balance = self._select_account_balance(account)
            amount = self._extract_balance_amount(balance, account)
            currency = amount.get("currency") or account.get("currency") or "EUR"
            external_id = str(account.get("id") or account.get("accountId") or "")
            if not external_id:
                continue
            reference_date = None
            if isinstance(balance, dict):
                reference_date = _parse_date(balance.get("dateTime") or balance.get("date"))
            accounts.append(
                BankAccountData(
                    external_id=external_id,
                    name=self._account_name(account),
                    institution_name=connection.institution_name or connection.institution_id,
                    currency=currency,
                    balance=_parse_decimal(amount.get("amount"), external_id),
                    account_type=self._infer_yapily_account_type(account),
                    iban=self._account_identifier(account),
                    reference_date=reference_date,
                    raw_details=account,
                    raw_balances=account.get("accountBalances") or [],
                )
            )

        if not accounts:
            raise BankSyncProviderError("Yapily returned no accounts for this consent.")

        connection.accounts = [account.external_id for account in accounts]
        connection.save(update_fields=["accounts", "updated_at"])
        return accounts

    def list_institutions(self, country_code):
        return self._request_json("GET", "/institutions")

    def _request_json(self, method, path, payload=None, consent_token=None):
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": f"Basic {self._basic_auth_token()}",
            "User-Agent": "FinOrbit bank sync",
        }
        if consent_token:
            headers["consent"] = consent_token
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise BankSyncProviderError(f"Yapily API error {exc.code}: {body}") from exc
        except URLError as exc:
            raise BankSyncProviderError(f"Could not reach Yapily: {exc.reason}") from exc

        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise BankSyncProviderError("Yapily returned invalid JSON.") from exc

    def _basic_auth_token(self):
        credentials = f"{self.application_id}:{self.application_secret}".encode("utf-8")
        return base64.b64encode(credentials).decode("ascii")

    def _select_account_balance(self, account):
        balances = account.get("accountBalances") or []
        preferred_types = [
            "CLOSING_BOOKED",
            "CLOSING_AVAILABLE",
            "INTERIM_BOOKED",
            "INTERIM_AVAILABLE",
            "EXPECTED",
            "AUTHORISED",
        ]
        for balance_type in preferred_types:
            for balance in balances:
                if balance.get("type") == balance_type:
                    return balance
        if balances:
            return balances[0]
        return {
            "balanceAmount": {
                "amount": account.get("balance"),
                "currency": account.get("currency"),
            }
        }

    def _extract_balance_amount(self, balance, account):
        if isinstance(balance, dict):
            amount = balance.get("balanceAmount") or balance.get("amount")
            if isinstance(amount, dict):
                return amount
            if amount is not None:
                return {"amount": amount, "currency": account.get("currency")}
        return {"amount": account.get("balance"), "currency": account.get("currency")}

    def _account_name(self, account):
        names = account.get("accountNames") or []
        account_name = ""
        if names and isinstance(names[0], dict):
            account_name = names[0].get("name", "")
        return (
            account.get("nickname")
            or account_name
            or account.get("description")
            or account.get("type")
            or "Yapily account"
        )

    def _account_identifier(self, account):
        identifiers = account.get("accountIdentifications") or []
        for preferred_type in ("IBAN", "BBAN", "ACCOUNT_NUMBER"):
            for identifier in identifiers:
                if identifier.get("type") == preferred_type:
                    return identifier.get("identification", "")
        return ""

    def _infer_yapily_account_type(self, account):
        raw_type = str(account.get("accountType") or account.get("type") or "").upper()
        if "SAV" in raw_type:
            return "SAVINGS"
        if "LOAN" in raw_type or "CREDIT" in raw_type:
            return "DEBT"
        return "CHECKING"


PROVIDER_CLASSES: Dict[str, type] = {
    BankConnection.PROVIDER_MOCK: MockBankDataProvider,
    BankConnection.PROVIDER_GOCARDLESS: GoCardlessBankDataProvider,
    BankConnection.PROVIDER_YAPILY: YapilyBankDataProvider,
}


def get_provider(provider_key):
    provider_key = _provider_key(provider_key)
    provider_class = PROVIDER_CLASSES.get(provider_key)
    if not provider_class:
        raise BankSyncConfigurationError(f"Unsupported bank sync provider: {provider_key}")
    return provider_class()


def create_bank_connection(
    user,
    provider_key,
    institution_id="",
    institution_name="",
    redirect_url="",
    country_code="",
):
    _ensure_enabled()
    provider_key = _provider_key(provider_key)
    provider = get_provider(provider_key)
    connection = BankConnection.objects.create(
        user=user,
        provider=provider_key,
        institution_id=institution_id,
        institution_name=institution_name,
    )
    if redirect_url and "{reference}" in redirect_url:
        redirect_url = redirect_url.format(reference=connection.reference)
    try:
        return provider.prepare_connection(
            connection=connection,
            redirect_url=redirect_url,
            country_code=country_code,
        )
    except BankSyncError as exc:
        connection.status = BankConnection.STATUS_ERROR
        connection.error_message = str(exc)
        connection.save(update_fields=["status", "error_message", "updated_at"])
        raise


def refresh_bank_connection(connection):
    _ensure_enabled()
    provider = get_provider(connection.provider)
    return provider.refresh_connection(connection)


def list_bank_institutions(provider_key, country_code=""):
    _ensure_enabled()
    provider = get_provider(provider_key)
    if not hasattr(provider, "list_institutions"):
        return []

    response = provider.list_institutions(country_code)
    institutions = response.get("data") if isinstance(response, dict) else response
    if not institutions:
        return []

    normalized_country = (country_code or "").strip().upper()
    filtered = []
    for institution in institutions:
        if normalized_country and not _institution_supports_country(
            institution,
            normalized_country,
        ):
            continue
        filtered.append(institution)

    return sorted(filtered, key=lambda item: item.get("name") or item.get("id") or "")


def _institution_supports_country(institution, country_code):
    countries = institution.get("countries") or []
    if not countries:
        return True
    for country in countries:
        if isinstance(country, str) and country.upper() == country_code:
            return True
        if str(country.get("countryCode2", "")).upper() == country_code:
            return True
    return False


def complete_bank_connection(connection, callback_params):
    _ensure_enabled()
    provider = get_provider(connection.provider)
    return provider.complete_connection(connection, callback_params)


def sync_bank_connection(connection, snapshot_date=None):
    _ensure_enabled()
    provider = get_provider(connection.provider)
    account_data = provider.fetch_accounts(connection)
    now = timezone.now()
    result = BankSyncResult(accounts_seen=len(account_data), snapshot_date=snapshot_date)

    with transaction.atomic():
        for data in account_data:
            account, account_created = BankAccount.objects.update_or_create(
                user=connection.user,
                sync_provider=connection.provider,
                external_account_id=data.external_id,
                defaults={
                    "name": data.name[:100],
                    "institution": data.institution_name[:100],
                    "account_type": data.account_type,
                    "currency": data.currency[:3],
                    "iban": data.iban or None,
                    "is_active": True,
                    "sync_connection": connection,
                    "last_synced_at": now,
                },
            )
            snapshot_day = snapshot_date or data.reference_date or timezone.localdate()
            result.snapshot_date = snapshot_day
            _, snapshot_created = AccountBalanceSnapshot.objects.update_or_create(
                user=connection.user,
                account=account,
                date=snapshot_day,
                defaults={
                    "balance": data.balance,
                },
            )
            if account_created:
                result.accounts_created += 1
            if snapshot_created:
                result.snapshots_created += 1
            else:
                result.snapshots_updated += 1

        connection.last_synced_at = now
        connection.status = BankConnection.STATUS_LINKED
        connection.error_message = ""
        connection.save(
            update_fields=["last_synced_at", "status", "error_message", "updated_at"]
        )

    return result


def sync_all_linked_connections(user=None, snapshot_date=None):
    queryset = BankConnection.objects.filter(status=BankConnection.STATUS_LINKED)
    if user is not None:
        queryset = queryset.filter(user=user)

    results = []
    for connection in queryset.select_related("user"):
        results.append((connection, sync_bank_connection(connection, snapshot_date=snapshot_date)))
    return results
