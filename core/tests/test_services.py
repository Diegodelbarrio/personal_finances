from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date

from holdings.models import BankAccount, AccountBalanceSnapshot
from investments.models import Asset, AssetHistory
from core.services.net_worth import calculate_net_worth

User = get_user_model()


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
