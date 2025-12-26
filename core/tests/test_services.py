from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date

from holdings.models import BankAccount, AccountBalanceSnapshot
from investments.models import Asset, AssetHistory
from core.services.net_worth import calculate_net_worth


class CoreNetWorthTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        acc = BankAccount.objects.create(
            user=self.user,
            name="Cash"
        )

        AccountBalanceSnapshot.objects.create(
            account=acc,
            date=date(2024, 1, 31),
            balance=1000
        )

        asset = Asset.objects.create(
            user=self.user,
            name="ETF"
        )

        AssetHistory.objects.create(
            asset=asset,
            date=date(2024, 1, 31),
            total_value=2000
        )

    def test_calculate_net_worth(self):
        data = calculate_net_worth(self.user)

        self.assertEqual(data["current_net_worth"], 3000)
        self.assertFalse(data["is_stale"])
