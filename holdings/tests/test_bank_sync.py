import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from holdings.models import AccountBalanceSnapshot, BankAccount, BankConnection
from holdings.services.bank_sync import (
    complete_bank_connection,
    create_bank_connection,
    list_bank_institutions,
    sync_bank_connection,
)

User = get_user_model()


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@override_settings(BANK_SYNC_ENABLED=True)
class BankSyncServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")

    def test_mock_bank_sync_creates_accounts_and_snapshots(self):
        connection = create_bank_connection(
            user=self.user,
            provider_key=BankConnection.PROVIDER_MOCK,
            redirect_url="http://testserver/holdings/bank-sync/callback/{reference}/",
        )

        result = sync_bank_connection(connection)

        self.assertEqual(result.accounts_seen, 2)
        self.assertEqual(result.accounts_created, 2)
        self.assertEqual(result.snapshots_created, 2)
        self.assertEqual(BankAccount.objects.filter(user=self.user).count(), 2)
        self.assertEqual(AccountBalanceSnapshot.objects.filter(user=self.user).count(), 2)
        self.assertTrue(
            AccountBalanceSnapshot.objects.filter(
                user=self.user,
                account__name="Mock Checking",
                balance=Decimal("3210.45"),
            ).exists()
        )

    def test_mock_bank_sync_updates_existing_snapshot(self):
        connection = create_bank_connection(
            user=self.user,
            provider_key=BankConnection.PROVIDER_MOCK,
            redirect_url="http://testserver/holdings/bank-sync/callback/{reference}/",
        )

        sync_bank_connection(connection)
        second_result = sync_bank_connection(connection)

        self.assertEqual(second_result.accounts_created, 0)
        self.assertEqual(second_result.snapshots_created, 0)
        self.assertEqual(second_result.snapshots_updated, 2)
        self.assertEqual(BankAccount.objects.filter(user=self.user).count(), 2)
        self.assertEqual(AccountBalanceSnapshot.objects.filter(user=self.user).count(), 2)


@override_settings(
    BANK_SYNC_ENABLED=True,
    YAPILY_APPLICATION_ID="test-application-id",
    YAPILY_APPLICATION_SECRET="test-application-secret",
)
class YapilyBankSyncServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")

    @patch("holdings.services.bank_sync.urlopen")
    def test_yapily_connection_stores_authorisation_url(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(
            {
                "data": {
                    "id": "auth-request-1",
                    "institutionConsentId": "institution-consent-1",
                    "status": "AWAITING_AUTHORIZATION",
                    "state": "state-1",
                    "userUuid": "user-uuid-1",
                    "authorisationUrl": "https://auth.example/continue",
                }
            }
        )

        connection = create_bank_connection(
            user=self.user,
            provider_key=BankConnection.PROVIDER_YAPILY,
            institution_id="modelo-sandbox",
            redirect_url="http://testserver/holdings/bank-sync/callback/{reference}/",
        )

        self.assertEqual(connection.external_id, "auth-request-1")
        self.assertEqual(connection.agreement_id, "institution-consent-1")
        self.assertEqual(connection.consent_url, "https://auth.example/continue")
        self.assertEqual(connection.status, BankConnection.STATUS_CREATED)

    @patch("holdings.services.bank_sync.urlopen")
    def test_yapily_callback_token_syncs_accounts_and_snapshots(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(
            {
                "data": [
                    {
                        "id": "account-1",
                        "type": "Personal - Current",
                        "accountType": "CURRENT",
                        "nickname": "Sandbox Current",
                        "currency": "EUR",
                        "accountIdentifications": [
                            {"type": "IBAN", "identification": "ES0000000001"}
                        ],
                        "accountBalances": [
                            {
                                "type": "CLOSING_BOOKED",
                                "dateTime": "2026-05-17T10:15:00Z",
                                "balanceAmount": {
                                    "amount": "1234.56",
                                    "currency": "EUR",
                                },
                            }
                        ],
                    }
                ]
            }
        )
        connection = BankConnection.objects.create(
            user=self.user,
            provider=BankConnection.PROVIDER_YAPILY,
            institution_id="modelo-sandbox",
            institution_name="Modelo Sandbox",
            external_id="auth-request-1",
        )

        complete_bank_connection(
            connection,
            {
                "consent": "consent-token-1",
                "application-user-id": "finorbit-1",
                "user-uuid": "user-uuid-1",
                "institution": "modelo-sandbox",
            },
        )
        result = sync_bank_connection(connection)

        self.assertEqual(result.accounts_seen, 1)
        self.assertEqual(result.accounts_created, 1)
        account = BankAccount.objects.get(user=self.user)
        snapshot = AccountBalanceSnapshot.objects.get(user=self.user, account=account)
        self.assertEqual(account.name, "Sandbox Current")
        self.assertEqual(account.iban, "ES0000000001")
        self.assertEqual(snapshot.balance, Decimal("1234.56"))

    @patch("holdings.services.bank_sync.urlopen")
    def test_yapily_institutions_are_filtered_by_country(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(
            {
                "data": [
                    {
                        "id": "modelo-sandbox",
                        "name": "Modelo Sandbox",
                        "countries": [{"countryCode2": "ES"}],
                    },
                    {
                        "id": "gb-bank",
                        "name": "GB Bank",
                        "countries": [{"countryCode2": "GB"}],
                    },
                ]
            }
        )

        institutions = list_bank_institutions(
            BankConnection.PROVIDER_YAPILY,
            country_code="ES",
        )

        self.assertEqual([institution["id"] for institution in institutions], ["modelo-sandbox"])


@override_settings(BANK_SYNC_ENABLED=True, BANK_SYNC_PROVIDER="mock")
class BankSyncViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")

    def test_bank_sync_dashboard_requires_login(self):
        response = self.client.get(reverse("holdings:bank_sync"))

        self.assertEqual(response.status_code, 302)

    def test_bank_sync_dashboard_renders_for_logged_user(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.get(reverse("holdings:bank_sync"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bank Sync")

    def test_start_mock_connection_syncs_balances(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.post(
            reverse("holdings:bank_sync_start"),
            {
                "provider": BankConnection.PROVIDER_MOCK,
                "country_code": "ES",
                "institution_id": "",
                "institution_name": "",
            },
        )

        self.assertRedirects(response, reverse("holdings:bank_sync"))
        connection = BankConnection.objects.get(user=self.user)
        self.assertEqual(connection.status, BankConnection.STATUS_LINKED)
        self.assertEqual(BankAccount.objects.filter(user=self.user).count(), 2)
        self.assertEqual(AccountBalanceSnapshot.objects.filter(user=self.user).count(), 2)

    def test_delete_connection_removes_connection_and_keeps_imported_history(self):
        self.client.login(username="diego", password="test1234")
        connection = create_bank_connection(
            user=self.user,
            provider_key=BankConnection.PROVIDER_MOCK,
            redirect_url="http://testserver/holdings/bank-sync/callback/{reference}/",
        )
        sync_bank_connection(connection)

        response = self.client.post(
            reverse("holdings:bank_sync_delete_connection", args=[connection.id])
        )

        self.assertRedirects(response, reverse("holdings:bank_sync"))
        self.assertFalse(BankConnection.objects.filter(id=connection.id).exists())
        self.assertEqual(BankAccount.objects.filter(user=self.user).count(), 2)
        self.assertEqual(AccountBalanceSnapshot.objects.filter(user=self.user).count(), 2)
