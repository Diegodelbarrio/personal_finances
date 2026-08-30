from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date
from unittest.mock import patch

from django.db import OperationalError
from django.urls import reverse

from holdings.models import BankAccount, AccountBalanceSnapshot
from investments.models import Asset, AssetHistory
from core.services.net_worth import calculate_net_worth

User = get_user_model()


class HealthCheckTest(TestCase):
    def test_health_check_reports_ready_database(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(
            response["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

    @patch("core.views.connection.cursor", side_effect=OperationalError("unavailable"))
    def test_health_check_fails_closed_without_database(self, _cursor):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unhealthy"})


class CoreNetWorthTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        acc = BankAccount.objects.create(
            user=self.user,
            name="Cash",
            institution="Test Bank",
            account_type="CHECKING",
        )

        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=acc,
            date=date(2024, 1, 31),
            balance=1000,
        )

        asset = Asset.objects.create(
            user=self.user,
            name="ETF",
            category="INDEX_FUND",
            platform="Test Broker",
        )

        AssetHistory.objects.create(
            user=self.user,
            asset=asset,
            date=date(2024, 1, 31),
            total_value=2000,
        )

    def test_calculate_net_worth(self):
        data = calculate_net_worth(self.user)

        self.assertEqual(data["current_net_worth"], 3000)
        self.assertEqual(data["last_market_date"], date(2024, 1, 31))
        self.assertEqual(data["data_status"], "danger")

    def test_global_net_worth_includes_assets_excluded_from_personal_analytics(self):
        excluded_asset = Asset.objects.create(
            user=self.user,
            name="Managed for family",
            category="INDEX_FUND",
            platform="Test Broker",
            exclude_from_totals=True,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=excluded_asset,
            date=date(2024, 1, 31),
            total_value=10000,
        )

        data = calculate_net_worth(self.user)

        self.assertEqual(data["current_net_worth"], 13000)
        self.assertEqual(data["investments_value"], 12000)

    def test_family_investments_count_only_for_their_owner(self):
        family_asset = Asset.objects.create(
            user=self.user,
            name="Family Investments",
            category="INDEX_FUND",
            platform="Test Broker",
            exclude_from_totals=True,
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=family_asset,
            date=date(2024, 1, 31),
            total_value=4000,
        )

        other_user = User.objects.create_user(username="other", password="1234")
        other_family_asset = Asset.objects.create(
            user=other_user,
            name="Family Investments",
            category="INDEX_FUND",
            platform="Other Broker",
            exclude_from_totals=True,
        )
        AssetHistory.objects.create(
            user=other_user,
            asset=other_family_asset,
            date=date(2024, 1, 31),
            total_value=90000,
        )

        data = calculate_net_worth(self.user)

        self.assertEqual(data["current_net_worth"], 7000)
        self.assertEqual(data["investments_value"], 6000)
