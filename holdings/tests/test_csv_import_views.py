from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from holdings.models import AccountBalanceSnapshot, BankAccount

User = get_user_model()


class HoldingCSVImportViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")

    def test_import_holding_snapshots_csv_creates_account_and_snapshot(self):
        self.client.login(username="diego", password="test1234")
        csv_content = (
            "date,account_name,institution,account_type,currency,balance,interest_earned\n"
            "2026-02-28,Main Checking,ING,CHECKING,EUR,3050.75,2.20\n"
        )
        csv_file = SimpleUploadedFile(
            "holding_snapshots.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("holdings:import_snapshots_csv"),
            {
                "csv_file": csv_file,
                "next": "/home/",
            },
        )

        self.assertRedirects(response, "/home/")
        account = BankAccount.objects.get(user=self.user, name="Main Checking")
        snapshot = AccountBalanceSnapshot.objects.get(user=self.user, account=account)
        self.assertEqual(account.institution, "ING")
        self.assertEqual(account.account_type, "CHECKING")
        self.assertEqual(snapshot.date, date(2026, 2, 28))
        self.assertEqual(snapshot.balance, Decimal("3050.75"))
        self.assertEqual(snapshot.interest_earned, Decimal("2.20"))

    def test_import_holding_snapshots_csv_rejects_invalid_account_type(self):
        self.client.login(username="diego", password="test1234")
        csv_content = (
            "date,account_name,institution,account_type,currency,balance\n"
            "2026-02-28,Main Checking,ING,INVALID,EUR,3050.75\n"
        )
        csv_file = SimpleUploadedFile(
            "holding_snapshots_invalid.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("holdings:import_snapshots_csv"),
            {"csv_file": csv_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account_type must be one of")
        self.assertFalse(AccountBalanceSnapshot.objects.filter(user=self.user).exists())

    def test_import_rejects_currency_different_from_reporting_currency(self):
        self.client.login(username="diego", password="test1234")
        csv_file = SimpleUploadedFile(
            "holding_snapshots_usd.csv",
            (
                "date,account_name,institution,account_type,currency,balance\n"
                "2026-02-28,Dollar Account,Bank,CHECKING,USD,100\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("holdings:import_snapshots_csv"),
            {"csv_file": csv_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must match your reporting currency (EUR)")
        self.assertFalse(BankAccount.objects.filter(user=self.user).exists())
