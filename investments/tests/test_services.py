from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date

from investments.models import Asset, AssetHistory
from investments.services.api import get_portfolio_overview


class InvestmentsServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        asset = Asset.objects.create(
            user=self.user,
            name="ETF World"
        )

        AssetHistory.objects.create(
            asset=asset,
            date=date(2024, 1, 31),
            total_value=5000
        )

    def test_portfolio_overview(self):
        data = get_portfolio_overview(self.user)

        self.assertEqual(data["global_current_value"], 5000)
        self.assertIsNotNone(data["last_market_date"])
