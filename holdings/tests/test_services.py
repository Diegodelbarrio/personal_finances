from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from holdings.models import BankAccount, AccountBalanceSnapshot
from holdings.services.api import (
    get_annual_balance_evolution,
    get_currency_mismatches,
    get_current_value,
)
from holdings.services.history import get_net_worth_evolution
from investments.models import Asset, AssetHistory

User = get_user_model()


class HoldingsServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        self.account = BankAccount.objects.create(
            user=self.user,
            name="Cuenta Principal",
            institution="Test Bank",
            account_type="CHECKING",
        )

        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=self.account,
            date=date(2024, 1, 31),
            balance=1000,
        )

    def test_get_current_value(self):
        value, dates = get_current_value(self.user)

        self.assertEqual(value, 1000)
        self.assertEqual(len(dates), 1)

    def test_net_worth_history_keeps_latest_monthly_snapshot_and_carries_forward(self):
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=self.account,
            date=date(2024, 1, 5),
            balance=500,
        )
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=self.account,
            date=date(2024, 3, 31),
            balance=1500,
        )
        asset = Asset.objects.create(
            user=self.user,
            name="Index Fund",
            category="INDEX_FUND",
            platform="Broker",
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=asset,
            date=date(2024, 1, 10),
            total_value=200,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=asset,
            date=date(2024, 1, 31),
            total_value=300,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=asset,
            date=date(2024, 3, 1),
            total_value=450,
        )

        history = get_net_worth_evolution(self.user)

        self.assertEqual([item["label"] for item in history], ["Jan 24", "Feb 24", "Mar 24"])
        self.assertEqual([item["savings"] for item in history], [1000, 1000, 1500])
        self.assertEqual([item["investments"] for item in history], [300, 300, 450])
        self.assertEqual([item["value"] for item in history], [1300, 1300, 1950])

    @patch("holdings.services.api.timezone.localdate", return_value=date(2026, 8, 30))
    def test_annual_history_carries_previous_year_closing_balance(self, _localdate):
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=self.account,
            date=date(2024, 12, 31),
            balance=1100,
        )
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=self.account,
            date=date(2025, 3, 31),
            balance=1600,
        )

        result = get_annual_balance_evolution(self.user, 2025)

        self.assertEqual(len(result["month_names"]), 12)
        self.assertEqual(result["matrix"][0]["balances"][:4], [1100, 1100, 1600, 1600])
        self.assertEqual(result["monthly_totals"][:4], [1100, 1100, 1600, 1600])

    def test_snapshot_rejects_owner_different_from_account_owner(self):
        other_user = User.objects.create_user(username="other", password="1234")

        with self.assertRaises(ValidationError):
            AccountBalanceSnapshot.objects.create(
                user=other_user,
                account=self.account,
                date=date(2024, 2, 1),
                balance=1,
            )

    def test_account_rejects_currency_different_from_reporting_currency(self):
        with self.assertRaises(ValidationError):
            BankAccount.objects.create(
                user=self.user,
                name="Dollar Account",
                institution="Test Bank",
                account_type="CHECKING",
                currency="USD",
            )

    def test_legacy_mismatched_currency_is_visible_and_excluded_from_total(self):
        usd_account = BankAccount(
            user=self.user,
            name="Legacy Dollar Account",
            institution="Test Bank",
            account_type="CHECKING",
            currency="USD",
        )
        BankAccount.objects.bulk_create([usd_account])
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=usd_account,
            date=date(2024, 2, 1),
            balance=5000,
        )

        value, _dates = get_current_value(self.user)
        mismatches = get_currency_mismatches(self.user)

        self.assertEqual(value, 1000)
        self.assertEqual(
            mismatches,
            [{"id": usd_account.id, "name": "Legacy Dollar Account", "currency": "USD"}],
        )
